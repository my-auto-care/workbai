"""Advisor/admin Check-in handoff for the Workbai inspection lifecycle."""

from __future__ import annotations

import re
import uuid
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy.orm import Session

from app.auth import StaffActor, require_roles
from app.db.models import ChecklistTemplate, InspectionSession, SessionStatus, User, UserRole
from app.db.session import get_db
from app.inspection_template import validated_template_snapshot

router = APIRouter(prefix="/check-in", tags=["check-in"])
_ADVISOR_OR_ADMIN = require_roles(UserRole.advisor, UserRole.admin)
_VIN = re.compile(r"^[A-HJ-NPR-Z0-9]{17}$")


class CheckinCreate(BaseModel):
    """The only web intake payload. Shop and actor are deliberately absent."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    vehicle_year: int = Field(ge=1886, le=2100)
    vehicle_make: str = Field(min_length=1, max_length=100)
    vehicle_model: str = Field(min_length=1, max_length=100)
    vehicle_vin: str | None = Field(default=None, max_length=17)
    vehicle_mileage: int | None = Field(default=None, ge=0, le=2_000_000)
    customer_concern: str = Field(min_length=3, max_length=1000)
    presence_mode: Literal["waiter", "dropoff"]
    checklist_template_id: uuid.UUID
    assigned_technician_id: uuid.UUID

    @field_validator("vehicle_vin")
    @classmethod
    def normalize_vin(cls, value: str | None) -> str | None:
        if value is None or not value.strip():
            return None
        normalized = value.replace(" ", "").upper()
        if not _VIN.fullmatch(normalized):
            raise ValueError("VIN must be 17 characters and cannot include I, O, or Q")
        return normalized


def _session_payload(session: InspectionSession) -> dict:
    return {
        "id": str(session.id),
        "status": session.status.value if isinstance(session.status, SessionStatus) else str(session.status),
        "shop_id": str(session.shop_id),
        "assigned_technician_id": str(session.assigned_technician_id),
        "vehicle_year": session.vehicle_year,
        "vehicle_make": session.vehicle_make,
        "vehicle_model": session.vehicle_model,
        "vehicle_vin": session.vehicle_vin,
        "vehicle_mileage": session.vehicle_mileage,
        "presence_mode": session.presence_mode,
        "template_version": session.template_version,
        "started_at": session.started_at,
    }


@router.get("/options")
def checkin_options(
    actor: StaffActor = Depends(_ADVISOR_OR_ADMIN),
    db: Session = Depends(get_db),
):
    technicians = (
        db.query(User)
        .filter(
            User.shop_id == actor.shop_id,
            User.active.is_(True),
            User.role == UserRole.technician,
        )
        .order_by(User.name.asc())
        .all()
    )
    templates = db.query(ChecklistTemplate).order_by(ChecklistTemplate.name.asc(), ChecklistTemplate.version.desc()).all()
    return {
        "actor": {"name": actor.name, "role": actor.role.value, "shop_id": str(actor.shop_id)},
        "technicians": [{"id": str(user.id), "name": user.name} for user in technicians],
        "checklists": [
            {"id": str(template.id), "name": template.name, "version": template.version, "vehicle_filter": template.vehicle_filter or {}}
            for template in templates
        ],
    }


@router.post("/sessions", status_code=status.HTTP_201_CREATED)
def create_pending_session(
    body: CheckinCreate,
    actor: StaffActor = Depends(_ADVISOR_OR_ADMIN),
    db: Session = Depends(get_db),
):
    technician = (
        db.query(User)
        .filter(
            User.id == body.assigned_technician_id,
            User.shop_id == actor.shop_id,
            User.active.is_(True),
            User.role == UserRole.technician,
        )
        .one_or_none()
    )
    if not technician:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Select an active technician in this shop")

    template = db.get(ChecklistTemplate, body.checklist_template_id)
    if not template:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Select an available shared inspection template")
    try:
        snapshot = validated_template_snapshot(template.items)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Selected inspection template is structurally invalid and cannot be used for a new visit",
        ) from exc

    session = InspectionSession(
        shop_id=actor.shop_id,
        technician_id=technician.id,
        assigned_technician_id=technician.id,
        checklist_template_id=template.id,
        template_snapshot=snapshot,
        template_version=template.version,
        presence_mode=body.presence_mode,
        vehicle_year=str(body.vehicle_year),
        vehicle_make=body.vehicle_make,
        vehicle_model=body.vehicle_model,
        vehicle_vin=body.vehicle_vin,
        vehicle_mileage=body.vehicle_mileage,
        customer_concern=body.customer_concern,
        status=SessionStatus.pending,
        started_at=datetime.utcnow(),
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return _session_payload(session)
