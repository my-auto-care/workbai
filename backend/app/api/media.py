import os
import re
import uuid
from typing import Optional

import boto3
from botocore.config import Config
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy.orm import Session

from app.auth import StaffActor, get_current_actor, scoped_session_or_404
from app.db.models import InspectionSession, Media, MediaType, UserRole
from app.db.session import get_db

router = APIRouter()
BUCKET = os.getenv("DO_SPACES_BUCKET_DATA", "workbay-data")
_FILENAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,119}$")


def get_spaces_client():
    return boto3.client(
        "s3",
        region_name=os.getenv("DO_SPACES_REGION", "nyc3"),
        endpoint_url=os.getenv("DO_SPACES_ENDPOINT", "https://nyc3.digitaloceanspaces.com"),
        aws_access_key_id=os.getenv("DO_SPACES_ACCESS_KEY"),
        aws_secret_access_key=os.getenv("DO_SPACES_SECRET_KEY"),
        config=Config(signature_version="s3v4"),
    )


def presigned_read_url(s3_key: str, expires: int = 3600) -> str:
    return get_spaces_client().generate_presigned_url(
        "get_object", Params={"Bucket": BUCKET, "Key": s3_key}, ExpiresIn=expires
    )


class UploadUrlRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    session_id: uuid.UUID
    filename: str = Field(min_length=1, max_length=120)
    media_type: MediaType = MediaType.photo
    content_type: str = Field(default="image/jpeg", max_length=100)

    @field_validator("filename")
    @classmethod
    def filename_is_safe(cls, value: str) -> str:
        if not _FILENAME.fullmatch(value):
            raise ValueError("Filename must contain only letters, numbers, dot, dash, or underscore")
        return value


class MediaAttach(BaseModel):
    model_config = ConfigDict(extra="forbid")
    finding_id: Optional[uuid.UUID] = None
    session_id: uuid.UUID
    media_type: MediaType = MediaType.photo
    s3_key: str = Field(min_length=1, max_length=512)


def _media_actor(actor: StaffActor) -> None:
    if actor.role not in {UserRole.technician, UserRole.advisor, UserRole.admin}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient staff role")


def _operator_session(db: Session, session_id: uuid.UUID, actor: StaffActor) -> InspectionSession:
    _media_actor(actor)
    inspection = scoped_session_or_404(
        db.get(InspectionSession, session_id), actor, require_assigned_technician=True
    )
    if actor.role == UserRole.technician and actor.user_id not in {inspection.technician_id, inspection.assigned_technician_id}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Inspection is not assigned to this technician")
    return inspection


@router.post("/media/upload-url")
def get_upload_url(
    body: UploadUrlRequest,
    actor: StaffActor = Depends(get_current_actor),
    db: Session = Depends(get_db),
):
    _operator_session(db, body.session_id, actor)
    media_type = body.media_type.value
    key = f"sessions/{body.session_id}/{media_type}/{uuid.uuid4()}_{body.filename}"
    url = get_spaces_client().generate_presigned_url(
        "put_object",
        Params={"Bucket": BUCKET, "Key": key, "ContentType": body.content_type},
        ExpiresIn=900,
    )
    return {"upload_url": url, "s3_key": key}


@router.post("/media/{media_id}/attach", status_code=status.HTTP_201_CREATED)
def attach_media(
    media_id: uuid.UUID,
    body: MediaAttach,
    actor: StaffActor = Depends(get_current_actor),
    db: Session = Depends(get_db),
):
    inspection = _operator_session(db, body.session_id, actor)
    expected_prefix = f"sessions/{inspection.id}/{body.media_type.value}/"
    if not body.s3_key.startswith(expected_prefix):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Media key does not match the inspection upload scope")
    if db.get(Media, media_id):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Media is already attached")
    if body.finding_id and not any(finding.id == body.finding_id for finding in inspection.findings):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Finding is not part of this inspection")
    media = Media(id=media_id, session_id=inspection.id, finding_id=body.finding_id, media_type=body.media_type, s3_key=body.s3_key)
    db.add(media)
    db.commit()
    db.refresh(media)
    return {"id": str(media.id), "s3_key": media.s3_key, "media_type": media.media_type.value, "url": presigned_read_url(media.s3_key)}


@router.get("/media/{media_id}/url")
def get_media_url(
    media_id: uuid.UUID,
    actor: StaffActor = Depends(get_current_actor),
    db: Session = Depends(get_db),
):
    media = db.get(Media, media_id)
    if not media:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Media not found")
    _operator_session(db, media.session_id, actor)
    return {"id": str(media.id), "url": presigned_read_url(media.s3_key)}
