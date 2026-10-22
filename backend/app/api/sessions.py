from datetime import datetime, timedelta
from typing import Optional
import uuid

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.auth import StaffActor, get_current_actor, require_internal_scheduler, require_roles, scoped_session_or_404
from app.db.models import Finding, FindingCondition, InspectionSession, Media, SessionStatus, User, UserRole, Vehicle
from app.db.session import get_db

router = APIRouter()


class SessionCreate(BaseModel):
    """Legacy-compatible inspection start payload. Shop scope is never accepted from the caller."""

    model_config = ConfigDict(extra="forbid")
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


def _value(value):
    return value.value if hasattr(value, "value") else value


def _session_dict(s):
    return {
        "id": str(s.id),
        "shop_id": str(s.shop_id),
        "technician_id": str(s.technician_id) if s.technician_id else None,
        "assigned_technician_id": str(s.assigned_technician_id) if s.assigned_technician_id else None,
        "status": _value(s.status),
        "customer_concern": s.customer_concern,
        "vehicle_year": s.vehicle_year,
        "vehicle_make": s.vehicle_make,
        "vehicle_model": s.vehicle_model,
        "vehicle_vin": s.vehicle_vin,
        "vehicle_mileage": s.vehicle_mileage,
        "checklist_template_id": str(s.checklist_template_id) if s.checklist_template_id else None,
        "started_at": s.started_at,
        "completed_at": s.completed_at,
    }


def _media_dict(m, with_url: bool = False):
    data = {"id": str(m.id), "media_type": _value(m.media_type), "s3_key": m.s3_key}
    if with_url:
        try:
            from app.api.media import presigned_read_url
            data["url"] = presigned_read_url(m.s3_key)
        except Exception:
            data["url"] = None
    return data


def _operator_or_403(actor: StaffActor) -> None:
    if actor.role not in {UserRole.technician, UserRole.advisor, UserRole.admin}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient staff role")


def _assigned_technician_or_403(session: InspectionSession, actor: StaffActor) -> None:
    if actor.role == UserRole.technician and actor.user_id not in {session.technician_id, session.assigned_technician_id}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Inspection is not assigned to this technician")


def expire_stale_sessions(db: Session) -> dict:
    """Scheduler-only helper: expire in-progress sessions older than 24 hours."""
    cutoff = datetime.utcnow() - timedelta(hours=24)
    stale = db.query(InspectionSession).filter(
        InspectionSession.status == SessionStatus.in_progress,
        InspectionSession.started_at < cutoff,
    ).all()
    expired_ids = []
    for inspection in stale:
        inspection.status = SessionStatus.abandoned
        expired_ids.append(str(inspection.id))
    if stale:
        db.commit()
    return {"expired_count": len(expired_ids), "expired_ids": expired_ids}


@router.get("/sessions")
def list_sessions(
    status_filter: Optional[str] = Query(None, alias="status"),
    technician_id: Optional[uuid.UUID] = Query(None),
    actor: StaffActor = Depends(get_current_actor),
    db: Session = Depends(get_db),
):
    _operator_or_403(actor)
    query = db.query(InspectionSession).filter(InspectionSession.shop_id == actor.shop_id)
    if actor.role == UserRole.technician:
        query = query.filter(
            (InspectionSession.technician_id == actor.user_id)
            | (InspectionSession.assigned_technician_id == actor.user_id)
        )
    elif technician_id:
        query = query.filter(
            (InspectionSession.technician_id == technician_id)
            | (InspectionSession.assigned_technician_id == technician_id)
        )
    if status_filter:
        query = query.filter(InspectionSession.status == status_filter)
    return [_session_dict(inspection) for inspection in query.order_by(InspectionSession.started_at.desc()).limit(100).all()]


@router.post("/sessions", status_code=status.HTTP_201_CREATED)
def create_session(
    body: SessionCreate,
    actor: StaffActor = Depends(get_current_actor),
    db: Session = Depends(get_db),
):
    _operator_or_403(actor)
    requested_technician = body.assigned_technician_id or body.technician_id
    if actor.role == UserRole.technician:
        if requested_technician and requested_technician != actor.user_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Technicians may only start their own inspection")
        technician_id = actor.user_id
        initial_status = SessionStatus.in_progress
    else:
        if not requested_technician:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="An assigned technician is required")
        technician = db.query(User).filter(
            User.id == requested_technician,
            User.shop_id == actor.shop_id,
            User.active.is_(True),
            User.role == UserRole.technician,
        ).one_or_none()
        if not technician:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Select an active technician in this shop")
        technician_id = technician.id
        initial_status = SessionStatus.pending if body.status == "pending" else SessionStatus.in_progress

    if body.vehicle_id:
        vehicle = db.query(Vehicle).filter(Vehicle.id == body.vehicle_id, Vehicle.shop_id == actor.shop_id).one_or_none()
        if not vehicle:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Vehicle is not available in this shop")

    inspection = InspectionSession(
        shop_id=actor.shop_id,
        technician_id=technician_id,
        assigned_technician_id=technician_id,
        vehicle_id=body.vehicle_id,
        vehicle_year=str(body.vehicle_year) if body.vehicle_year else None,
        vehicle_make=body.vehicle_make,
        vehicle_model=body.vehicle_model,
        vehicle_vin=body.vehicle_vin,
        vehicle_mileage=body.vehicle_mileage,
        checklist_template_id=body.checklist_template_id,
        customer_concern=body.customer_concern,
        status=initial_status,
        started_at=datetime.utcnow(),
    )
    db.add(inspection)
    db.commit()
    db.refresh(inspection)
    return _session_dict(inspection)


@router.get("/sessions/{session_id}")
def get_session(session_id: uuid.UUID, actor: StaffActor = Depends(get_current_actor), db: Session = Depends(get_db)):
    _operator_or_403(actor)
    inspection = scoped_session_or_404(db.get(InspectionSession, session_id), actor, require_assigned_technician=True)
    payload = _session_dict(inspection)
    payload["findings"] = [
        {
            "id": str(finding.id),
            "checklist_item_id": finding.checklist_item_id,
            "transcript": finding.transcript,
            "condition": _value(finding.condition),
            "structured_data": finding.structured_data,
        }
        for finding in inspection.findings
    ]
    payload["media"] = [_media_dict(media, with_url=True) for media in inspection.media]
    return payload


@router.post("/sessions/{session_id}/start")
def start_session(session_id: uuid.UUID, actor: StaffActor = Depends(require_roles(UserRole.technician)), db: Session = Depends(get_db)):
    inspection = scoped_session_or_404(db.get(InspectionSession, session_id), actor, require_assigned_technician=True)
    _assigned_technician_or_403(inspection, actor)
    if inspection.status != SessionStatus.pending:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Only pending inspections may be started")
    inspection.status = SessionStatus.in_progress
    db.commit()
    db.refresh(inspection)
    return _session_dict(inspection)


@router.post("/sessions/{session_id}/complete")
def complete_session(session_id: uuid.UUID, actor: StaffActor = Depends(require_roles(UserRole.technician)), db: Session = Depends(get_db)):
    inspection = scoped_session_or_404(db.get(InspectionSession, session_id), actor, require_assigned_technician=True)
    _assigned_technician_or_403(inspection, actor)
    if inspection.status != SessionStatus.in_progress:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Only active inspections may be completed")
    inspection.status = SessionStatus.completed
    inspection.completed_at = datetime.utcnow()
    db.commit()
    db.refresh(inspection)
    return _session_dict(inspection)


@router.post("/sessions/{session_id}/findings", status_code=status.HTTP_201_CREATED)
def create_finding(session_id: uuid.UUID, body: FindingCreate, actor: StaffActor = Depends(require_roles(UserRole.technician)), db: Session = Depends(get_db)):
    inspection = scoped_session_or_404(db.get(InspectionSession, session_id), actor, require_assigned_technician=True)
    _assigned_technician_or_403(inspection, actor)
    if inspection.status != SessionStatus.in_progress:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Findings require an active inspection")
    finding = Finding(
        session_id=session_id,
        checklist_item_id=body.checklist_item_id,
        transcript=body.transcript,
        structured_data=body.structured_data,
        condition=body.condition,
    )
    db.add(finding)
    db.commit()
    db.refresh(finding)
    return {"id": str(finding.id), "condition": _value(finding.condition), "created_at": finding.created_at}


@router.patch("/findings/{finding_id}")
def update_finding(finding_id: uuid.UUID, body: FindingUpdate, actor: StaffActor = Depends(require_roles(UserRole.technician)), db: Session = Depends(get_db)):
    finding = db.get(Finding, finding_id)
    inspection = scoped_session_or_404(finding.session if finding else None, actor, require_assigned_technician=True)
    _assigned_technician_or_403(inspection, actor)
    if inspection.status != SessionStatus.in_progress:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Findings require an active inspection")
    if body.transcript is not None:
        finding.transcript = body.transcript
    if body.structured_data is not None:
        finding.structured_data = body.structured_data
    if body.condition is not None:
        finding.condition = body.condition
    db.commit()
    db.refresh(finding)
    return {"id": str(finding.id), "condition": _value(finding.condition), "transcript": finding.transcript}


@router.get("/sessions/{session_id}/report")
def get_report(session_id: uuid.UUID, actor: StaffActor = Depends(get_current_actor), db: Session = Depends(get_db)):
    _operator_or_403(actor)
    inspection = scoped_session_or_404(db.get(InspectionSession, session_id), actor, require_assigned_technician=True)
    return {
        "report": {
            "session_id": str(inspection.id),
            "status": _value(inspection.status),
            "started_at": inspection.started_at,
            "completed_at": inspection.completed_at,
            "customer_concern": inspection.customer_concern,
            "vehicle_year": inspection.vehicle_year,
            "vehicle_make": inspection.vehicle_make,
            "vehicle_model": inspection.vehicle_model,
            "vehicle_vin": inspection.vehicle_vin,
            "vehicle_mileage": inspection.vehicle_mileage,
            "findings": [
                {
                    "id": str(finding.id),
                    "checklist_item_id": finding.checklist_item_id,
                    "transcript": finding.transcript,
                    "condition": _value(finding.condition),
                    "structured_data": finding.structured_data,
                    "media": [_media_dict(media, with_url=True) for media in finding.media],
                }
                for finding in inspection.findings
            ],
        }
    }


@router.post("/sessions/expire-stale")
def expire_stale_endpoint(
    x_workbai_scheduler_secret: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
):
    require_internal_scheduler(x_workbai_scheduler_secret)
    return expire_stale_sessions(db)
