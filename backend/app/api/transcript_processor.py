"""
Transcript Processing Endpoint
Receives an audio file, transcribes via AssemblyAI, then uses Claude to
strip background noise/banter, extract vehicle info, and return only inspection-relevant content.
"""
import os
import json
import logging
import asyncio
import httpx
import anthropic
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session as DBSession
import uuid

from app.db.session import get_db
from app.db.models import InspectionSession, Finding, FindingCondition

router = APIRouter()
logger = logging.getLogger("workbay.transcript")

ASSEMBLYAI_API_KEY = os.getenv("ASSEMBLYAI_API_KEY")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
ASSEMBLYAI_BASE = "https://api.assemblyai.com/v2"


CLAUDE_PROMPT = """You are an automotive inspection transcript processor.

You will receive a raw audio transcript from a vehicle inspection. Your job is to do TWO things and return a JSON object.

TASK 1 — Clean the transcript:
- Extract ONLY inspection-relevant content: findings, observations, measurements, part conditions
- Remove: background noise, coworker chatter, personal talk, filler sounds (um/uh), false starts
- Preserve order and context of findings
- Return clean prose, no bullet points, no headers

TASK 2 — Extract vehicle info mentioned in the transcript:
- Look for year (4-digit number like 2019, 2022), make (Ford, Toyota, etc.), model (F-150, Camry, etc.)
- Look for mileage (e.g. "at 87,000 miles", "87k")
- Look for VIN if mentioned
- Only extract if clearly stated — do not guess

Return ONLY valid JSON in this exact format:
{
  "transcript": "<cleaned inspection narrative here>",
  "vehicle": {
    "year": <integer or null>,
    "make": "<string or null>",
    "model": "<string or null>",
    "mileage": <integer or null>,
    "vin": "<string or null>"
  }
}"""


async def _upload_to_assemblyai(audio_bytes: bytes, content_type: str) -> str:
    headers = {"authorization": ASSEMBLYAI_API_KEY, "content-type": content_type}
    async with httpx.AsyncClient(timeout=60.0) as client:
        r = await client.post(f"{ASSEMBLYAI_BASE}/upload", headers=headers, content=audio_bytes)
        if r.status_code != 200:
            raise HTTPException(status_code=500, detail=f"AssemblyAI upload failed: {r.text}")
        return r.json()["upload_url"]


async def _transcribe_assemblyai(upload_url: str) -> str:
    headers = {"authorization": ASSEMBLYAI_API_KEY, "content-type": "application/json"}
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.post(f"{ASSEMBLYAI_BASE}/transcript", headers=headers, json={
            "audio_url": upload_url,
            "speech_models": ["universal-2"],
            "punctuate": True,
            "format_text": True,
            "filter_profanity": False,
            "disfluencies": False,
        })
        if r.status_code != 200:
            raise HTTPException(status_code=500, detail=f"AssemblyAI job failed: {r.text}")
        job_id = r.json()["id"]

    async with httpx.AsyncClient(timeout=10.0) as client:
        for _ in range(120):
            await asyncio.sleep(5)
            r = await client.get(f"{ASSEMBLYAI_BASE}/transcript/{job_id}",
                                 headers={"authorization": ASSEMBLYAI_API_KEY})
            data = r.json()
            status = data.get("status")
            if status == "completed":
                return data.get("text", "")
            elif status == "error":
                raise HTTPException(status_code=500, detail=f"AssemblyAI error: {data.get('error')}")

    raise HTTPException(status_code=504, detail="Transcription timed out")


def _process_with_claude(raw_transcript: str, existing_vehicle: str) -> dict:
    """Clean transcript and extract vehicle info in one Claude call."""
    if not ANTHROPIC_API_KEY:
        return {"transcript": raw_transcript, "vehicle": {}}

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    response = client.messages.create(
        model="claude-haiku-4-5",
        max_tokens=4000,
        system=CLAUDE_PROMPT,
        messages=[{
            "role": "user",
            "content": f"Existing vehicle info (already known, only add what is missing): {existing_vehicle}\n\nRaw transcript:\n{raw_transcript}"
        }]
    )
    text = response.content[0].text.strip()
    # Strip markdown code fences if present
    if text.startswith("```"):
        text = text.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
    try:
        return json.loads(text)
    except Exception:
        return {"transcript": raw_transcript, "vehicle": {}}


@router.post("/sessions/{session_id}/process-transcript")
async def process_transcript(
    session_id: uuid.UUID,
    audio: UploadFile = File(...),
    photo_markers: str = Form(default=""),
    db: DBSession = Depends(get_db),
):
    session = db.get(InspectionSession, session_id)
    if not session:
        from app.db.models import SessionStatus
        session = InspectionSession(id=session_id, status=SessionStatus.in_progress)
        db.add(session)
        db.commit()
        db.refresh(session)

    existing_vehicle = f"{session.vehicle_year or ''} {session.vehicle_make or ''} {session.vehicle_model or ''}".strip() or "Unknown"
    logger.info(f"Processing transcript for session {session_id}, vehicle: {existing_vehicle}")

    audio_bytes = await audio.read()
    content_type = audio.content_type or "audio/aac"

    logger.info("Uploading to AssemblyAI...")
    upload_url = await _upload_to_assemblyai(audio_bytes, content_type)

    logger.info("Transcribing...")
    raw_transcript = await _transcribe_assemblyai(upload_url)
    logger.info(f"Raw transcript: {len(raw_transcript)} chars")

    if not raw_transcript:
        raise HTTPException(status_code=422, detail="No speech detected in audio")

    logger.info("Processing with Claude...")
    result = _process_with_claude(raw_transcript, existing_vehicle)

    clean_transcript = result.get("transcript", raw_transcript)
    vehicle = result.get("vehicle", {})
    logger.info(f"Clean transcript: {len(clean_transcript)} chars, extracted vehicle: {vehicle}")

    # Update session with any newly extracted vehicle info (only fill blanks)
    updated = False
    if vehicle.get("year") and not session.vehicle_year:
        session.vehicle_year = vehicle["year"]; updated = True
    if vehicle.get("make") and not session.vehicle_make:
        session.vehicle_make = vehicle["make"]; updated = True
    if vehicle.get("model") and not session.vehicle_model:
        session.vehicle_model = vehicle["model"]; updated = True
    if vehicle.get("mileage") and not session.vehicle_mileage:
        session.vehicle_mileage = vehicle["mileage"]; updated = True
    if vehicle.get("vin") and not session.vehicle_vin:
        session.vehicle_vin = vehicle["vin"]; updated = True
    if updated:
        db.commit()

    finding = Finding(
        session_id=session_id,
        checklist_item_id="transcript_mode",
        transcript=clean_transcript,
        condition=FindingCondition.na,
        structured_data={
            "mode": "transcript_only",
            "raw_length": len(raw_transcript),
            "clean_length": len(clean_transcript),
            "vehicle_extracted": vehicle,
            "photo_markers": photo_markers.split(",") if photo_markers else [],
        }
    )
    db.add(finding)
    db.commit()
    db.refresh(finding)

    # Link unattached session media to this finding
    from app.db.models import Media
    unlinked = db.query(Media).filter(
        Media.session_id == session_id,
        Media.finding_id == None
    ).all()
    for m in unlinked:
        m.finding_id = finding.id
    if unlinked:
        db.commit()

    return {
        "finding_id": str(finding.id),
        "transcript": clean_transcript,
        "raw_length": len(raw_transcript),
        "clean_length": len(clean_transcript),
        "words_removed": len(raw_transcript.split()) - len(clean_transcript.split()),
        "vehicle_extracted": vehicle,
    }
