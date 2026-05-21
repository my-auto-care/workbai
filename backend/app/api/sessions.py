from fastapi import APIRouter, Depends, HTTPException, Query
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
    technician_id: Optional[uuid.UUID] = None
    assigned_technician_id: Optional[uuid.UUID] = None
    vehicle_id: Optional[uuid.UUID] = None
    vehicle_year: Optional[int] = None
    vehicle_make: Optional[str] = None
    vehicle_model: Optional[str] = None
    vehicle_vin: Optional[str] = None
    vehicle_mileage: Optional[int] = None
    checklist_template_id: Optional[uuid.UUID] = None
    customer_concern: Optional[str] = None
    status: Optional[str] = None

class FindingCreate(BaseModel):
    checklist_item_id: Optional[str] = None
    transcript: Optional[str] = None
    structured_data: Optional[dict] = {}
    condition: Optional[FindingCondition] = FindingCondition.na

class FindingUpdate(BaseModel):
    transcript: Optional[str] = None
    structured_data: Optional[dict] = None
    condition: Optional[FindingCondition] = None

def _session_dict(s):
    return {
        "id": str(s.id),
        "shop_id": str(s.shop_id),
        "technician_id": str(s.technician_id) if s.technician_id else None,
        "assigned_technician_id": str(s.assigned_technician_id) if s.assigned_technician_id else None,
        "status": s.status,
        "customer_concern": s.customer_concern,
        "vehicle_year": s.vehicle_year,
        "vehicle_make": s.vehicle_make,
        "vehicle_model": s.vehicle_model,
        "vehicle_vin": s.vehicle_vin,
        "vehicle_mileage": s.vehicle_mileage,
        "started_at": s.started_at,
        "completed_at": s.completed_at,
    }

@router.get("/sessions")
def list_sessions(
    status: Optional[str] = Query(None),
    technician_id: Optional[uuid.UUID] = Query(None),
    db: Session = Depends(get_db)
):
    q = db.query(InspectionSession).order_by(InspectionSession.started_at.desc())
    if status:
        q = q.filter(InspectionSession.status == status)
    if technician_id:
        q = q.filter(
            (InspectionSession.technician_id == technician_id) |
            (InspectionSession.assigned_technician_id == technician_id)
        )
    sessions = q.limit(100).all()
    return [_session_dict(s) for s in sessions]

@router.post("/sessions", status_code=201)
def create_session(body: SessionCreate, db: Session = Depends(get_db)):
    initial_status = SessionStatus.pending if body.status == "pending" else SessionStatus.in_progress
    tech_id = body.technician_id or body.assigned_technician_id
    session = InspectionSession(
        shop_id=body.shop_id,
        technician_id=tech_id,
        assigned_technician_id=body.assigned_technician_id,
        vehicle_id=body.vehicle_id,
        vehicle_year=body.vehicle_year,
        vehicle_make=body.vehicle_make,
        vehicle_model=body.vehicle_model,
        vehicle_vin=body.vehicle_vin,
        vehicle_mileage=body.vehicle_mileage,
        checklist_template_id=body.checklist_template_id,
        customer_concern=body.customer_concern,
        status=initial_status,
        started_at=datetime.utcnow()
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return _session_dict(session)

@router.get("/sessions/{session_id}")
def get_session(session_id: uuid.UUID, db: Session = Depends(get_db)):
    session = db.get(InspectionSession, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    d = _session_dict(session)
    d["findings"] = [{"id": str(f.id), "checklist_item_id": f.checklist_item_id, "transcript": f.transcript, "condition": f.condition, "structured_data": f.structured_data} for f in session.findings]
    d["media"] = [{"id": str(m.id), "media_type": m.media_type, "s3_key": m.s3_key} for m in session.media]
    return d

@router.post("/sessions/{session_id}/start")
def start_session(session_id: uuid.UUID, db: Session = Depends(get_db)):
    session = db.get(InspectionSession, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    session.status = SessionStatus.in_progress
    db.commit()
    return _session_dict(session)

@router.post("/sessions/{session_id}/complete")
def complete_session(session_id: uuid.UUID, db: Session = Depends(get_db)):
    session = db.get(InspectionSession, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    session.status = SessionStatus.completed
    session.completed_at = datetime.utcnow()
    db.commit()
    return _session_dict(session)

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
            "vehicle_year": session.vehicle_year,
            "vehicle_make": session.vehicle_make,
            "vehicle_model": session.vehicle_model,
            "vehicle_vin": session.vehicle_vin,
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
