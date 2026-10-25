import os
import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from livekit.api import AccessToken, VideoGrants, RoomConfiguration, RoomAgentDispatch

from app.db.session import get_db
from app.db.models import InspectionSession

router = APIRouter()

class VoiceSessionRequest(BaseModel):
    session_id: uuid.UUID
    technician_name: str
    language: str = "en"

@router.post("/voice/token")
def create_voice_token(body: VoiceSessionRequest, db: Session = Depends(get_db)):
    session = db.get(InspectionSession, body.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    room_name = f"inspection-{body.session_id}"

    token = (
        AccessToken(
            api_key=os.getenv("LIVEKIT_API_KEY"),
            api_secret=os.getenv("LIVEKIT_API_SECRET")
        )
        .with_identity(body.technician_name)
        .with_name(body.technician_name)
        .with_grants(VideoGrants(
            room_join=True,
            room=room_name,
            can_publish=True,
            can_subscribe=True,
        ))
        # The voice worker is a NAMED agent, so it must be dispatched by name.
        # Without this the worker would have to run unnamed, which puts it in
        # every room on this shared LiveKit project.
        .with_room_config(RoomConfiguration(
            agents=[RoomAgentDispatch(
                agent_name=os.getenv("LIVEKIT_AGENT_NAME", "workbai-inspection")
            )]
        ))
    )

    return {
        "token": token.to_jwt(),
        "room": room_name,
        "livekit_url": os.getenv("LIVEKIT_URL"),
        "session_id": str(body.session_id),
        "language": body.language
    }
