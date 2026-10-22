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
from app.current_visit_security import (
    contact_encryption_key_id,
    contact_lookup_hmac,
    current_visit_release_enabled,
    encrypt_contact,
    normalize_contact,
    require_current_visit_release_enabled,
)
from app.db.models import ChecklistTemplate, CommunicationConsent, CustomerContactPoint, InspectionSession, SessionStatus, TemplateLifecycleStatus, User, UserRole
from app.db.session import get_db
from app.inspection_template import validated_template_snapshot

router = APIRouter(prefix="/check-in", tags=["check-in"])
_ADVISOR_OR_ADMIN = require_roles(UserRole.advisor, UserRole.admin)
_VIN = re.compile(r"^[A-HJ-NPR-Z0-9]{17}$")
_CONSENT_POLICY_VERSION = "current-visit-pilot-v1"


class CustomerContactAtCheckin(BaseModel):
    """Optional, visit-scoped contact and purpose-specific permission record."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    channel: Literal["sms", "email"]
    destination: str = Field(min_length=3, max_length=320)
    current_visit_link_consent: Literal["granted", "declined", "not_asked"] = "not_asked"
    current_visit_progress_consent: Literal["granted", "declined", "not_asked"] = "not_asked"


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
    assigned_technician_id: uuid.UUID
    customer_contact: CustomerContactAtCheckin | None = None

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
        "customer_contact_recorded": bool(session.customer_contacts),
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
    templates = (
        db.query(ChecklistTemplate)
        .filter(
            ChecklistTemplate.lifecycle_status == TemplateLifecycleStatus.approved,
            ChecklistTemplate.is_provisional.is_(False),
            ChecklistTemplate.active_for_new_visits.is_(True),
        )
        .order_by(ChecklistTemplate.name.asc(), ChecklistTemplate.version.desc())
        .all()
    )
    return {
        "actor": {"name": actor.name, "role": actor.role.value, "shop_id": str(actor.shop_id)},
        "technicians": [{"id": str(user.id), "name": user.name} for user in technicians],
        "checklists": [
            {"id": str(template.id), "name": template.name, "version": template.version, "vehicle_filter": template.vehicle_filter or {}}
            for template in templates
        ],
        "customer_contact_capture_enabled": current_visit_release_enabled(),
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

    templates = (
        db.query(ChecklistTemplate)
        .with_for_update()
        .filter(
            ChecklistTemplate.lifecycle_status == TemplateLifecycleStatus.approved,
            ChecklistTemplate.is_provisional.is_(False),
            ChecklistTemplate.active_for_new_visits.is_(True),
        )
        .all()
    )
    if len(templates) != 1:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="A single active approved inspection template is required before a new visit can be started",
        )
    template = templates[0]
    if not template.source_reference or not template.source_sha256 or not template.approved_at or not template.approved_by_user_id:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="The active inspection template is missing required approval provenance")
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
        template_source_reference=template.source_reference,
        template_source_sha256=template.source_sha256,
        template_approved_at=template.approved_at,
        template_approved_by_user_id=template.approved_by_user_id,
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
    if body.customer_contact:
        require_current_visit_release_enabled()
        normalized = normalize_contact(body.customer_contact.channel, body.customer_contact.destination)
        db.flush()
        contact = CustomerContactPoint(
            shop_id=actor.shop_id,
            session_id=session.id,
            channel=body.customer_contact.channel,
            encrypted_destination=encrypt_contact(normalized),
            encryption_key_id=contact_encryption_key_id(),
            lookup_hmac=contact_lookup_hmac(normalized),
            verification_state="unverified",
            created_by_user_id=actor.user_id,
            created_at=datetime.utcnow(),
        )
        db.add(contact)
        db.flush()
        db.add_all([
            CommunicationConsent(
                contact_point_id=contact.id,
                purpose="current_visit_link",
                state=body.customer_contact.current_visit_link_consent,
                policy_version=_CONSENT_POLICY_VERSION,
                captured_by_user_id=actor.user_id,
                captured_at=datetime.utcnow(),
            ),
            CommunicationConsent(
                contact_point_id=contact.id,
                purpose="current_visit_progress",
                state=body.customer_contact.current_visit_progress_consent,
                policy_version=_CONSENT_POLICY_VERSION,
                captured_by_user_id=actor.user_id,
                captured_at=datetime.utcnow(),
            ),
        ])
    db.commit()
    db.refresh(session)
    return _session_payload(session)
