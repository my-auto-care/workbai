"""
Transcript Processing Endpoint
Receives an audio file, transcribes via AssemblyAI, then uses Claude to
strip background noise/banter and return only inspection-relevant content.
"""
import os
import logging
import httpx
import time
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


CLEANUP_PROMPT = """You are an automotive inspection transcript cleaner.

You will receive a raw audio transcript from a vehicle inspection. The technician was recording the entire time — including walking around, background shop noise, conversations with coworkers, personal talk, and silence fillers.

Your job:
1. Extract ONLY inspection-relevant content — findings, observations, measurements, part conditions
2. Remove ALL of the following:
   - Background noise transcriptions (clanging, music, radio, etc.)
   - Conversations with coworkers unrelated to the inspection
   - Personal banter, jokes, phone calls
   - Filler sounds (um, uh, hmm) unless part of a finding
   - Repeated false starts
   - Anything clearly not about the vehicle being inspected
3. Preserve the order and context of findings
4. Keep photo markers exactly as they appear: [PHOTO]
5. Return clean prose — no bullet points, no headers, just the cleaned inspection narrative

If a sentence is ambiguous (could be inspection-related), keep it.
Return ONLY the cleaned transcript text. No explanation, no preamble."""


async def _upload_to_assemblyai(audio_bytes: bytes, content_type: str) -> str:
    """Upload audio to AssemblyAI and return the upload URL."""
    headers = {"authorization": ASSEMBLYAI_API_KEY, "content-type": content_type}
    async with httpx.AsyncClient(timeout=60.0) as client:
        r = await client.post(f"{ASSEMBLYAI_BASE}/upload", headers=headers, content=audio_bytes)
        if r.status_code != 200:
            raise HTTPException(status_code=500, detail=f"AssemblyAI upload failed: {r.text}")
        return r.json()["upload_url"]


async def _transcribe_assemblyai(upload_url: str) -> str:
    """Submit transcription job and poll until complete."""
    headers = {"authorization": ASSEMBLYAI_API_KEY, "content-type": "application/json"}
    async with httpx.AsyncClient(timeout=30.0) as client:
        # Submit job
        r = await client.post(f"{ASSEMBLYAI_BASE}/transcript", headers=headers, json={
            "audio_url": upload_url,
            "speech_models": ["universal-2"],
            "punctuate": True,
            "format_text": True,
            "filter_profanity": False,
            "disfluencies": False,  # strip um/uh automatically
        })
        if r.status_code != 200:
            raise HTTPException(status_code=500, detail=f"AssemblyAI job failed: {r.text}")
        job_id = r.json()["id"]

    # Poll for completion
    async with httpx.AsyncClient(timeout=10.0) as client:
        for _ in range(120):  # max 10 minutes
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


def _clean_with_claude(raw_transcript: str, vehicle_info: str) -> str:
    """Use Claude to strip irrelevant content from the transcript."""
    if not ANTHROPIC_API_KEY:
        return raw_transcript  # fallback: return raw if no key

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    response = client.messages.create(
        model="claude-haiku-4-5",  # fast + cheap for cleanup task
        max_tokens=4000,
        system=CLEANUP_PROMPT,
        messages=[{
            "role": "user",
            "content": f"Vehicle: {vehicle_info}\n\nRaw transcript:\n{raw_transcript}"
        }]
    )
    return response.content[0].text.strip()


import asyncio

@router.post("/sessions/{session_id}/process-transcript")
async def process_transcript(
    session_id: uuid.UUID,
    audio: UploadFile = File(...),
    photo_markers: str = Form(default=""),  # comma-separated timestamps where photos were taken
    db: DBSession = Depends(get_db),
):
    """
    Receive audio recording from transcript mode inspection.
    Transcribe via AssemblyAI, clean via Claude, save as finding.
    """
    session = db.get(InspectionSession, session_id)
    if not session:
        # Session not found — create a minimal one so transcript can be saved
        from app.db.models import SessionStatus
        session = InspectionSession(
            id=session_id,
            status=SessionStatus.in_progress,
        )
        db.add(session)
        db.commit()
        db.refresh(session)

    vehicle_info = f"{session.vehicle_year or ''} {session.vehicle_make or ''} {session.vehicle_model or ''}".strip() or "Unknown vehicle"

    logger.info(f"Processing transcript audio for session {session_id}, vehicle: {vehicle_info}")

    # Read audio
    audio_bytes = await audio.read()
    content_type = audio.content_type or "audio/m4a"

    # Step 1: Upload to AssemblyAI
    logger.info("Uploading audio to AssemblyAI...")
    upload_url = await _upload_to_assemblyai(audio_bytes, content_type)

    # Step 2: Transcribe
    logger.info("Transcribing...")
    raw_transcript = await _transcribe_assemblyai(upload_url)
    logger.info(f"Raw transcript: {len(raw_transcript)} chars")

    if not raw_transcript:
        raise HTTPException(status_code=422, detail="No speech detected in audio")

    # Step 3: Clean with Claude
    logger.info("Cleaning transcript with Claude...")
    clean_transcript = _clean_with_claude(raw_transcript, vehicle_info)
    logger.info(f"Clean transcript: {len(clean_transcript)} chars")

    # Step 4: Save as finding
    finding = Finding(
        session_id=session_id,
        checklist_item_id="transcript_mode",
        transcript=clean_transcript,
        condition=FindingCondition.na,
        structured_data={
            "mode": "transcript_only",
            "raw_length": len(raw_transcript),
            "clean_length": len(clean_transcript),
            "vehicle": vehicle_info,
            "photo_markers": photo_markers.split(",") if photo_markers else [],
        }
    )
    db.add(finding)
    db.commit()
    db.refresh(finding)

    # Link any unattached session media to this finding
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
    }
