"""
Vehicle Lookup API — VehicleDatabases.com + PlateRecognizer
Endpoints:
  POST /vehicle/lookup-plate       — photo → PlateRecognizer OCR → plate number
  POST /vehicle/lookup-plate-vin   — photo + state → plate → VDB plate-to-VIN → full decode
  POST /vehicle/ocr-vin            — photo of VIN tag → VDB VIN OCR → full decode
  POST /vehicle/decode-vin         — VIN → full decode + recalls + maintenance + repairs + warranty
  GET  /vehicle/recalls/{vin}      — recalls by VIN
  POST /vehicle/identify-plate     — check-in: plate photo or typed plate + state → VIN → year/make/model (lean)
"""
import os
import re
import logging
import asyncio
import httpx
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from typing import Optional
from app.auth import get_current_actor

router = APIRouter(dependencies=[Depends(get_current_actor)])
logger = logging.getLogger("workbay.vehicle")

PLATE_RECOGNIZER_TOKEN = os.getenv("PLATE_RECOGNIZER_TOKEN")
VDB_KEY = os.getenv("VEHICLE_DATABASES_KEY")
VDB_BASE = "https://api.vehicledatabases.com"

def _h():
    return {"x-authkey": VDB_KEY} if VDB_KEY else {}


# ── PlateRecognizer — Plate OCR ────────────────────────────────────────────

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


# ── VehicleDatabases — VIN OCR (photo of VIN tag) ─────────────────────────

async def _vdb_ocr_vin(image_bytes: bytes, filename: str) -> Optional[str]:
    """POST /vin-ocr — image → VIN string"""
    async with httpx.AsyncClient(timeout=15.0) as client:
        r = await client.post(
            f"{VDB_BASE}/vin-ocr",
            headers=_h(),
            files=[("file", (filename, image_bytes, "image/jpeg"))],
        )
        if r.status_code == 200 and r.json().get("status") == "success":
            return r.json().get("data", {}).get("vin")
        logger.warning(f"VIN OCR failed: {r.status_code} {r.text[:100]}")
        return None


# ── VehicleDatabases — Plate to VIN ───────────────────────────────────────

async def _vdb_plate_to_vin(plate: str, state: str) -> Optional[str]:
    """GET /license-decode/{plate}/{state} → VIN"""
    async with httpx.AsyncClient(timeout=15.0) as client:
        r = await client.get(
            f"{VDB_BASE}/license-decode/{plate.upper()}/{state.upper()}",
            headers=_h(),
        )
        if r.status_code == 200 and r.json().get("status") == "success":
            return r.json().get("data", {}).get("intro", {}).get("vin")
        logger.warning(f"Plate-to-VIN failed: {r.status_code} {r.text[:100]}")
        return None


# ── VehicleDatabases — Advanced VIN Decode ────────────────────────────────

async def _vdb_decode_vin(vin: str) -> dict:
    """GET /advanced-vin-decode/v2/{vin} — full vehicle specs"""
    async with httpx.AsyncClient(timeout=15.0) as client:
        r = await client.get(
            f"{VDB_BASE}/advanced-vin-decode/v2/{vin.upper()}",
            headers=_h(),
        )
        if r.status_code != 200 or r.json().get("status") != "success":
            logger.warning(f"Advanced VIN decode failed ({r.status_code}), falling back to NHTSA")
            return await _nhtsa_decode_vin(vin)

        d = r.json().get("data", {})
        engine = d.get("engine", {})
        fuel = d.get("fuel", {})
        drive = d.get("drivetrain", {})
        trans = d.get("transmission", {})
        vehicle = d.get("vehicle", {})
        weights = d.get("weights", {})
        tires = d.get("wheels_and_tires", {})

        def _w(obj, key):
            """Extract first value from weight/dimension array."""
            v = obj.get(key, [])
            return v[0].get("value") if isinstance(v, list) and v else None

        return {
            "vin": vin.upper(),
            "year": d.get("year"),
            "make": d.get("make"),
            "model": d.get("model"),
            "trim": d.get("trim"),
            "style": d.get("style"),
            "body_type": vehicle.get("body_type"),
            "doors": vehicle.get("doors"),
            "engine_cylinders": engine.get("cylinders"),
            "engine_size": engine.get("engine_size"),
            "engine_description": engine.get("engine_description"),
            "horsepower": engine.get("horsepower"),
            "torque": engine.get("torque"),
            "fuel_type": fuel.get("fuel_type_1") or fuel.get("fuel_type"),
            "secondary_fuel": fuel.get("fuel_type_2") or fuel.get("secondary_fuel_type"),
            "mpg_city": fuel.get("city_mileage"),
            "mpg_highway": fuel.get("highway_mileage"),
            "drive_type": drive.get("driven_wheels") or drive.get("drive_type"),
            "transmission": trans.get("transmission_type") or trans.get("transmission_style"),
            "transmission_speeds": trans.get("number_of_speeds"),
            "curb_weight_lbs": _w(weights, "curb_weight"),
            "towing_capacity_lbs": _w(weights, "max_towing_capacity"),
            "front_tire": tires.get("front_tire_size"),
            "rear_tire": tires.get("rear_tire_size"),
            "msrp": d.get("price", {}).get("base_msrp"),
            "source": "vehicledatabases_advanced",
        }


# ── VehicleDatabases — Recalls ────────────────────────────────────────────

async def _vdb_recalls(vin: str) -> list:
    """GET /vehicle-recalls/{vin}"""
    async with httpx.AsyncClient(timeout=15.0) as client:
        r = await client.get(f"{VDB_BASE}/vehicle-recalls/{vin.upper()}", headers=_h())
        if r.status_code != 200 or r.json().get("status") != "success":
            return []
        recalls = r.json().get("data", {}).get("recall", [])
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
        r = await client.get(f"{VDB_BASE}/vehicle-maintenance/v4/{vin.upper()}", headers=_h())
        if r.status_code != 200 or r.json().get("status") != "success":
            return {}
        return r.json().get("data", {})


# ── VehicleDatabases — Repairs ────────────────────────────────────────────

async def _vdb_repairs(vin: str) -> list:
    """GET /vehicle-repairs/v2/{vin}"""
    async with httpx.AsyncClient(timeout=15.0) as client:
        r = await client.get(f"{VDB_BASE}/vehicle-repairs/v2/{vin.upper()}", headers=_h())
        if r.status_code != 200 or r.json().get("status") != "success":
            return []
        data = r.json().get("data", [])
        return data[:15] if isinstance(data, list) else []


# ── VehicleDatabases — Warranty ───────────────────────────────────────────

async def _vdb_warranty(vin: str) -> dict:
    """GET /vehicle-warranty/{vin}"""
    async with httpx.AsyncClient(timeout=15.0) as client:
        r = await client.get(f"{VDB_BASE}/vehicle-warranty/{vin.upper()}", headers=_h())
        if r.status_code != 200 or r.json().get("status") != "success":
            return {}
        return r.json().get("data", {})


# ── NHTSA fallback ────────────────────────────────────────────────────────

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


# ── Full decode (used by transcript processor) ────────────────────────────

async def decode_vin_full(vin: str) -> dict:
    """VIN → vehicle + recalls + maintenance + repairs + warranty (concurrent)."""
    results = await asyncio.gather(
        _vdb_decode_vin(vin),
        _vdb_recalls(vin),
        _vdb_maintenance(vin),
        _vdb_repairs(vin),
        _vdb_warranty(vin),
        return_exceptions=True,
    )
    vehicle     = results[0] if not isinstance(results[0], Exception) else {}
    recalls     = results[1] if not isinstance(results[1], Exception) else []
    maintenance = results[2] if not isinstance(results[2], Exception) else {}
    repairs     = results[3] if not isinstance(results[3], Exception) else []
    warranty    = results[4] if not isinstance(results[4], Exception) else {}

    return {
        "vehicle": vehicle,
        "recalls": recalls,
        "maintenance": maintenance,
        "common_repairs": repairs,
        "warranty": warranty,
        "recall_count": len(recalls),
        "repair_count": len(repairs),
    }


# ── Endpoints ──────────────────────────────────────────────────────────────

@router.post("/vehicle/lookup-plate")
async def lookup_plate(
    image: UploadFile = File(...),
    region: str = Form(default="us"),
):
    """Photo of license plate → plate number + confidence."""
    image_bytes = await image.read()
    return await _ocr_plate(image_bytes, image.filename or "plate.jpg", region)


@router.post("/vehicle/lookup-plate-vin")
async def lookup_plate_vin(
    image: UploadFile = File(...),
    state: str = Form(default="FL"),
    region: str = Form(default="us"),
):
    """Photo of plate → OCR → plate-to-VIN → full decode + recalls + maintenance + repairs + warranty."""
    image_bytes = await image.read()
    plate_result = await _ocr_plate(image_bytes, image.filename or "plate.jpg", region)
    plate = plate_result["plate"]

    vin = await _vdb_plate_to_vin(plate, state)
    if not vin:
        return {
            "plate": plate,
            "confidence": plate_result["confidence"],
            "vin": None,
            "message": f"Plate {plate} detected. Could not resolve VIN — enter or speak VIN to continue.",
        }

    full = await decode_vin_full(vin)
    return {"plate": plate, "confidence": plate_result["confidence"], **full}


# ── Check-in: identify a vehicle from its plate (lean) ────────────────────
# Chad, 2026-10-22: "a license plate scan tied to the vehicle database api". One plate read (skipped for a typed plate),
# one plate-to-VIN, one VIN decode: the recalls/maintenance/repairs/warranty calls of /vehicle/lookup-plate-vin are paid
# calls check-in does not need. The photo is never stored, and provider error text never reaches the client.

US_STATES = frozenset("AL AK AZ AR CA CO CT DE DC FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO MT NE NV NH NJ NM NY "
                      "NC ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY".split())
PLATE_RE = re.compile(r"^[A-Z0-9]{2,8}$")
MAX_PLATE_IMAGE_BYTES = 8 * 1024 * 1024


def normalize_plate(raw: Optional[str]) -> str:
    """A typed plate as the DMV prints it: letters and digits only, upper case (spaces and dashes dropped)."""
    return re.sub(r"[^A-Za-z0-9]", "", raw or "").upper()


@router.post("/vehicle/identify-plate")
async def identify_plate(
    state: str = Form(...),
    image: Optional[UploadFile] = File(default=None),
    plate: Optional[str] = Form(default=None),
):
    """A plate photo (or the plate typed in) and its state → plate, VIN, year, make, model, trim. Staff only."""
    st = (state or "").strip().upper()
    if st not in US_STATES:
        raise HTTPException(status_code=422, detail="Choose the state on the plate.")
    if not VDB_KEY:
        raise HTTPException(status_code=503, detail="The vehicle database is not configured.")
    confidence = None
    if image is not None and (image.filename or image.size):
        if image.content_type and not image.content_type.startswith("image/"):
            raise HTTPException(status_code=415, detail="Send a photo of the plate.")
        data = await image.read(MAX_PLATE_IMAGE_BYTES + 1)
        if len(data) > MAX_PLATE_IMAGE_BYTES:
            raise HTTPException(status_code=413, detail="That photo is too large. Try again closer to the plate.")
        try:
            read = await _ocr_plate(data, image.filename or "plate.jpg", f"us-{st.lower()}")
        except HTTPException as exc:
            if exc.status_code == 422:
                raise HTTPException(status_code=422, detail="No plate found in that photo. Try again, or type the plate.") from exc
            logger.warning("Plate read failed: %s", exc.status_code)
            raise HTTPException(status_code=502, detail="The plate reader is unavailable. Type the plate instead.") from exc
        found = normalize_plate(read["plate"])
        confidence = read.get("confidence")
    else:
        found = normalize_plate(plate)
    if not PLATE_RE.match(found):
        raise HTTPException(status_code=422, detail="Type the plate as letters and numbers (2 to 8).")
    try:
        vin = await _vdb_plate_to_vin(found, st)
    except httpx.HTTPError as exc:
        logger.warning("Plate-to-VIN request failed: %s", type(exc).__name__)
        vin = None
    if not vin:
        return {"plate": found, "state": st, "confidence": confidence, "vin": None,
                "message": f"Plate {found} ({st}) wasn't found in the vehicle database. Enter the vehicle by hand."}
    vehicle = await _vdb_decode_vin(vin)
    return {"plate": found, "state": st, "confidence": confidence, "vin": vin.upper(),
            "year": vehicle.get("year"), "make": vehicle.get("make"), "model": vehicle.get("model"),
            "trim": vehicle.get("trim"), "engine": vehicle.get("engine_description"), "source": vehicle.get("source")}


@router.post("/vehicle/ocr-vin")
async def ocr_vin(
    image: UploadFile = File(...),
):
    """Photo of VIN tag/sticker → VIN OCR → full decode + recalls + maintenance + repairs + warranty."""
    image_bytes = await image.read()
    vin = await _vdb_ocr_vin(image_bytes, image.filename or "vin.jpg")
    if not vin:
        raise HTTPException(status_code=422, detail="Could not read VIN from image. Ensure VIN tag is clearly visible.")

    full = await decode_vin_full(vin)
    return {"vin_ocr": vin, **full}


@router.post("/vehicle/decode-vin")
async def decode_vin_endpoint(vin: str = Form(...)):
    """VIN → full vehicle info + recalls + maintenance + common repairs + warranty."""
    vin = vin.strip().upper()
    if len(vin) != 17:
        raise HTTPException(status_code=422, detail="VIN must be 17 characters")
    return await decode_vin_full(vin)


@router.get("/vehicle/recalls/{vin}")
async def get_recalls_by_vin(vin: str):
    """Recalls by VIN."""
    return {"vin": vin.upper(), "recalls": await _vdb_recalls(vin)}
