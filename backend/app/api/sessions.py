from datetime import datetime, timedelta
from typing import Literal, Optional
import uuid

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from sqlalchemy.orm import Session

from app.auth import StaffActor, get_current_actor, require_internal_scheduler, require_roles, scoped_session_or_404
from app.db.models import (
    ChecklistTemplate,
    Finding,
    FindingCondition,
    InspectionItemResponse,
    InspectionSession,
    Media,
    SessionStatus,
    User,
    UserRole,
    Vehicle,
)
from app.db.session import get_db
from app.inspection_template import validated_template_snapshot

router = APIRouter()


class FindingCreate(BaseModel):
    checklist_item_id: Optional[str] = None
    transcript: Optional[str] = None
    structured_data: Optional[dict] = {}
    condition: Optional[FindingCondition] = FindingCondition.na


class FindingUpdate(BaseModel):
    transcript: Optional[str] = None
    structured_data: Optional[dict] = None
    condition: Optional[FindingCondition] = None


class InspectionItemRecord(BaseModel):
    """A controlled technician response to one item in this visit's template snapshot."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    condition: Literal["good", "poor", "na"]
    note: Optional[str] = Field(default=None, max_length=2_000)
    measurement: Optional[str] = Field(default=None, max_length=128)
    selected_option: Optional[str] = Field(default=None, max_length=128)

    @field_validator("note", "measurement", "selected_option")
    @classmethod
    def blank_to_none(cls, value: Optional[str]) -> Optional[str]:
        return value.strip() if value and value.strip() else None

    @model_validator(mode="after")
    def require_explanation_when_not_good(self):
        if self.condition in {"poor", "na"} and not self.note:
            raise ValueError("A written note is required for Needs attention or N/A")
        return self


def _value(value):
    return value.value if hasattr(value, "value") else value


def _session_dict(inspection: InspectionSession):
    return {
        "id": str(inspection.id),
        "shop_id": str(inspection.shop_id),
        "technician_id": str(inspection.technician_id) if inspection.technician_id else None,
        "assigned_technician_id": str(inspection.assigned_technician_id) if inspection.assigned_technician_id else None,
        "status": _value(inspection.status),
        "customer_concern": inspection.customer_concern,
        "presence_mode": inspection.presence_mode,
        "vehicle_year": inspection.vehicle_year,
        "vehicle_make": inspection.vehicle_make,
        "vehicle_model": inspection.vehicle_model,
        "vehicle_vin": inspection.vehicle_vin,
        "vehicle_mileage": inspection.vehicle_mileage,
        "checklist_template_id": str(inspection.checklist_template_id) if inspection.checklist_template_id else None,
        "template_version": inspection.template_version,
        "started_at": inspection.started_at,
        "inspection_submitted_at": inspection.inspection_submitted_at,
        "completed_at": inspection.completed_at,
    }


def _media_dict(media: Media, with_url: bool = False):
    data = {"id": str(media.id), "media_type": _value(media.media_type), "s3_key": media.s3_key}
    if with_url:
        try:
            from app.api.media import presigned_read_url

            data["url"] = presigned_read_url(media.s3_key)
        except Exception:
            data["url"] = None
    return data


def _response_dict(response: InspectionItemResponse):
    return {
        "id": str(response.id),
        "template_item_id": response.template_item_id,
        "condition": _value(response.condition),
        "note": response.note,
        "measurement": response.measurement,
        "selected_option": (response.response_data or {}).get("selected_option"),
        "recorded_at": response.recorded_at,
        "updated_at": response.updated_at,
    }


def _operator_or_403(actor: StaffActor) -> None:
    if actor.role not in {UserRole.technician, UserRole.advisor, UserRole.admin}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient staff role")


def _assigned_technician_or_403(inspection: InspectionSession, actor: StaffActor) -> None:
    if actor.role == UserRole.technician and actor.user_id not in {inspection.technician_id, inspection.assigned_technician_id}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Inspection is not assigned to this technician")


def _snapshot_item_specs(snapshot: object) -> dict[str, dict]:
    """Return only controlled item nodes from the saved template snapshot."""
    if not isinstance(snapshot, dict):
        return {}
    sections = snapshot.get("sections")
    if not isinstance(sections, list):
        return {}

    items: dict[str, dict] = {}
    for section in sections:
        if not isinstance(section, dict) or not isinstance(section.get("items"), list):
            continue
        for item in section["items"]:
            if isinstance(item, dict) and isinstance(item.get("id"), str) and item["id"].strip():
                items[item["id"]] = item
    return items


def _template_snapshot_or_409(inspection: InspectionSession) -> tuple[dict, dict[str, dict]]:
    try:
        snapshot = validated_template_snapshot(inspection.template_snapshot)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This inspection has no valid controlled template snapshot. Start a new provisional-template inspection instead.",
        ) from exc
    specs = _snapshot_item_specs(snapshot)
    return snapshot, specs


def expire_stale_sessions(db: Session) -> dict:
    """Scheduler-only helper: expire active, unsubmitted sessions older than 24 hours."""
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
    payload["item_responses"] = [_response_dict(response) for response in inspection.item_responses]
    payload["media"] = [_media_dict(media, with_url=True) for media in inspection.media]
    return payload


@router.get("/sessions/{session_id}/inspection-workspace")
def inspection_workspace(
    session_id: uuid.UUID,
    actor: StaffActor = Depends(get_current_actor),
    db: Session = Depends(get_db),
):
    _operator_or_403(actor)
    inspection = scoped_session_or_404(db.get(InspectionSession, session_id), actor, require_assigned_technician=True)
    snapshot, specs = _template_snapshot_or_409(inspection)
    return {
        "session": _session_dict(inspection),
        "template": {
            "id": str(inspection.checklist_template_id),
            "version": inspection.template_version,
            "name": snapshot.get("name", "Provisional inspection template"),
            "description": snapshot.get("description"),
            "sections": snapshot.get("sections", []),
        },
        "responses": [_response_dict(response) for response in inspection.item_responses],
        "summary": {"item_count": len(specs), "response_count": len(inspection.item_responses)},
        "can_record": actor.role == UserRole.technician,
        "can_submit": actor.role == UserRole.technician and inspection.status == SessionStatus.in_progress,
    }


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


@router.put("/sessions/{session_id}/inspection-items/{item_id}")
def record_inspection_item(
    session_id: uuid.UUID,
    item_id: str,
    body: InspectionItemRecord,
    actor: StaffActor = Depends(require_roles(UserRole.technician)),
    db: Session = Depends(get_db),
):
    inspection = scoped_session_or_404(db.get(InspectionSession, session_id), actor, require_assigned_technician=True)
    _assigned_technician_or_403(inspection, actor)
    if inspection.status != SessionStatus.in_progress:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Item responses require an active inspection")

    _, specs = _template_snapshot_or_409(inspection)
    item = specs.get(item_id)
    if not item:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Item is not part of this inspection template snapshot")
    allowed_options = item.get("options")
    if body.selected_option and (not isinstance(allowed_options, list) or body.selected_option not in allowed_options):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Selected observation is not allowed for this template item")

    response = db.query(InspectionItemResponse).filter(
        InspectionItemResponse.session_id == inspection.id,
        InspectionItemResponse.template_item_id == item_id,
    ).one_or_none()
    if response is None:
        response = InspectionItemResponse(
            session_id=inspection.id,
            template_item_id=item_id,
            recorded_by_user_id=actor.user_id,
            condition=FindingCondition(body.condition),
        )
        db.add(response)
    response.condition = FindingCondition(body.condition)
    response.note = body.note
    response.measurement = body.measurement
    response.response_data = {"selected_option": body.selected_option} if body.selected_option else {}
    response.recorded_by_user_id = actor.user_id
    db.commit()
    db.refresh(response)
    return _response_dict(response)


@router.post("/sessions/{session_id}/submit-inspection")
def submit_inspection_for_advisor_review(
    session_id: uuid.UUID,
    actor: StaffActor = Depends(require_roles(UserRole.technician)),
    db: Session = Depends(get_db),
):
    inspection = scoped_session_or_404(db.get(InspectionSession, session_id), actor, require_assigned_technician=True)
    _assigned_technician_or_403(inspection, actor)
    if inspection.status != SessionStatus.in_progress:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Only active inspections may be submitted")

    _, specs = _template_snapshot_or_409(inspection)
    recorded = {
        response.template_item_id
        for response in db.query(InspectionItemResponse.template_item_id)
        .filter(InspectionItemResponse.session_id == inspection.id)
        .all()
    }
    missing = sorted(set(specs) - recorded)
    if missing:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"message": "Every applicable template item needs an explicit result before submission", "missing_item_ids": missing},
        )

    inspection.status = SessionStatus.submitted
    inspection.inspection_submitted_at = datetime.utcnow()
    db.commit()
    db.refresh(inspection)
    return {
        "session": _session_dict(inspection),
        "message": "Inspection submitted for advisor review. No customer report, estimate, message, or approval was created.",
    }


@router.post("/sessions/{session_id}/complete")
def complete_session(session_id: uuid.UUID, actor: StaffActor = Depends(require_roles(UserRole.technician)), db: Session = Depends(get_db)):
    inspection = scoped_session_or_404(db.get(InspectionSession, session_id), actor, require_assigned_technician=True)
    _assigned_technician_or_403(inspection, actor)
    if inspection.template_snapshot:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Template-driven inspections must be submitted for advisor review; technician completion is not a customer or repair completion state.",
        )
    if inspection.status != SessionStatus.in_progress:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Only active legacy inspections may be completed")
    inspection.status = SessionStatus.completed
    inspection.completed_at = datetime.utcnow()
    db.commit()
    db.refresh(inspection)
    return _session_dict(inspection)


@router.post("/sessions/{session_id}/findings", status_code=status.HTTP_201_CREATED)
def create_finding(session_id: uuid.UUID, body: FindingCreate, actor: StaffActor = Depends(require_roles(UserRole.technician)), db: Session = Depends(get_db)):
    inspection = scoped_session_or_404(db.get(InspectionSession, session_id), actor, require_assigned_technician=True)
    _assigned_technician_or_403(inspection, actor)
    if inspection.template_snapshot:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Use the controlled inspection-item response command for template-driven inspections")
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
    if inspection.template_snapshot:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Use the controlled inspection-item response command for template-driven inspections")
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
            **_session_dict(inspection),
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
            "item_responses": [_response_dict(response) for response in inspection.item_responses],
        }
    }


@router.post("/sessions/expire-stale")
def expire_stale_endpoint(
    x_workbai_scheduler_secret: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
):
    require_internal_scheduler(x_workbai_scheduler_secret)
    return expire_stale_sessions(db)
