"""
Vehicle Lookup API
- POST /vehicle/lookup-plate  — photo → plate → VIN → full vehicle info + recalls
- POST /vehicle/decode-vin    — VIN → full vehicle info + recalls
- GET  /vehicle/recalls/{year}/{make}/{model} — recalls by ymm
"""
import os
import logging
import httpx
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from pydantic import BaseModel
from typing import Optional

router = APIRouter()
logger = logging.getLogger("workbay.vehicle")

PLATE_RECOGNIZER_TOKEN = os.getenv("PLATE_RECOGNIZER_TOKEN")
NHTSA_BASE = os.getenv("NHTSA_BASE", "https://vpic.nhtsa.dot.gov/api/vehicles")
NHTSA_RECALLS_BASE = "https://api.nhtsa.gov/recalls/recallsByVehicle"
NHTSA_COMPLAINTS_BASE = "https://api.nhtsa.gov/complaints/complaintsByVehicle"


async def _ocr_plate(image_bytes: bytes, filename: str, region: str = "us") -> dict:
    """Send plate image to PlateRecognizer, return best plate result."""
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

        data = r.json()
        results = data.get("results", [])
        if not results:
            raise HTTPException(status_code=422, detail="No license plate detected in image")

        best = results[0]
        return {
            "plate": best["plate"].upper(),
            "confidence": best.get("score", 0),
            "region": best.get("region", {}).get("code", region),
            "vehicle_hint": best.get("vehicle", {}),
        }


async def _decode_vin(vin: str) -> dict:
    """Decode VIN via NHTSA free API."""
    async with httpx.AsyncClient(timeout=15.0) as client:
        r = await client.get(
            f"{NHTSA_BASE}/DecodeVinValuesExtended/{vin}?format=json"
        )
        if r.status_code != 200:
            raise HTTPException(status_code=502, detail=f"NHTSA VIN decode failed: {r.text}")

        results = r.json().get("Results", [{}])[0]

        def _get(key):
            v = results.get(key, "")
            return v if v and v != "0" else None

        return {
            "vin": vin.upper(),
            "year": int(_get("ModelYear")) if _get("ModelYear") else None,
            "make": _get("Make"),
            "model": _get("Model"),
            "trim": _get("Trim"),
            "engine": _get("DisplacementL"),
            "engine_cylinders": _get("EngineCylinders"),
            "fuel_type": _get("FuelTypePrimary"),
            "transmission": _get("TransmissionStyle"),
            "drive_type": _get("DriveType"),
            "body_class": _get("BodyClass"),
            "doors": _get("Doors"),
            "plant_country": _get("PlantCountry"),
            "error": _get("ErrorText"),
        }


async def _get_recalls(year: int, make: str, model: str) -> list:
    """Get NHTSA recalls for a vehicle."""
    async with httpx.AsyncClient(timeout=15.0) as client:
        r = await client.get(
            NHTSA_RECALLS_BASE,
            params={"make": make, "model": model, "modelYear": year},
        )
        if r.status_code != 200:
            return []
        results = r.json().get("results", [])
        return [
            {
                "campaign": rec.get("NHTSACampaignNumber"),
                "date": rec.get("ReportReceivedDate"),
                "component": rec.get("Component"),
                "summary": rec.get("Summary"),
                "consequence": rec.get("Consequence"),
                "remedy": rec.get("Remedy"),
            }
            for rec in results[:10]  # cap at 10
        ]


async def _get_complaints(year: int, make: str, model: str) -> list:
    """Get top NHTSA complaints for a vehicle."""
    async with httpx.AsyncClient(timeout=15.0) as client:
        r = await client.get(
            NHTSA_COMPLAINTS_BASE,
            params={"make": make, "model": model, "modelYear": year},
        )
        if r.status_code != 200:
            return []
        results = r.json().get("results", [])
        # Sort by number of complaints descending
        results.sort(key=lambda x: x.get("numberOfComplaints", 0), reverse=True)
        return [
            {
                "component": rec.get("components"),
                "complaints": rec.get("numberOfComplaints"),
                "summary": rec.get("summary"),
                "date": rec.get("dateOfIncident"),
            }
            for rec in results[:10]
        ]


async def _plate_to_vin(plate: str, state: str) -> Optional[str]:
    """
    Plate → VIN lookup.
    NHTSA doesn't offer plate lookup — would need a paid service (Marketcheck etc).
    For now we return None and surface the plate so the tech can confirm.
    Future: integrate Marketcheck or similar.
    """
    return None


# ── Endpoints ──────────────────────────────────────────────────────────────

@router.post("/vehicle/lookup-plate")
async def lookup_plate(
    image: UploadFile = File(...),
    region: str = Form(default="us"),
    session_id: Optional[str] = Form(default=None),
):
    """
    Upload a photo of a license plate.
    Returns plate number + any vehicle info PlateRecognizer can infer.
    Does NOT auto-decode VIN (requires paid plate→VIN service).
    Tech can confirm plate and then VIN is entered or spoken.
    """
    image_bytes = await image.read()
    plate_result = await _ocr_plate(image_bytes, image.filename or "plate.jpg", region)

    return {
        "plate": plate_result["plate"],
        "confidence": plate_result["confidence"],
        "region": plate_result["region"],
        "vehicle_hint": plate_result["vehicle_hint"],
        "vin": None,  # requires paid plate→VIN lookup
        "message": f"Plate detected: {plate_result['plate']}. Please confirm and enter VIN or speak it to decode full vehicle info.",
    }


@router.post("/vehicle/decode-vin")
async def decode_vin_endpoint(vin: str = Form(...)):
    """Decode a VIN and return full vehicle info + recalls + top complaints."""
    if len(vin) != 17:
        raise HTTPException(status_code=422, detail="VIN must be 17 characters")

    vehicle = await _decode_vin(vin)

    recalls = []
    complaints = []
    if vehicle.get("year") and vehicle.get("make") and vehicle.get("model"):
        recalls, complaints = await _get_recalls_and_complaints(
            vehicle["year"], vehicle["make"], vehicle["model"]
        )

    return {
        "vehicle": vehicle,
        "recalls": recalls,
        "complaints": complaints,
        "recall_count": len(recalls),
        "complaint_count": len(complaints),
    }


async def _get_recalls_and_complaints(year, make, model):
    import asyncio
    recalls, complaints = await asyncio.gather(
        _get_recalls(year, make, model),
        _get_complaints(year, make, model),
    )
    return recalls, complaints


@router.get("/vehicle/recalls/{year}/{make}/{model}")
async def get_recalls(year: int, make: str, model: str):
    """Get NHTSA recalls + complaints for a vehicle."""
    recalls, complaints = await _get_recalls_and_complaints(year, make, model)
    return {
        "year": year,
        "make": make,
        "model": model,
        "recalls": recalls,
        "complaints": complaints,
        "recall_count": len(recalls),
        "complaint_count": len(complaints),
    }
