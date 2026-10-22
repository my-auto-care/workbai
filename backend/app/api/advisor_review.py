"""Advisor/admin review workbench for technician-submitted provisional inspections.

This router records internal human triage only. It deliberately cannot price, send,
release a customer view, create an authorization, or change technician evidence.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy.orm import Session

from app.api.sessions import _response_dict, _session_dict, _template_snapshot_or_409
from app.auth import StaffActor, require_roles, scoped_session_or_404
from app.db.models import (
    AdvisorDisposition,
    AdvisorReviewItem,
    FindingCondition,
    InspectionItemResponse,
    InspectionSession,
    SessionStatus,
    UserRole,
)
from app.db.session import get_db

router = APIRouter(tags=["advisor-review"])
_REVIEWER = require_roles(UserRole.advisor, UserRole.admin)


class AdvisorDispositionRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    disposition: Literal["safety", "maintenance", "visit_concern", "monitor", "no_action", "needs_clarification"]
    rationale: str = Field(min_length=3, max_length=2_000)

    @field_validator("rationale")
    @classmethod
    def meaningful_rationale(cls, value: str) -> str:
        if len(value.strip()) < 3:
            raise ValueError("A written advisor rationale is required")
        return value.strip()


def _value(value):
    return value.value if hasattr(value, "value") else value


def _decision_dict(decision: AdvisorReviewItem | None) -> dict | None:
    if decision is None:
        return None
    return {
        "id": str(decision.id),
        "template_item_id": decision.template_item_id,
        "disposition": _value(decision.disposition),
        "rationale": decision.rationale,
        "reviewed_by_user_id": str(decision.reviewed_by_user_id),
        "created_at": decision.created_at,
        "updated_at": decision.updated_at,
    }


def _review_session_or_409(
    session_id: uuid.UUID,
    actor: StaffActor,
    db: Session,
    *,
    lock_for_update: bool = False,
) -> InspectionSession:
    query = db.query(InspectionSession).filter(InspectionSession.id == session_id)
    if lock_for_update:
        # Serialize writes on the canonical visit, preventing a concurrent save
        # from committing after another advisor completes and locks the review.
        query = query.with_for_update()
    inspection = scoped_session_or_404(query.one_or_none(), actor)
    if inspection.status not in {SessionStatus.submitted, SessionStatus.advisor_reviewed}:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Advisor review begins only after a technician submits a complete inspection",
        )
    return inspection


def _attention_items(inspection: InspectionSession) -> tuple[dict, dict[str, InspectionItemResponse], dict[str, dict]]:
    snapshot, specs = _template_snapshot_or_409(inspection)
    responses = {
        response.template_item_id: response
        for response in inspection.item_responses
        if response.template_item_id in specs
    }
    attention = {
        item_id: response
        for item_id, response in responses.items()
        if _value(response.condition) == FindingCondition.poor.value
    }
    return snapshot, attention, specs


@router.get("/sessions/{session_id}/advisor-review")
def advisor_review_workspace(
    session_id: uuid.UUID,
    actor: StaffActor = Depends(_REVIEWER),
    db: Session = Depends(get_db),
):
    inspection = _review_session_or_409(session_id, actor, db)
    snapshot, attention, specs = _attention_items(inspection)
    decisions = {
        decision.template_item_id: decision
        for decision in db.query(AdvisorReviewItem).filter(AdvisorReviewItem.session_id == inspection.id).all()
    }
    ordered_attention = []
    for section in snapshot.get("sections", []):
        for item in section.get("items", []):
            item_id = item["id"]
            response = attention.get(item_id)
            if response is None:
                continue
            ordered_attention.append(
                {
                    "section_name": section["name"],
                    "item": {key: item.get(key) for key in ("id", "name", "type", "unit", "options")},
                    "technician_response": _response_dict(response),
                    "advisor_decision": _decision_dict(decisions.get(item_id)),
                }
            )

    response_conditions = [_value(response.condition) for response in inspection.item_responses if response.template_item_id in specs]
    return {
        "session": _session_dict(inspection),
        "attention_items": ordered_attention,
        "summary": {
            "attention_count": len(ordered_attention),
            "decisions_saved": sum(1 for item in ordered_attention if item["advisor_decision"]),
            "good_count": response_conditions.count(FindingCondition.good.value),
            "na_count": response_conditions.count(FindingCondition.na.value),
        },
        "can_review": inspection.status == SessionStatus.submitted,
        "customer_release_available": False,
    }


@router.put("/sessions/{session_id}/advisor-review/items/{item_id}")
def save_advisor_disposition(
    session_id: uuid.UUID,
    item_id: str,
    body: AdvisorDispositionRecord,
    actor: StaffActor = Depends(_REVIEWER),
    db: Session = Depends(get_db),
):
    inspection = _review_session_or_409(session_id, actor, db, lock_for_update=True)
    if inspection.status != SessionStatus.submitted:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Advisor review is already complete and locked")

    _, attention, specs = _attention_items(inspection)
    if item_id not in specs or item_id not in attention:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Only a technician-attested Needs attention item may receive an advisor disposition")

    decision = (
        db.query(AdvisorReviewItem)
        .filter(AdvisorReviewItem.session_id == inspection.id, AdvisorReviewItem.template_item_id == item_id)
        .one_or_none()
    )
    if decision is None:
        decision = AdvisorReviewItem(
            session_id=inspection.id,
            template_item_id=item_id,
            reviewed_by_user_id=actor.user_id,
            disposition=AdvisorDisposition(body.disposition),
            rationale=body.rationale,
        )
        db.add(decision)
    else:
        decision.disposition = AdvisorDisposition(body.disposition)
        decision.rationale = body.rationale
        decision.reviewed_by_user_id = actor.user_id
    db.commit()
    db.refresh(decision)
    return _decision_dict(decision)


@router.post("/sessions/{session_id}/advisor-review/complete")
def complete_advisor_review(
    session_id: uuid.UUID,
    actor: StaffActor = Depends(_REVIEWER),
    db: Session = Depends(get_db),
):
    inspection = _review_session_or_409(session_id, actor, db, lock_for_update=True)
    if inspection.status != SessionStatus.submitted:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Advisor review is already complete and locked")

    _, attention, _ = _attention_items(inspection)
    decided_ids = {
        item_id
        for (item_id,) in db.query(AdvisorReviewItem.template_item_id)
        .filter(AdvisorReviewItem.session_id == inspection.id)
        .all()
    }
    missing = sorted(set(attention) - decided_ids)
    if missing:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "message": "Every Needs attention item needs a written advisor disposition before review can be completed",
                "missing_item_ids": missing,
            },
        )

    inspection.status = SessionStatus.advisor_reviewed
    inspection.advisor_reviewed_at = datetime.utcnow()
    inspection.advisor_reviewed_by_user_id = actor.user_id
    db.commit()
    db.refresh(inspection)
    return {
        "session": _session_dict(inspection),
        "message": "Advisor review recorded. No customer report, estimate, message, repair authorization, or work release was created.",
    }
