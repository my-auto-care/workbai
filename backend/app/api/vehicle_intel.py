"""
Vehicle Intelligence API
Calls Claude to generate vehicle-specific inspection priorities based on year/make/model/mileage.
"""
import os
import json
import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session as DBSession
from pydantic import BaseModel
from typing import Optional
import uuid
import anthropic

from app.db.session import get_db
from app.db.models import InspectionSession

router = APIRouter()
logger = logging.getLogger("workbay.vehicle_intel")

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")


VEHICLE_INTEL_PROMPT = """You are an expert automotive technician with 30 years of experience and deep knowledge of vehicle-specific failure patterns, TSBs (Technical Service Bulletins), and common issues by year/make/model/mileage.

Given a vehicle's year, make, model, and mileage, return a JSON object with:
1. known_issues: Top 5-8 known failure areas specific to this vehicle (with priority: critical/high/medium)
2. mileage_alerts: Items that are due or overdue based on mileage (timing belt, transmission fluid, spark plugs, etc.)
3. priority_questions: Specific questions the inspector should ask/check for this exact vehicle
4. tsb_notes: Any notable TSBs or recalls the technician should be aware of
5. inspection_focus: A short paragraph telling the inspector what to pay special attention to

Be SPECIFIC to the vehicle. Do not give generic advice. Reference actual known issues for this year/make/model.

Respond ONLY with valid JSON. No markdown, no explanation.

Example format:
{
  "known_issues": [
    {"area": "Timing chain tensioner", "priority": "critical", "description": "2011-2013 Ecoboost engines known for timing chain stretch at high mileage", "what_to_check": "Listen for rattle on cold start, check for codes P0016/P0017"},
    ...
  ],
  "mileage_alerts": [
    {"item": "Spark plugs", "status": "overdue", "recommended_interval": "100k miles", "notes": "Ford spec iridium plugs, check for carbon fouling"},
    ...
  ],
  "priority_questions": [
    "Has the customer noticed any cold start rattle?",
    "Any rough idle or hesitation under load?",
    ...
  ],
  "tsb_notes": [
    "TSB 14-0194: Transmission shudder on light throttle — check for updated fluid",
    ...
  ],
  "inspection_focus": "This is a high-mileage Ecoboost. Prioritize the timing system, turbo oil lines, and intercooler boots. The 6F35 transmission in this vehicle is known for shudder and delayed engagement at higher mileages."
}"""


class VehicleIntelRequest(BaseModel):
    year: int
    make: str
    model: str
    mileage: Optional[int] = None
    customer_concern: Optional[str] = None


@router.post("/vehicle-intelligence")
async def get_vehicle_intelligence(body: VehicleIntelRequest):
    """Generate AI-powered vehicle-specific inspection intelligence."""
    if not ANTHROPIC_API_KEY:
        raise HTTPException(status_code=500, detail="Anthropic API key not configured")

    mileage_str = f"{body.mileage:,} miles" if body.mileage else "unknown mileage"
    concern_str = f"\nCustomer concern: {body.customer_concern}" if body.customer_concern else ""

    user_message = f"Vehicle: {body.year} {body.make} {body.model}, {mileage_str}{concern_str}"

    try:
        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        response = client.messages.create(
            model="claude-sonnet-4-5",
            max_tokens=2000,
            system=VEHICLE_INTEL_PROMPT,
            messages=[{"role": "user", "content": user_message}]
        )
        raw = response.content[0].text.strip()
        intel = json.loads(raw)
        intel["vehicle"] = {
            "year": body.year,
            "make": body.make,
            "model": body.model,
            "mileage": body.mileage,
        }
        logger.info(f"Vehicle intel generated for {body.year} {body.make} {body.model}")
        return intel
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse vehicle intel JSON: {e}")
        raise HTTPException(status_code=500, detail="Failed to parse AI response")
    except Exception as e:
        logger.error(f"Vehicle intel error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sessions/{session_id}/vehicle-intelligence")
async def get_session_vehicle_intelligence(session_id: uuid.UUID, db: DBSession = Depends(get_db)):
    """Generate vehicle intelligence for an existing session using its stored vehicle data."""
    session = db.get(InspectionSession, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    if not session.vehicle_year or not session.vehicle_make or not session.vehicle_model:
        raise HTTPException(status_code=400, detail="Session has no vehicle information")

    req = VehicleIntelRequest(
        year=int(session.vehicle_year),
        make=session.vehicle_make,
        model=session.vehicle_model,
        mileage=session.vehicle_mileage if hasattr(session, 'vehicle_mileage') else None,
        customer_concern=session.customer_concern,
    )
    return await get_vehicle_intelligence(req)
