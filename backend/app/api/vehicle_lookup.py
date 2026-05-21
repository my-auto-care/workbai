"""
Vehicle Lookup API — VehicleDatabases.com + PlateRecognizer
- POST /vehicle/lookup-plate       — photo → PlateRecognizer OCR → plate number
- POST /vehicle/lookup-plate-vin   — photo + state → plate OCR → VDB plate-to-VIN → full decode
- POST /vehicle/decode-vin         — VIN → full decode + recalls + maintenance + repairs
- GET  /vehicle/recalls/{vin}      — recalls by VIN
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

def _vdb_headers():
    return {"x-authkey": VDB_KEY} if VDB_KEY else {}


# ── PlateRecognizer OCR ────────────────────────────────────────────────────

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


# ── VehicleDatabases — Plate to VIN ───────────────────────────────────────

async def _vdb_plate_to_vin(plate: str, state: str) -> Optional[str]:
    """GET /license-decode/{plate}/{state} → VIN"""
    async with httpx.AsyncClient(timeout=15.0) as client:
        r = await client.get(
            f"{VDB_BASE}/license-decode/{plate.upper()}/{state.upper()}",
            headers=_vdb_headers(),
        )
        if r.status_code == 200:
            data = r.json()
            if data.get("status") == "success":
                return data.get("data", {}).get("intro", {}).get("vin")
        logger.warning(f"Plate-to-VIN failed: {r.status_code} {r.text[:150]}")
        return None


# ── VehicleDatabases — VIN Decode ─────────────────────────────────────────

async def _vdb_decode_vin(vin: str) -> dict:
    """GET /vin-decode/{vin} → vehicle info"""
    async with httpx.AsyncClient(timeout=15.0) as client:
        r = await client.get(
            f"{VDB_BASE}/vin-decode/{vin.upper()}",
            headers=_vdb_headers(),
        )
        if r.status_code != 200:
            logger.warning(f"VDB VIN decode failed ({r.status_code}), falling back to NHTSA")
            return await _nhtsa_decode_vin(vin)

        d = r.json().get("data", {})
        basic = d.get("basic", {})
        engine = d.get("engine", {})
        drivetrain = d.get("drivetrain", {})
        fuel = d.get("fuel", {})
        transmission = d.get("transmission", {})

        return {
            "vin": vin.upper(),
            "year": int(basic["year"]) if basic.get("year") else None,
            "make": basic.get("make"),
            "model": basic.get("model"),
            "trim": basic.get("trim"),
            "body_type": basic.get("body_type"),
            "doors": basic.get("doors"),
            "seating": basic.get("seating_capacity"),
            "engine_cylinders": engine.get("cylinders"),
            "engine_size": engine.get("engine_size"),
            "engine_description": engine.get("engine_description"),
            "fuel_type": fuel.get("fuel_type"),
            "secondary_fuel": fuel.get("secondary_fuel_type"),
            "drive_type": drivetrain.get("drive_type"),
            "transmission": transmission.get("transmission_style"),
            "source": "vehicledatabases",
        }


# ── VehicleDatabases — Recalls ────────────────────────────────────────────

async def _vdb_recalls(vin: str) -> list:
    """GET /vehicle-recalls/{vin}"""
    async with httpx.AsyncClient(timeout=15.0) as client:
        r = await client.get(
            f"{VDB_BASE}/vehicle-recalls/{vin.upper()}",
            headers=_vdb_headers(),
        )
        if r.status_code != 200:
            return []
        data = r.json()
        if data.get("status") != "success":
            return []
        recalls = data.get("data", {}).get("recall", [])
        return [
            {
                "campaign_id": rec.get("campaign_id"),
                "date": rec.get("recall_date"),
                "component": rec.get("component_affected"),
                "summary": rec.get("summary"),
                "consequence": rec.get("consequences"),
                "remedy": rec.get("remedy"),
            }
            for rec in recalls[:10]
        ]


# ── VehicleDatabases — Maintenance ────────────────────────────────────────

async def _vdb_maintenance(vin: str) -> dict:
    """GET /vehicle-maintenance/v4/{vin}"""
    async with httpx.AsyncClient(timeout=15.0) as client:
        r = await client.get(
            f"{VDB_BASE}/vehicle-maintenance/v4/{vin.upper()}",
            headers=_vdb_headers(),
        )
        if r.status_code != 200:
            return {}
        data = r.json()
        return data.get("data", {}) if data.get("status") == "success" else {}


# ── VehicleDatabases — Repairs ────────────────────────────────────────────

async def _vdb_repairs(vin: str) -> list:
    """GET /vehicle-repairs/v2/{vin}"""
    async with httpx.AsyncClient(timeout=15.0) as client:
        r = await client.get(
            f"{VDB_BASE}/vehicle-repairs/v2/{vin.upper()}",
            headers=_vdb_headers(),
        )
        if r.status_code != 200:
            return []
        data = r.json()
        if data.get("status") != "success":
            return []
        repairs = data.get("data", [])
        return repairs[:15] if isinstance(repairs, list) else []


# ── NHTSA fallback (free, no key needed) ──────────────────────────────────

async def _nhtsa_decode_vin(vin: str) -> dict:
    async with httpx.AsyncClient(timeout=15.0) as client:
        r = await client.get(
            f"https://vpic.nhtsa.dot.gov/api/vehicles/DecodeVinValuesExtended/{vin}?format=json"
        )
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
            "body_type": g("BodyClass"),
            "doors": g("Doors"),
            "engine_cylinders": g("EngineCylinders"),
            "engine_size": g("DisplacementL"),
            "fuel_type": g("FuelTypePrimary"),
            "drive_type": g("DriveType"),
            "transmission": g("TransmissionStyle"),
            "source": "nhtsa_fallback",
        }


# ── Full decode (used internally by transcript processor) ─────────────────

async def decode_vin_full(vin: str) -> dict:
    """VIN → vehicle + recalls + maintenance + repairs (concurrent)."""
    results = await asyncio.gather(
        _vdb_decode_vin(vin),
        _vdb_recalls(vin),
        _vdb_maintenance(vin),
        _vdb_repairs(vin),
        return_exceptions=True,
    )
    vehicle    = results[0] if not isinstance(results[0], Exception) else {}
    recalls    = results[1] if not isinstance(results[1], Exception) else []
    maintenance= results[2] if not isinstance(results[2], Exception) else {}
    repairs    = results[3] if not isinstance(results[3], Exception) else []

    return {
        "vehicle": vehicle,
        "recalls": recalls,
        "maintenance": maintenance,
        "common_repairs": repairs,
        "recall_count": len(recalls),
        "repair_count": len(repairs),
    }


# ── Endpoints ──────────────────────────────────────────────────────────────

@router.post("/vehicle/lookup-plate")
async def lookup_plate(
    image: UploadFile = File(...),
    region: str = Form(default="us"),
):
    """Photo → PlateRecognizer OCR → plate number + confidence."""
    image_bytes = await image.read()
    return await _ocr_plate(image_bytes, image.filename or "plate.jpg", region)


@router.post("/vehicle/lookup-plate-vin")
async def lookup_plate_vin(
    image: UploadFile = File(...),
    state: str = Form(default="FL"),
    region: str = Form(default="us"),
):
    """Photo → plate OCR → VDB plate-to-VIN → full decode + recalls + maintenance + repairs."""
    image_bytes = await image.read()
    plate_result = await _ocr_plate(image_bytes, image.filename or "plate.jpg", region)
    plate = plate_result["plate"]

    vin = await _vdb_plate_to_vin(plate, state)
    if not vin:
        return {
            "plate": plate,
            "confidence": plate_result["confidence"],
            "vin": None,
            "message": f"Plate {plate} detected. VIN lookup unavailable — enter VIN manually or speak it.",
        }

    full = await decode_vin_full(vin)
    return {"plate": plate, "confidence": plate_result["confidence"], **full}


@router.post("/vehicle/decode-vin")
async def decode_vin_endpoint(vin: str = Form(...)):
    """VIN → full vehicle info + recalls + maintenance + common repairs."""
    vin = vin.strip().upper()
    if len(vin) != 17:
        raise HTTPException(status_code=422, detail="VIN must be 17 characters")
    return await decode_vin_full(vin)


@router.get("/vehicle/recalls/{vin}")
async def get_recalls_by_vin(vin: str):
    """Recalls by VIN."""
    return {"vin": vin.upper(), "recalls": await _vdb_recalls(vin)}
