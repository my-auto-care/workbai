import os
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from livekit.api import AccessToken, RoomAgentDispatch, RoomConfiguration, VideoGrants
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.auth import StaffActor, get_current_actor, scoped_session_or_404
from app.db.models import InspectionSession, SessionStatus, UserRole
from app.db.session import get_db

router = APIRouter()


class VoiceSessionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    session_id: uuid.UUID
    language: str = Field(default="en", min_length=2, max_length=12)
    # Sent by released mobile builds. Ignored: the LiveKit identity and display
    # name always come from the authenticated technician.
    technician_name: str | None = Field(default=None, max_length=200)


@router.post("/voice/token")
def create_voice_token(
    body: VoiceSessionRequest,
    actor: StaffActor = Depends(get_current_actor),
    db: Session = Depends(get_db),
):
    if actor.role != UserRole.technician:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the assigned technician may start voice inspection")
    inspection = scoped_session_or_404(db.get(InspectionSession, body.session_id), actor, require_assigned_technician=True)
    if actor.user_id not in {inspection.technician_id, inspection.assigned_technician_id}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Inspection is not assigned to this technician")
    if inspection.status != SessionStatus.in_progress:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Start the pending inspection before requesting voice access")
    if inspection.template_snapshot:
        # The voice agent records free-form findings, which template-driven
        # visits reject. Refuse up front instead of running a voice session
        # whose findings would all be dropped.
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This visit uses the shop's inspection checklist; record it in the inspection workspace, not voice mode",
        )

    room_name = f"inspection-{body.session_id}"
    token = (
        AccessToken(api_key=os.getenv("LIVEKIT_API_KEY"), api_secret=os.getenv("LIVEKIT_API_SECRET"))
        .with_identity(str(actor.user_id))
        .with_name(actor.name)
        .with_grants(VideoGrants(room_join=True, room=room_name, can_publish=True, can_subscribe=True))
        # The voice worker is a NAMED agent, so it must be dispatched by name.
        # Without this the worker would have to run unnamed, which puts it in
        # every room on this shared LiveKit project.
        .with_room_config(RoomConfiguration(
            agents=[RoomAgentDispatch(agent_name=os.getenv("LIVEKIT_AGENT_NAME", "workbai-inspection"))]
        ))
    )
    return {"token": token.to_jwt(), "room": room_name, "livekit_url": os.getenv("LIVEKIT_URL"), "session_id": str(body.session_id), "language": body.language}
