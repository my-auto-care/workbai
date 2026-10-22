"""Default-off Current Visit release domain.

This module never adapts staff report serializers for public use. It produces a
small immutable projection and serves it only after an explicit manager release.
Outbound SMS/email delivery is intentionally not implemented in this slice.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta
from typing import Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.advisor_review import _current_visit_readiness
from app.auth import StaffActor, require_roles, scoped_session_or_404
from app.current_visit_security import (
    current_visit_public_edge_verified,
    current_visit_release_enabled,
    new_public_secret,
    public_access_hmac,
    public_glovebox_origin,
    public_link_hmac,
    public_link_hmac_key_id,
    public_support_phone,
    require_current_visit_public_edge_verified,
    require_current_visit_release_enabled,
    trusted_client_ip,
    valid_public_resolver_key,
    valid_public_secret,
)
from app.db.models import (
    CommunicationConsent,
    CurrentVisitProjectionRevision,
    CurrentVisitRelease,
    CustomerContactPoint,
    CustomerPublicAccessAudit,
    CustomerPublicLink,
    CustomerReleaseManagerGrant,
    CurrentVisitReleaseAudit,
    CurrentVisitRateLimitBucket,
    InspectionSession,
    SessionStatus,
    Shop,
    User,
    UserRole,
)
from app.db.session import get_db


router = APIRouter(tags=["current-visit"])
_ADVISOR_OR_ADMIN = require_roles(UserRole.advisor, UserRole.admin)
_ADMIN = require_roles(UserRole.admin)
_POLICY_VERSION = "current-visit-pilot-v1"
_COUNTER_LINK_TTL = timedelta(minutes=15)
# The durable worker runs every five minutes. Keep a one-hour cushion so normal
# scheduling jitter deletes public-access audit data before the seven-day maximum.
_PUBLIC_AUDIT_RETENTION = timedelta(days=6, hours=23)
_PROGRESS_CODES = {
    "checked_in": "Your visit has been checked in.",
    "inspection_underway": "The visit inspection is in progress. Your advisor will post the next update after review.",
    "team_reviewing": "Your advisor is reviewing the visit. Contact the store if you need an update now.",
    "shop_update_available": "Your service advisor would like to speak with you about the next step.",
}


class ManagerGrantCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_id: UUID
    active: bool


class PrepareReleaseCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")

    human_owner_user_id: UUID | None = None


class RevokeReleaseCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: Literal["customer_requested", "wrong_recipient", "privacy_request", "other"]


class ProgressRequestCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status_code: Literal["checked_in", "inspection_underway", "team_reviewing", "shop_update_available"]


class PublicResolveCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")

    secret: str = Field(min_length=32, max_length=256)


def _value(value):
    return value.value if hasattr(value, "value") else value


def _utc(value: datetime | None) -> str | None:
    return value.replace(microsecond=0).isoformat() + "Z" if value else None


def _manager_grant(actor: StaffActor, db: Session) -> CustomerReleaseManagerGrant | None:
    return (
        db.query(CustomerReleaseManagerGrant)
        .filter(
            CustomerReleaseManagerGrant.shop_id == actor.shop_id,
            CustomerReleaseManagerGrant.user_id == actor.user_id,
            CustomerReleaseManagerGrant.active.is_(True),
        )
        .one_or_none()
    )


def _require_manager(actor: StaffActor, db: Session) -> None:
    if not _manager_grant(actor, db):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Current Visit manager delegation is required")


def _release_session(session_id: UUID, actor: StaffActor, db: Session) -> InspectionSession:
    inspection = scoped_session_or_404(db.get(InspectionSession, session_id), actor)
    return inspection


def _assert_release_eligible(inspection: InspectionSession, db: Session) -> None:
    readiness = _current_visit_readiness(inspection, db)
    if inspection.status != SessionStatus.advisor_reviewed or not readiness["ready_for_future_customer_access"]:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"message": "Current Visit requires completed internal review and verified controlled-template provenance", "reasons": readiness["reasons"]},
        )
    if not inspection.template_source_sha256 or not inspection.advisor_reviewed_at or not inspection.advisor_reviewed_by_user_id:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Current Visit source record is incomplete")


def _assert_release_source(release: CurrentVisitRelease, inspection: InspectionSession) -> None:
    if (
        release.source_template_sha256 != inspection.template_source_sha256
        or release.source_advisor_reviewed_at != inspection.advisor_reviewed_at
        or release.source_advisor_reviewed_by_user_id != inspection.advisor_reviewed_by_user_id
    ):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Current Visit source record changed; prepare a new manager review")


def _safe_vehicle_label(inspection: InspectionSession) -> str:
    label = " ".join(value for value in [inspection.vehicle_year, inspection.vehicle_make, inspection.vehicle_model] if value)
    return label[:160] if label else "Your vehicle"


def _payload_hash(payload: dict) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    return hashlib.sha256(encoded).hexdigest()


def _projection_payload(inspection: InspectionSession, shop: Shop, status_code: str) -> dict:
    if status_code not in _PROGRESS_CODES:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Unsupported customer progress state")
    return {
        "schema_version": 1,
        "vehicle_label": _safe_vehicle_label(inspection),
        "shop": {"display_name": shop.name[:160], "support_phone": public_support_phone()},
        "visit": {"status_code": status_code, "status_label": _PROGRESS_CODES[status_code], "updated_at": _utc(datetime.utcnow())},
        "contact": {"primary_action_label": "Call the shop"},
        "disclosure": "This page provides a limited update about your current visit. It is not an estimate, diagnosis, approval request, invoice, or authorization for work.",
    }


def _release_summary(inspection: InspectionSession, actor: StaffActor, db: Session) -> dict:
    release = (
        db.query(CurrentVisitRelease)
        .filter(CurrentVisitRelease.inspection_session_id == inspection.id)
        .one_or_none()
    )
    readiness = _current_visit_readiness(inspection, db)
    if not release:
        return {
            "feature_enabled": current_visit_release_enabled(),
            "internal_readiness": readiness,
            "manager_delegated": bool(_manager_grant(actor, db)),
            "release": None,
            "outbound_delivery": {"enabled": False, "reason": "No approved delivery provider or recipient-verification flow is configured."},
        }
    active_link = (
        db.query(CustomerPublicLink)
        .filter(CustomerPublicLink.release_id == release.id, CustomerPublicLink.state == "active")
        .one_or_none()
    )
    current_projection = None
    if release.active_projection_revision is not None:
        current_projection = (
            db.query(CurrentVisitProjectionRevision)
            .filter(
                CurrentVisitProjectionRevision.release_id == release.id,
                CurrentVisitProjectionRevision.revision == release.active_projection_revision,
            )
            .one_or_none()
        )
    pending_projection = (
        db.query(CurrentVisitProjectionRevision)
        .filter(CurrentVisitProjectionRevision.release_id == release.id, CurrentVisitProjectionRevision.state == "draft")
        .order_by(CurrentVisitProjectionRevision.revision.desc())
        .first()
    )
    contact = (
        db.query(CustomerContactPoint)
        .filter(CustomerContactPoint.session_id == inspection.id)
        .order_by(CustomerContactPoint.created_at.asc())
        .first()
    )
    consent_states: dict[str, str] = {}
    if contact:
        consent_states = {
            consent.purpose: consent.state
            for consent in db.query(CommunicationConsent).filter(CommunicationConsent.contact_point_id == contact.id).all()
        }
    return {
        "feature_enabled": current_visit_release_enabled(),
        "internal_readiness": readiness,
        "manager_delegated": bool(_manager_grant(actor, db)),
        "release": {
            "state": release.state,
            "human_owner_user_id": str(release.human_owner_user_id),
            "prepared_at": _utc(release.prepared_at),
            "approved_at": _utc(release.approved_at),
            "active_projection": {"revision": current_projection.revision, "status_code": current_projection.status_code} if current_projection else None,
            "pending_projection": {"revision": pending_projection.revision, "status_code": pending_projection.status_code} if pending_projection else None,
            "active_counter_link_expires_at": _utc(active_link.expires_at) if active_link else None,
            "contact": {
                "present": bool(contact),
                "channel": contact.channel if contact else None,
                "verification_state": contact.verification_state if contact else None,
                "consents": consent_states,
            },
        },
        "outbound_delivery": {"enabled": False, "reason": "No approved delivery provider or recipient-verification flow is configured."},
    }


def _next_projection(release: CurrentVisitRelease, inspection: InspectionSession, actor: StaffActor, db: Session, status_code: str) -> CurrentVisitProjectionRevision:
    shop = db.get(Shop, inspection.shop_id)
    if not shop:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Current Visit shop record is unavailable")
    latest = (
        db.query(CurrentVisitProjectionRevision.revision)
        .filter(CurrentVisitProjectionRevision.release_id == release.id)
        .order_by(CurrentVisitProjectionRevision.revision.desc())
        .first()
    )
    revision = (latest[0] if latest else 0) + 1
    payload = _projection_payload(inspection, shop, status_code)
    projection = CurrentVisitProjectionRevision(
        release_id=release.id,
        revision=revision,
        state="draft",
        status_code=status_code,
        schema_version=1,
        payload_json=payload,
        payload_sha256=_payload_hash(payload),
        prepared_by_user_id=actor.user_id,
        prepared_at=datetime.utcnow(),
    )
    db.add(projection)
    db.flush()
    return projection


def _locked_release(inspection: InspectionSession, db: Session) -> CurrentVisitRelease:
    release = (
        db.query(CurrentVisitRelease)
        .filter(CurrentVisitRelease.inspection_session_id == inspection.id)
        .with_for_update()
        .one_or_none()
    )
    if not release:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Prepare a Current Visit release before this action")
    return release


def _audit_release(db: Session, *, inspection: InspectionSession, release: CurrentVisitRelease | None, actor: StaffActor, action: str, reason_code: str | None = None, projection: CurrentVisitProjectionRevision | None = None) -> None:
    db.add(CurrentVisitReleaseAudit(
        shop_id=inspection.shop_id,
        inspection_session_id=inspection.id,
        release_id=release.id if release else None,
        action=action,
        actor_user_id=actor.user_id,
        reason_code=reason_code,
        release_state=release.state if release else None,
        projection_sha256=projection.payload_sha256 if projection else None,
        occurred_at=datetime.utcnow(),
    ))


@router.get("/current-visit/manager-grants")
def list_manager_grants(actor: StaffActor = Depends(_ADMIN), db: Session = Depends(get_db)):
    users = (
        db.query(User)
        .filter(User.shop_id == actor.shop_id, User.active.is_(True), User.role.in_([UserRole.advisor, UserRole.admin]))
        .order_by(User.name.asc())
        .all()
    )
    grant_ids = {
        grant.user_id
        for grant in db.query(CustomerReleaseManagerGrant)
        .filter(CustomerReleaseManagerGrant.shop_id == actor.shop_id, CustomerReleaseManagerGrant.active.is_(True))
        .all()
    }
    return {"feature_enabled": current_visit_release_enabled(), "users": [{"id": str(user.id), "name": user.name, "role": _value(user.role), "current_visit_manager": user.id in grant_ids} for user in users]}


@router.put("/current-visit/manager-grants")
def set_manager_grant(body: ManagerGrantCommand, actor: StaffActor = Depends(_ADMIN), db: Session = Depends(get_db)):
    require_current_visit_release_enabled()
    user = db.query(User).filter(User.id == body.user_id, User.shop_id == actor.shop_id, User.active.is_(True)).one_or_none()
    if not user or user.role not in {UserRole.advisor, UserRole.admin}:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Current Visit manager delegation requires an active advisor or administrator in this shop")
    grant = (
        db.query(CustomerReleaseManagerGrant)
        .filter(CustomerReleaseManagerGrant.shop_id == actor.shop_id, CustomerReleaseManagerGrant.user_id == user.id)
        .one_or_none()
    )
    if not grant:
        grant = CustomerReleaseManagerGrant(shop_id=actor.shop_id, user_id=user.id, active=body.active, granted_by_user_id=actor.user_id, granted_at=datetime.utcnow())
        db.add(grant)
    elif body.active:
        grant.active = True
        grant.granted_by_user_id = actor.user_id
        grant.granted_at = datetime.utcnow()
        grant.revoked_by_user_id = None
        grant.revoked_at = None
    else:
        grant.active = False
        grant.revoked_by_user_id = actor.user_id
        grant.revoked_at = datetime.utcnow()
    db.commit()
    return {"user_id": str(user.id), "current_visit_manager": grant.active}


@router.get("/sessions/{session_id}/current-visit")
def current_visit_status(session_id: UUID, actor: StaffActor = Depends(_ADVISOR_OR_ADMIN), db: Session = Depends(get_db)):
    return _release_summary(_release_session(session_id, actor, db), actor, db)


@router.post("/sessions/{session_id}/current-visit/prepare")
def prepare_current_visit_release(session_id: UUID, body: PrepareReleaseCommand, actor: StaffActor = Depends(_ADVISOR_OR_ADMIN), db: Session = Depends(get_db)):
    require_current_visit_release_enabled()
    inspection = _release_session(session_id, actor, db)
    _assert_release_eligible(inspection, db)
    owner_id = body.human_owner_user_id or actor.user_id
    owner = db.query(User).filter(User.id == owner_id, User.shop_id == actor.shop_id, User.active.is_(True)).one_or_none()
    if not owner or owner.role not in {UserRole.advisor, UserRole.admin}:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Select an active advisor or administrator as the named customer owner")
    release = _locked_release(inspection, db) if inspection.current_visit_release else None
    if release and release.state == "active":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Revoke the active customer view before preparing a new release")
    if not release:
        release = CurrentVisitRelease(
            shop_id=actor.shop_id,
            inspection_session_id=inspection.id,
            state="draft",
            human_owner_user_id=owner.id,
            source_template_sha256=inspection.template_source_sha256,
            source_advisor_reviewed_at=inspection.advisor_reviewed_at,
            source_advisor_reviewed_by_user_id=inspection.advisor_reviewed_by_user_id,
            prepared_by_user_id=actor.user_id,
            prepared_at=datetime.utcnow(),
        )
        db.add(release)
        db.flush()
    else:
        release.state = "draft"
        release.human_owner_user_id = owner.id
        release.prepared_by_user_id = actor.user_id
        release.prepared_at = datetime.utcnow()
        release.approved_at = None
        release.approved_by_user_id = None
        release.revoked_at = None
        release.revoked_by_user_id = None
        release.revocation_reason = None
    projection = _next_projection(release, inspection, actor, db, "shop_update_available")
    _audit_release(db, inspection=inspection, release=release, actor=actor, action="prepared", projection=projection)
    db.commit()
    return _release_summary(inspection, actor, db)


@router.post("/sessions/{session_id}/current-visit/approve")
def approve_current_visit_release(session_id: UUID, actor: StaffActor = Depends(_ADVISOR_OR_ADMIN), db: Session = Depends(get_db)):
    require_current_visit_release_enabled()
    _require_manager(actor, db)
    inspection = _release_session(session_id, actor, db)
    _assert_release_eligible(inspection, db)
    release = _locked_release(inspection, db)
    _assert_release_source(release, inspection)
    if release.state != "draft":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Only a draft Current Visit release can be approved")
    projection = (
        db.query(CurrentVisitProjectionRevision)
        .filter(CurrentVisitProjectionRevision.release_id == release.id, CurrentVisitProjectionRevision.state == "draft")
        .order_by(CurrentVisitProjectionRevision.revision.desc())
        .first()
    )
    if not projection:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Current Visit has no customer-safe projection awaiting approval")
    now = datetime.utcnow()
    projection.state = "manager_approved"
    projection.approved_by_user_id = actor.user_id
    projection.approved_at = now
    release.state = "manager_approved"
    release.approved_by_user_id = actor.user_id
    release.approved_at = now
    release.active_projection_revision = projection.revision
    _audit_release(db, inspection=inspection, release=release, actor=actor, action="manager_approved", projection=projection)
    db.commit()
    return _release_summary(inspection, actor, db)


@router.post("/sessions/{session_id}/current-visit/activate-counter")
def activate_counter_link(session_id: UUID, actor: StaffActor = Depends(_ADVISOR_OR_ADMIN), db: Session = Depends(get_db)):
    require_current_visit_release_enabled()
    require_current_visit_public_edge_verified()
    _require_manager(actor, db)
    inspection = _release_session(session_id, actor, db)
    release = _locked_release(inspection, db)
    _assert_release_eligible(inspection, db)
    _assert_release_source(release, inspection)
    if release.state != "manager_approved" or release.active_projection_revision is None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Manager approval is required before activating a counter view")
    now = datetime.utcnow()
    if db.query(CustomerPublicLink).filter(CustomerPublicLink.release_id == release.id, CustomerPublicLink.issued_at >= now - timedelta(hours=24)).count() >= 3:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Counter link issuance limit reached; contact a manager before retrying")
    if db.query(CustomerPublicLink).filter(CustomerPublicLink.issued_by_user_id == actor.user_id, CustomerPublicLink.issued_at >= now - timedelta(hours=1)).count() >= 10:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Counter link issuance limit reached; try again later")
    for old_link in db.query(CustomerPublicLink).filter(CustomerPublicLink.release_id == release.id, CustomerPublicLink.state == "active").with_for_update().all():
        old_link.state = "revoked"
        old_link.revoked_at = now
        old_link.revoked_by_user_id = actor.user_id
        old_link.revocation_reason = "rotated"
    secret = new_public_secret()
    link = CustomerPublicLink(
        release_id=release.id,
        purpose="counter",
        secret_hmac=public_link_hmac(secret),
        hmac_key_id=public_link_hmac_key_id(),
        state="active",
        issued_by_user_id=actor.user_id,
        issued_at=now,
        expires_at=now + _COUNTER_LINK_TTL,
    )
    db.add(link)
    release.state = "active"
    _audit_release(db, inspection=inspection, release=release, actor=actor, action="counter_link_issued")
    db.commit()
    return {
        "url": f"{public_glovebox_origin()}/v#{secret}",
        "expires_at": _utc(link.expires_at),
        "message": "Counter view activated. The link is view-only and is shown once; it was not texted or emailed.",
    }


@router.post("/sessions/{session_id}/current-visit/revoke")
def revoke_current_visit_release(session_id: UUID, body: RevokeReleaseCommand, actor: StaffActor = Depends(_ADVISOR_OR_ADMIN), db: Session = Depends(get_db)):
    require_current_visit_release_enabled()
    _require_manager(actor, db)
    inspection = _release_session(session_id, actor, db)
    release = _locked_release(inspection, db)
    now = datetime.utcnow()
    for link in db.query(CustomerPublicLink).filter(CustomerPublicLink.release_id == release.id, CustomerPublicLink.state == "active").with_for_update().all():
        link.state = "revoked"
        link.revoked_at = now
        link.revoked_by_user_id = actor.user_id
        link.revocation_reason = body.reason
    release.state = "revoked"
    release.revoked_at = now
    release.revoked_by_user_id = actor.user_id
    release.revocation_reason = body.reason
    _audit_release(db, inspection=inspection, release=release, actor=actor, action="revoked", reason_code=body.reason)
    db.commit()
    return _release_summary(inspection, actor, db)


@router.post("/sessions/{session_id}/current-visit/progress/request")
def request_progress_update(session_id: UUID, body: ProgressRequestCommand, actor: StaffActor = Depends(_ADVISOR_OR_ADMIN), db: Session = Depends(get_db)):
    require_current_visit_release_enabled()
    inspection = _release_session(session_id, actor, db)
    release = _locked_release(inspection, db)
    _assert_release_eligible(inspection, db)
    _assert_release_source(release, inspection)
    if release.state not in {"manager_approved", "active"}:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Manager approval is required before a customer progress update can be prepared")
    projection = _next_projection(release, inspection, actor, db, body.status_code)
    _audit_release(db, inspection=inspection, release=release, actor=actor, action="progress_requested", projection=projection)
    db.commit()
    return _release_summary(inspection, actor, db)


@router.post("/sessions/{session_id}/current-visit/progress/approve")
def approve_progress_update(session_id: UUID, actor: StaffActor = Depends(_ADVISOR_OR_ADMIN), db: Session = Depends(get_db)):
    require_current_visit_release_enabled()
    _require_manager(actor, db)
    inspection = _release_session(session_id, actor, db)
    release = _locked_release(inspection, db)
    _assert_release_eligible(inspection, db)
    _assert_release_source(release, inspection)
    projection = (
        db.query(CurrentVisitProjectionRevision)
        .filter(CurrentVisitProjectionRevision.release_id == release.id, CurrentVisitProjectionRevision.state == "draft")
        .order_by(CurrentVisitProjectionRevision.revision.desc())
        .first()
    )
    if not projection:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="No customer progress update is awaiting manager approval")
    projection.state = "manager_approved"
    projection.approved_at = datetime.utcnow()
    projection.approved_by_user_id = actor.user_id
    release.active_projection_revision = projection.revision
    _audit_release(db, inspection=inspection, release=release, actor=actor, action="progress_manager_approved", projection=projection)
    db.commit()
    return _release_summary(inspection, actor, db)


def _public_failure() -> None:
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Visit link is unavailable")


def _audit(db: Session, *, link_id: UUID | None, outcome: str, ip_hmac: str, now: datetime) -> None:
    db.add(CustomerPublicAccessAudit(link_id=link_id, outcome=outcome, client_ip_hmac=ip_hmac, occurred_at=now, expires_at=now + _PUBLIC_AUDIT_RETENTION))


def _window_start(now: datetime, seconds: int) -> datetime:
    return datetime.utcfromtimestamp(int(now.timestamp() // seconds) * seconds)


def _consume_rate_bucket(db: Session, *, scope: Literal["ip", "link"], key_hmac: str, now: datetime, window_seconds: int, limit: int) -> bool:
    window_started_at = _window_start(now, window_seconds)
    count = db.execute(text("""
        INSERT INTO current_visit_rate_limit_buckets (id, scope, key_hmac, window_started_at, request_count, expires_at)
        VALUES (:id, :scope, :key_hmac, :window_started_at, 1, :expires_at)
        ON CONFLICT (scope, key_hmac, window_started_at)
        DO UPDATE SET request_count = current_visit_rate_limit_buckets.request_count + 1
        RETURNING request_count
    """), {
        "id": uuid4(),
        "scope": scope,
        "key_hmac": key_hmac,
        "window_started_at": window_started_at,
        "expires_at": window_started_at + timedelta(seconds=window_seconds + 300),
    }).scalar_one()
    return int(count) <= limit


def prune_expired_current_visit_records(db: Session, now: datetime | None = None) -> dict[str, int]:
    """Delete short-lived public rate/audit data; safe to call from the existing maintenance loop."""
    now = now or datetime.utcnow()
    bucket_count = db.query(CurrentVisitRateLimitBucket).filter(CurrentVisitRateLimitBucket.expires_at < now).delete(synchronize_session=False)
    audit_count = db.query(CustomerPublicAccessAudit).filter(CustomerPublicAccessAudit.expires_at < now).delete(synchronize_session=False)
    db.commit()
    return {"rate_buckets": bucket_count, "public_audits": audit_count}


@router.post("/public/current-visit/resolve")
def resolve_public_current_visit(body: PublicResolveCommand, request: Request, db: Session = Depends(get_db)):
    """Resolve a link secret supplied in a POST body so backend access logs never receive the secret in a path."""
    try:
        if not current_visit_release_enabled() or not current_visit_public_edge_verified() or not valid_public_secret(body.secret):
            _public_failure()
        if request.headers.get("x-workbai-public-edge-verified") != "1" or not valid_public_resolver_key(request.headers.get("x-workbai-public-resolver-key")):
            _public_failure()
        client_ip_hmac = public_access_hmac(trusted_client_ip(request.headers.get("x-workbai-public-client-ip")))
        now = datetime.utcnow()
        if not _consume_rate_bucket(db, scope="ip", key_hmac=client_ip_hmac, now=now, window_seconds=60, limit=10):
            _audit(db, link_id=None, outcome="rate_limited", ip_hmac=client_ip_hmac, now=now)
            db.commit()
            raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Visit link is unavailable")
        link = db.query(CustomerPublicLink).filter(CustomerPublicLink.secret_hmac == public_link_hmac(body.secret)).one_or_none()
        if not link or link.state != "active" or link.expires_at <= now:
            if link and link.state == "active" and link.expires_at <= now:
                link.state = "expired"
            _audit(db, link_id=link.id if link else None, outcome="unavailable", ip_hmac=client_ip_hmac, now=now)
            db.commit()
            _public_failure()
        if not _consume_rate_bucket(db, scope="link", key_hmac=public_access_hmac(f"link:{link.id}"), now=now, window_seconds=300, limit=30):
            _audit(db, link_id=link.id, outcome="rate_limited", ip_hmac=client_ip_hmac, now=now)
            db.commit()
            raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Visit link is unavailable")
        release = db.get(CurrentVisitRelease, link.release_id)
        if not release or release.state != "active" or release.active_projection_revision is None:
            _audit(db, link_id=link.id, outcome="unavailable", ip_hmac=client_ip_hmac, now=now)
            db.commit()
            _public_failure()
        projection = (
            db.query(CurrentVisitProjectionRevision)
            .filter(
                CurrentVisitProjectionRevision.release_id == release.id,
                CurrentVisitProjectionRevision.revision == release.active_projection_revision,
                CurrentVisitProjectionRevision.state == "manager_approved",
            )
            .one_or_none()
        )
        if not projection:
            _audit(db, link_id=link.id, outcome="unavailable", ip_hmac=client_ip_hmac, now=now)
            db.commit()
            _public_failure()
        payload = projection.payload_json
        safe_payload = {
            "schema_version": 1,
            "vehicle_label": str(payload.get("vehicle_label", "Your vehicle"))[:160],
            "shop": {
                "display_name": str(payload.get("shop", {}).get("display_name", "Service team"))[:160],
                "support_phone": str(payload.get("shop", {}).get("support_phone", ""))[:32],
            },
            "visit": {
                "status_code": str(payload.get("visit", {}).get("status_code", "shop_update_available")),
                "status_label": str(payload.get("visit", {}).get("status_label", "Your service team has an update."))[:280],
                "updated_at": str(payload.get("visit", {}).get("updated_at", ""))[:40],
            },
            "contact": {"primary_action_label": "Call the shop"},
            "access_expires_at": _utc(link.expires_at),
            "disclosure": "This page provides a limited update about your current visit. It is not an estimate, diagnosis, approval request, invoice, or authorization for work.",
        }
        link.last_accessed_at = now
        _audit(db, link_id=link.id, outcome="viewed", ip_hmac=client_ip_hmac, now=now)
        db.commit()
        return safe_payload
    except HTTPException as exc:
        if exc.status_code in {status.HTTP_404_NOT_FOUND, status.HTTP_429_TOO_MANY_REQUESTS}:
            raise
        _public_failure()
