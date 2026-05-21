"""
Vehicle Lookup API
- POST /vehicle/lookup-plate  — photo → PlateRecognizer OCR → plate number
- POST /vehicle/decode-vin    — VIN → VehicleDatabases decode + recalls + maintenance + repairs
- POST /vehicle/lookup-plate-vin — plate + state → VehicleDatabases plate-to-VIN → full decode
- GET  /vehicle/recalls/{vin} — recalls by VIN
"""
import os
import logging
import asyncio
import httpx
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from typing import Optional

router = APIRouter()
logger = logging.getLogger("workbay.vehicle")

PLATE_RECOGNIZER_TOKEN = os.getenv("PLATE_RECOGNIZER_TOKEN")
VDB_KEY = os.getenv("VEHICLE_DATABASES_KEY")
VDB_BASE = "https://api.vehicledatabases.com"
NHTSA_BASE = "https://vpic.nhtsa.dot.gov/api/vehicles"

VDB_HEADERS = {"x-AuthKey": VDB_KEY} if VDB_KEY else {}


# ── PlateRecognizer ────────────────────────────────────────────────────────

async def _ocr_plate(image_bytes: bytes, filename: str, region: str = "us") -> dict:
    if not PLATE_RECOGNIZER_TOKEN:
        raise HTTPException(status_code=500, detail="PlateRecognizer token not configured")
    async with httpx.AsyncClient(timeout=15.0) as client:
        r = await client.post(
            "https://api.platerecognizer.com/v1/plate-reader/",
            headers={"Authorization": f"Token {PLATE_RECOGNIZER_TOKEN}"},
            files={"upload": (filename, image_bytes, "image/jpeg")},
            data={"regions": region},
        )
        if r.status_code not in (200, 201):
            raise HTTPException(status_code=502, detail=f"PlateRecognizer error: {r.text}")
        results = r.json().get("results", [])
        if not results:
            raise HTTPException(status_code=422, detail="No license plate detected in image")
        best = results[0]
        return {
            "plate": best["plate"].upper(),
            "confidence": best.get("score", 0),
            "region": best.get("region", {}).get("code", region),
        }


# ── VehicleDatabases ───────────────────────────────────────────────────────

async def _vdb_plate_to_vin(plate: str, state: str) -> Optional[str]:
    """Plate + state → VIN via VehicleDatabases."""
    async with httpx.AsyncClient(timeout=15.0) as client:
        r = await client.get(
            f"{VDB_BASE}/plate-to-vin/{state.upper()}/{plate.upper()}",
            headers=VDB_HEADERS,
        )
        if r.status_code == 200:
            data = r.json()
            return data.get("vin") or data.get("data", {}).get("vin")
        logger.warning(f"Plate-to-VIN failed: {r.status_code} {r.text[:100]}")
        return None


async def _vdb_decode_vin(vin: str) -> dict:
    """Full VIN decode via VehicleDatabases."""
    async with httpx.AsyncClient(timeout=15.0) as client:
        r = await client.get(
            f"{VDB_BASE}/vin-decode/{vin.upper()}",
            headers=VDB_HEADERS,
        )
        if r.status_code != 200:
            # Fallback to NHTSA free decode
            logger.warning(f"VDB VIN decode failed ({r.status_code}), falling back to NHTSA")
            return await _nhtsa_decode_vin(vin)
        data = r.json()
        d = data.get("data", data)
        return {
            "vin": vin.upper(),
            "year": d.get("year") or d.get("model_year"),
            "make": d.get("make"),
            "model": d.get("model"),
            "trim": d.get("trim"),
            "engine": d.get("engine") or d.get("displacement"),
            "cylinders": d.get("cylinders") or d.get("engine_cylinders"),
            "fuel_type": d.get("fuel_type") or d.get("primary_fuel_type"),
            "transmission": d.get("transmission"),
            "drive_type": d.get("drive_type") or d.get("drive"),
            "body_style": d.get("body_style") or d.get("body_class"),
            "doors": d.get("doors"),
            "source": "vehicledatabases",
        }


async def _vdb_recalls(vin: str) -> list:
    """Recalls by VIN via VehicleDatabases."""
    async with httpx.AsyncClient(timeout=15.0) as client:
        r = await client.get(
            f"{VDB_BASE}/vehicle-recalls/{vin.upper()}",
            headers=VDB_HEADERS,
        )
        if r.status_code != 200:
            return []
        data = r.json()
        items = data.get("data", data) if isinstance(data.get("data"), list) else []
        return [
            {
                "campaign": item.get("campaign_number") or item.get("nhtsa_id"),
                "date": item.get("report_date") or item.get("date"),
                "component": item.get("component"),
                "summary": item.get("summary") or item.get("description"),
                "remedy": item.get("remedy"),
            }
            for item in items[:10]
        ]


async def _vdb_maintenance(vin: str) -> dict:
    """Maintenance schedule by VIN via VehicleDatabases."""
    async with httpx.AsyncClient(timeout=15.0) as client:
        r = await client.get(
            f"{VDB_BASE}/vehicle-maintenance/v4/{vin.upper()}",
            headers=VDB_HEADERS,
        )
        if r.status_code != 200:
            return {}
        return r.json().get("data", {})


async def _vdb_repairs(vin: str) -> list:
    """Common repairs by VIN via VehicleDatabases."""
    async with httpx.AsyncClient(timeout=15.0) as client:
        r = await client.get(
            f"{VDB_BASE}/vehicle-repairs/v2/{vin.upper()}",
            headers=VDB_HEADERS,
        )
        if r.status_code != 200:
            return []
        data = r.json()
        items = data.get("data", []) if isinstance(data.get("data"), list) else []
        return items[:15]


# ── NHTSA fallback ─────────────────────────────────────────────────────────

async def _nhtsa_decode_vin(vin: str) -> dict:
    async with httpx.AsyncClient(timeout=15.0) as client:
        r = await client.get(f"{NHTSA_BASE}/DecodeVinValuesExtended/{vin}?format=json")
        if r.status_code != 200:
            raise HTTPException(status_code=502, detail="VIN decode failed")
        res = r.json().get("Results", [{}])[0]
        def g(k): v = res.get(k, ""); return v if v and v != "0" else None
        return {
            "vin": vin.upper(),
            "year": int(g("ModelYear")) if g("ModelYear") else None,
            "make": g("Make"),
            "model": g("Model"),
            "trim": g("Trim"),
            "engine": g("DisplacementL"),
            "cylinders": g("EngineCylinders"),
            "fuel_type": g("FuelTypePrimary"),
            "transmission": g("TransmissionStyle"),
            "drive_type": g("DriveType"),
            "body_style": g("BodyClass"),
            "doors": g("Doors"),
            "source": "nhtsa",
        }


# ── Full decode helper (used by transcript processor too) ──────────────────

async def decode_vin_full(vin: str) -> dict:
    """Decode VIN + fetch recalls + maintenance + repairs concurrently."""
    vehicle, recalls, maintenance, repairs = await asyncio.gather(
        _vdb_decode_vin(vin),
        _vdb_recalls(vin),
        _vdb_maintenance(vin),
        _vdb_repairs(vin),
        return_exceptions=True,
    )
    return {
        "vehicle": vehicle if not isinstance(vehicle, Exception) else {},
        "recalls": recalls if not isinstance(recalls, Exception) else [],
        "maintenance": maintenance if not isinstance(maintenance, Exception) else {},
        "common_repairs": repairs if not isinstance(repairs, Exception) else [],
        "recall_count": len(recalls) if not isinstance(recalls, Exception) else 0,
    }


# ── Endpoints ──────────────────────────────────────────────────────────────

@router.post("/vehicle/lookup-plate")
async def lookup_plate(
    image: UploadFile = File(...),
    region: str = Form(default="us"),
):
    """Photo → plate OCR only. Returns plate + confidence."""
    image_bytes = await image.read()
    plate_result = await _ocr_plate(image_bytes, image.filename or "plate.jpg", region)
    return plate_result


@router.post("/vehicle/lookup-plate-vin")
async def lookup_plate_vin(
    image: UploadFile = File(...),
    state: str = Form(default="FL"),
    region: str = Form(default="us"),
):
    """Photo → plate OCR → plate-to-VIN → full decode + recalls + maintenance."""
    image_bytes = await image.read()
    plate_result = await _ocr_plate(image_bytes, image.filename or "plate.jpg", region)
    plate = plate_result["plate"]

    vin = await _vdb_plate_to_vin(plate, state)
    if not vin:
        return {
            "plate": plate,
            "confidence": plate_result["confidence"],
            "vin": None,
            "message": f"Plate {plate} detected but VIN lookup unavailable. Please enter VIN manually.",
        }

    full = await decode_vin_full(vin)
    return {
        "plate": plate,
        "confidence": plate_result["confidence"],
        **full,
    }


@router.post("/vehicle/decode-vin")
async def decode_vin_endpoint(vin: str = Form(...)):
    """VIN → full vehicle info + recalls + maintenance + common repairs."""
    if len(vin) not in (17,):
        raise HTTPException(status_code=422, detail="VIN must be 17 characters")
    return await decode_vin_full(vin)


@router.get("/vehicle/recalls/{vin}")
async def get_recalls_by_vin(vin: str):
    """Recalls by VIN."""
    return {"vin": vin.upper(), "recalls": await _vdb_recalls(vin)}
