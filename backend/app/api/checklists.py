"""Admin-controlled inspection template lifecycle.

Templates are shop-owned configuration: every read and write is limited to the
caller's shop. A draft may be edited, but an approved non-provisional template is
immutable and can be the shop's single active selection for new Check-in sessions.
Retired templates remain readable for historical snapshots.
"""

from __future__ import annotations

import re
import uuid
from datetime import datetime
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy.orm import Session

from app.auth import StaffActor, get_current_actor, require_roles
from app.db.models import ChecklistTemplate, TemplateLifecycleStatus, UserRole
from app.db.session import get_db
from app.inspection_template import InspectionTemplateDocument, validated_template_snapshot

router = APIRouter()
_SHA256 = re.compile(r"^[a-f0-9]{64}$")
_ADMIN = require_roles(UserRole.admin)


class ChecklistCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=200)
    vehicle_filter: Optional[dict] = {}
    items: InspectionTemplateDocument
    is_provisional: bool = True
    source_reference: str | None = Field(default=None, max_length=500)
    source_sha256: str | None = Field(default=None, max_length=64)

    @model_validator(mode="after")
    def source_for_non_provisional(self):
        if not self.is_provisional:
            _validate_source(self.source_reference, self.source_sha256)
        return self


class ChecklistUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    vehicle_filter: Optional[dict] = None
    items: Optional[InspectionTemplateDocument] = None
    is_provisional: bool | None = None
    source_reference: str | None = Field(default=None, max_length=500)
    source_sha256: str | None = Field(default=None, max_length=64)


class TemplateApproval(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    confirm_controlled_artifact: Literal[True]


class TemplateRetirement(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    confirm_retirement: Literal[True]


def _staff(actor: StaffActor = Depends(get_current_actor)) -> StaffActor:
    if actor.role not in {UserRole.technician, UserRole.advisor, UserRole.admin}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient staff role")
    return actor


def _value(value: object) -> str:
    return getattr(value, "value", str(value))


def _validate_source(source_reference: str | None, source_sha256: str | None) -> None:
    if not source_reference or len(source_reference.strip()) < 3:
        raise ValueError("A controlled source reference is required for a non-provisional template")
    if not source_sha256 or not _SHA256.fullmatch(source_sha256.lower()):
        raise ValueError("A lowercase 64-character SHA-256 artifact hash is required for a non-provisional template")


def _template_or_404(checklist_id: uuid.UUID, db: Session, actor: StaffActor, *, lock_for_update: bool = False) -> ChecklistTemplate:
    # Templates are shop-owned: another shop's template is indistinguishable from a missing one.
    query = db.query(ChecklistTemplate).filter(ChecklistTemplate.id == checklist_id, ChecklistTemplate.shop_id == actor.shop_id)
    if lock_for_update:
        query = query.with_for_update()
    template = query.one_or_none()
    if not template:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Checklist not found")
    return template


def _summary(template: ChecklistTemplate) -> dict:
    return {
        "id": str(template.id),
        "name": template.name,
        "version": template.version,
        "vehicle_filter": template.vehicle_filter or {},
        "lifecycle_status": _value(template.lifecycle_status),
        "is_provisional": template.is_provisional,
        "locked_provisional": template.locked_provisional,
        "active_for_new_visits": template.active_for_new_visits,
        "source_reference": template.source_reference,
        "source_sha256": template.source_sha256,
        "approved_at": template.approved_at,
        "approved_by_user_id": str(template.approved_by_user_id) if template.approved_by_user_id else None,
        "retired_at": template.retired_at,
        "retired_by_user_id": str(template.retired_by_user_id) if template.retired_by_user_id else None,
        "created_at": template.created_at,
        "updated_at": template.updated_at,
    }


def _detail(template: ChecklistTemplate) -> dict:
    return {**_summary(template), "items": template.items}


@router.get("/checklists")
def list_checklists(actor: StaffActor = Depends(_ADMIN), db: Session = Depends(get_db)):
    templates = (
        db.query(ChecklistTemplate)
        .filter(ChecklistTemplate.shop_id == actor.shop_id)
        .order_by(ChecklistTemplate.updated_at.desc(), ChecklistTemplate.name.asc())
        .all()
    )
    return [_summary(template) for template in templates]


@router.get("/checklists/{checklist_id}")
def get_checklist(checklist_id: uuid.UUID, actor: StaffActor = Depends(_ADMIN), db: Session = Depends(get_db)):
    return _detail(_template_or_404(checklist_id, db, actor))


@router.post("/checklists", status_code=status.HTTP_201_CREATED)
def create_checklist(
    body: ChecklistCreate,
    actor: StaffActor = Depends(_ADMIN),
    db: Session = Depends(get_db),
):
    template = ChecklistTemplate(
        shop_id=actor.shop_id,
        name=body.name,
        vehicle_filter=body.vehicle_filter,
        items=body.items.storage_dict(),
        lifecycle_status=TemplateLifecycleStatus.draft,
        is_provisional=body.is_provisional,
        locked_provisional=False,
        active_for_new_visits=False,
        source_reference=body.source_reference,
        source_sha256=body.source_sha256.lower() if body.source_sha256 else None,
    )
    db.add(template)
    db.commit()
    db.refresh(template)
    return _detail(template)


@router.patch("/checklists/{checklist_id}")
def update_checklist(
    checklist_id: uuid.UUID,
    body: ChecklistUpdate,
    actor: StaffActor = Depends(_ADMIN),
    db: Session = Depends(get_db),
):
    template = _template_or_404(checklist_id, db, actor, lock_for_update=True)
    if template.lifecycle_status != TemplateLifecycleStatus.draft:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Approved and retired templates are immutable; create a new draft for changes")

    if template.locked_provisional and body.is_provisional is False:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This legacy/provisional template is permanently ineligible for approval; create a new controlled draft from the verified artifact",
        )
    next_provisional = template.is_provisional if body.is_provisional is None else body.is_provisional
    next_reference = template.source_reference if body.source_reference is None else body.source_reference
    next_hash = template.source_sha256 if body.source_sha256 is None else body.source_sha256.lower()
    try:
        if not next_provisional:
            _validate_source(next_reference, next_hash)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc

    if body.name is not None:
        template.name = body.name
    if body.vehicle_filter is not None:
        template.vehicle_filter = body.vehicle_filter
    if body.items is not None:
        template.items = body.items.storage_dict()
        template.version += 1
    template.is_provisional = next_provisional
    template.source_reference = next_reference
    template.source_sha256 = next_hash
    db.commit()
    db.refresh(template)
    return _detail(template)


@router.post("/checklists/{checklist_id}/approve")
def approve_checklist(
    checklist_id: uuid.UUID,
    body: TemplateApproval,
    actor: StaffActor = Depends(_ADMIN),
    db: Session = Depends(get_db),
):
    # Lock this shop's template registry while rotating its single active
    # selection. This prevents two concurrent approvals from both claiming active.
    # Other shops' templates are never read, locked or deactivated here.
    templates = (
        db.query(ChecklistTemplate)
        .filter(ChecklistTemplate.shop_id == actor.shop_id)
        .with_for_update()
        .order_by(ChecklistTemplate.created_at.asc())
        .all()
    )
    template = next((candidate for candidate in templates if candidate.id == checklist_id), None)
    if template is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Checklist not found")
    if template.lifecycle_status != TemplateLifecycleStatus.draft:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Only a draft template can be approved")
    if template.is_provisional:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="A provisional test template cannot be approved for new visits")
    if template.locked_provisional:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This legacy/provisional template is permanently ineligible for approval")
    try:
        _validate_source(template.source_reference, template.source_sha256)
        validated_template_snapshot(template.items)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc

    for candidate in templates:
        candidate.active_for_new_visits = False
    # PostgreSQL checks the partial unique index per update. Flush the
    # deactivation before setting the new target active so ORM update ordering
    # cannot cause a transient duplicate-active violation.
    db.flush()
    template.lifecycle_status = TemplateLifecycleStatus.approved
    template.active_for_new_visits = True
    template.approved_at = datetime.utcnow()
    template.approved_by_user_id = actor.user_id
    db.commit()
    db.refresh(template)
    return _detail(template)


@router.post("/checklists/{checklist_id}/retire")
def retire_checklist(
    checklist_id: uuid.UUID,
    body: TemplateRetirement,
    actor: StaffActor = Depends(_ADMIN),
    db: Session = Depends(get_db),
):
    template = _template_or_404(checklist_id, db, actor, lock_for_update=True)
    if template.lifecycle_status == TemplateLifecycleStatus.retired:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This template is already retired")
    template.lifecycle_status = TemplateLifecycleStatus.retired
    template.active_for_new_visits = False
    template.retired_at = datetime.utcnow()
    template.retired_by_user_id = actor.user_id
    db.commit()
    db.refresh(template)
    return _detail(template)
