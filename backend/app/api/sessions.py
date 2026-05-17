from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import select
from typing import Optional
from datetime import datetime
from pydantic import BaseModel
import uuid

from app.db.session import get_db
from app.db.models import (
    InspectionSession, Finding, Media, SessionStatus, FindingCondition
)

router = APIRouter()

class SessionCreate(BaseModel):
    shop_id: uuid.UUID
    technician_id: uuid.UUID
    vehicle_id: uuid.UUID
    checklist_template_id: Optional[uuid.UUID] = None
    customer_concern: Optional[str] = None

class FindingCreate(BaseModel):
    checklist_item_id: Optional[str] = None
    transcript: Optional[str] = None
    structured_data: Optional[dict] = {}
    condition: Optional[FindingCondition] = FindingCondition.na

class FindingUpdate(BaseModel):
    transcript: Optional[str] = None
    structured_data: Optional[dict] = None
    condition: Optional[FindingCondition] = None

@router.post("/sessions", status_code=201)
def create_session(body: SessionCreate, db: Session = Depends(get_db)):
    session = InspectionSession(
        shop_id=body.shop_id,
        technician_id=body.technician_id,
        vehicle_id=body.vehicle_id,
        checklist_template_id=body.checklist_template_id,
        customer_concern=body.customer_concern,
        status=SessionStatus.in_progress,
        started_at=datetime.utcnow()
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return {"id": str(session.id), "status": session.status, "started_at": session.started_at}

@router.get("/sessions/{session_id}")
def get_session(session_id: uuid.UUID, db: Session = Depends(get_db)):
    session = db.get(InspectionSession, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return {
        "id": str(session.id),
        "shop_id": str(session.shop_id),
        "technician_id": str(session.technician_id),
        "vehicle_id": str(session.vehicle_id),
        "status": session.status,
        "customer_concern": session.customer_concern,
        "started_at": session.started_at,
        "completed_at": session.completed_at,
        "findings": [{"id": str(f.id), "checklist_item_id": f.checklist_item_id, "transcript": f.transcript, "condition": f.condition, "structured_data": f.structured_data} for f in session.findings],
        "media": [{"id": str(m.id), "media_type": m.media_type, "s3_key": m.s3_key} for m in session.media]
    }

@router.post("/sessions/{session_id}/complete")
def complete_session(session_id: uuid.UUID, db: Session = Depends(get_db)):
    session = db.get(InspectionSession, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    session.status = SessionStatus.completed
    session.completed_at = datetime.utcnow()
    db.commit()
    return {"id": str(session.id), "status": session.status, "completed_at": session.completed_at}

@router.post("/sessions/{session_id}/findings", status_code=201)
def create_finding(session_id: uuid.UUID, body: FindingCreate, db: Session = Depends(get_db)):
    session = db.get(InspectionSession, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    finding = Finding(
        session_id=session_id,
        checklist_item_id=body.checklist_item_id,
        transcript=body.transcript,
        structured_data=body.structured_data,
        condition=body.condition
    )
    db.add(finding)
    db.commit()
    db.refresh(finding)
    return {"id": str(finding.id), "condition": finding.condition, "created_at": finding.created_at}

@router.patch("/findings/{finding_id}")
def update_finding(finding_id: uuid.UUID, body: FindingUpdate, db: Session = Depends(get_db)):
    finding = db.get(Finding, finding_id)
    if not finding:
        raise HTTPException(status_code=404, detail="Finding not found")
    if body.transcript is not None:
        finding.transcript = body.transcript
    if body.structured_data is not None:
        finding.structured_data = body.structured_data
    if body.condition is not None:
        finding.condition = body.condition
    db.commit()
    db.refresh(finding)
    return {"id": str(finding.id), "condition": finding.condition, "transcript": finding.transcript}

@router.get("/sessions/{session_id}/report")
def get_report(session_id: uuid.UUID, db: Session = Depends(get_db)):
    session = db.get(InspectionSession, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return {
        "report": {
            "session_id": str(session.id),
            "status": session.status,
            "started_at": session.started_at,
            "completed_at": session.completed_at,
            "customer_concern": session.customer_concern,
            "findings": [
                {
                    "id": str(f.id),
                    "checklist_item_id": f.checklist_item_id,
                    "transcript": f.transcript,
                    "condition": f.condition,
                    "structured_data": f.structured_data,
                    "media": [{"id": str(m.id), "media_type": m.media_type, "s3_key": m.s3_key} for m in f.media]
                } for f in session.findings
            ]
        }
    }
