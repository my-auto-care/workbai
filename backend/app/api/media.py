from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
import boto3, os, uuid
from botocore.config import Config

from app.db.session import get_db
from app.db.models import Media, MediaType

router = APIRouter()

def get_spaces_client():
    return boto3.client(
        "s3",
        region_name=os.getenv("DO_SPACES_REGION", "nyc3"),
        endpoint_url=os.getenv("DO_SPACES_ENDPOINT", "https://nyc3.digitaloceanspaces.com"),
        aws_access_key_id=os.getenv("DO_SPACES_ACCESS_KEY"),
        aws_secret_access_key=os.getenv("DO_SPACES_SECRET_KEY"),
        config=Config(signature_version="s3v4")
    )

class UploadUrlRequest(BaseModel):
    session_id: uuid.UUID
    filename: str
    media_type: MediaType = MediaType.photo
    content_type: str = "image/jpeg"

class MediaAttach(BaseModel):
    finding_id: Optional[uuid.UUID] = None
    session_id: uuid.UUID
    media_type: MediaType = MediaType.photo
    s3_key: str

@router.post("/media/upload-url")
def get_upload_url(body: UploadUrlRequest):
    client = get_spaces_client()
    bucket = os.getenv("DO_SPACES_BUCKET_DATA", "workbay-data")
    s3_key = f"sessions/{body.session_id}/{body.media_type}/{uuid.uuid4()}_{body.filename}"
    url = client.generate_presigned_url(
        "put_object",
        Params={"Bucket": bucket, "Key": s3_key, "ContentType": body.content_type},
        ExpiresIn=900
    )
    return {"upload_url": url, "s3_key": s3_key}

@router.post("/media/{media_id}/attach", status_code=201)
def attach_media(media_id: uuid.UUID, body: MediaAttach, db: Session = Depends(get_db)):
    media = Media(
        id=media_id,
        session_id=body.session_id,
        finding_id=body.finding_id,
        media_type=body.media_type,
        s3_key=body.s3_key
    )
    db.add(media)
    db.commit()
    db.refresh(media)
    return {"id": str(media.id), "s3_key": media.s3_key, "media_type": media.media_type}
