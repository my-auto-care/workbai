"""Disposable acceptance harness for the feature-flagged Current Visit release domain.

Run only with an empty disposable database. It creates no network delivery and
never prints a contact destination or link secret.
"""

from __future__ import annotations

import os
from datetime import datetime

from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

os.environ.update({
    "WORKBAI_ENABLE_CURRENT_VISIT_RELEASE": "true",
    "WORKBAI_CURRENT_VISIT_EDGE_VERIFIED": "true",
    "WORKBAI_CONTACT_ENCRYPTION_KEY": Fernet.generate_key().decode(),
    "WORKBAI_CONTACT_ENCRYPTION_KEY_ID": "acceptance-fixture-v1",
    "WORKBAI_CONTACT_LOOKUP_HMAC_PEPPER": "contact-lookup-fixture-pepper",
    "WORKBAI_PUBLIC_LINK_HMAC_PEPPER": "link-fixture-pepper",
    "WORKBAI_PUBLIC_LINK_HMAC_KEY_ID": "link-fixture-v1",
    "WORKBAI_PUBLIC_ACCESS_AUDIT_PEPPER": "audit-fixture-pepper",
    "WORKBAI_PUBLIC_RESOLVER_SHARED_SECRET": "resolver-fixture-secret",
    "WORKBAI_PUBLIC_GLOVEBOX_ORIGIN": "https://test.workbay.autorepairsolutions.ai",
    "WORKBAI_PUBLIC_SUPPORT_PHONE": "+15551234567",
})

from app.auth import StaffActor, get_current_actor  # noqa: E402
from app.db.models import (  # noqa: E402
    ChecklistTemplate,
    CurrentVisitReleaseAudit,
    CustomerContactPoint,
    CustomerPublicLink,
    Shop,
    TemplateLifecycleStatus,
    User,
    UserRole,
)
from app.db.session import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402


def as_actor(user_id, shop_id, role, name):
    app.dependency_overrides[get_current_actor] = lambda: StaffActor(user_id, shop_id, role, name, f"auth0|{name.lower()}")


with SessionLocal() as db:
    shop = Shop(name="Current Visit Acceptance Shop")
    other_shop = Shop(name="Other Shop")
    db.add_all([shop, other_shop])
    db.flush()
    advisor = User(shop_id=shop.id, auth0_id="auth0|cv-advisor", role=UserRole.advisor, name="Advisor", active=True)
    manager = User(shop_id=shop.id, auth0_id="auth0|cv-manager", role=UserRole.admin, name="Manager", active=True)
    technician = User(shop_id=shop.id, auth0_id="auth0|cv-tech", role=UserRole.technician, name="Technician", active=True)
    other_advisor = User(shop_id=other_shop.id, auth0_id="auth0|cv-other", role=UserRole.advisor, name="Other", active=True)
    db.add_all([advisor, manager, technician, other_advisor])
    db.flush()
    template = ChecklistTemplate(
        name="Controlled acceptance template",
        version=1,
        lifecycle_status=TemplateLifecycleStatus.approved,
        is_provisional=False,
        active_for_new_visits=True,
        source_reference="current visit acceptance fixture",
        source_sha256="b" * 64,
        approved_at=datetime.utcnow(),
        approved_by_user_id=manager.id,
        items={"name": "Controlled acceptance template", "sections": [{"id": "safety", "name": "Safety", "items": [{"id": "safety_001", "name": "Fixture item", "type": "condition", "options": ["Good", "Needs attention"]}]}]},
    )
    db.add(template)
    db.commit()
    ids = {"shop": shop.id, "advisor": advisor.id, "manager": manager.id, "technician": technician.id, "other_shop": other_shop.id, "other_advisor": other_advisor.id}

with TestClient(app) as client:
    as_actor(ids["advisor"], ids["shop"], UserRole.advisor, "Advisor")
    created = client.post("/check-in/sessions", json={
        "vehicle_year": 2024,
        "vehicle_make": "Honda",
        "vehicle_model": "Accord",
        "vehicle_vin": "1HGCW2F61PA123456",
        "vehicle_mileage": 8200,
        "customer_concern": "Vibration during highway braking.",
        "presence_mode": "dropoff",
        "assigned_technician_id": str(ids["technician"]),
        "customer_contact": {
            "channel": "sms",
            "destination": "+15551234567",
            "current_visit_link_consent": "granted",
            "current_visit_progress_consent": "declined",
        },
    })
    assert created.status_code == 201, created.text
    assert created.json()["customer_contact_recorded"] is True
    session_id = created.json()["id"]
    with SessionLocal() as db:
        contact = db.query(CustomerContactPoint).one()
        assert "+15551234567" not in contact.encrypted_destination
        assert contact.verification_state == "unverified"

    as_actor(ids["technician"], ids["shop"], UserRole.technician, "Technician")
    assert client.post(f"/sessions/{session_id}/start").status_code == 200
    assert client.put(f"/sessions/{session_id}/inspection-items/safety_001", json={"condition": "good", "selected_option": "Good"}).status_code == 200
    assert client.post(f"/sessions/{session_id}/submit-inspection").status_code == 200

    as_actor(ids["advisor"], ids["shop"], UserRole.advisor, "Advisor")
    assert client.post(f"/sessions/{session_id}/advisor-review/complete").status_code == 200
    initial = client.get(f"/sessions/{session_id}/current-visit")
    assert initial.status_code == 200 and initial.json()["release"] is None, initial.text
    prepared = client.post(f"/sessions/{session_id}/current-visit/prepare", json={})
    assert prepared.status_code == 200 and prepared.json()["release"]["state"] == "draft", prepared.text
    assert client.post(f"/sessions/{session_id}/current-visit/approve").status_code == 403
    assert client.post(f"/sessions/{session_id}/current-visit/delivery", json={}).status_code == 404

    as_actor(ids["other_advisor"], ids["other_shop"], UserRole.advisor, "Other")
    assert client.get(f"/sessions/{session_id}/current-visit").status_code == 404

    as_actor(ids["manager"], ids["shop"], UserRole.admin, "Manager")
    assert client.post(f"/sessions/{session_id}/current-visit/approve").status_code == 403
    grant = client.put("/current-visit/manager-grants", json={"user_id": str(ids["manager"]), "active": True})
    assert grant.status_code == 200 and grant.json()["current_visit_manager"] is True, grant.text
    approved = client.post(f"/sessions/{session_id}/current-visit/approve")
    assert approved.status_code == 200 and approved.json()["release"]["state"] == "manager_approved", approved.text
    activated = client.post(f"/sessions/{session_id}/current-visit/activate-counter")
    assert activated.status_code == 200, activated.text
    link_url = activated.json()["url"]
    assert link_url.startswith("https://test.workbay.autorepairsolutions.ai/v#")
    secret = link_url.rsplit("#", 1)[1]
    with SessionLocal() as db:
        persisted_link = db.query(CustomerPublicLink).one()
        assert persisted_link.secret_hmac != secret

    public_headers = {"X-Workbai-Public-Client-IP": "203.0.113.8", "X-Workbai-Public-Resolver-Key": "resolver-fixture-secret", "X-Workbai-Public-Edge-Verified": "1"}
    assert client.post("/public/current-visit/resolve", json={"secret": secret}, headers={"X-Workbai-Public-Client-IP": "203.0.113.8", "X-Workbai-Public-Resolver-Key": "resolver-fixture-secret"}).status_code == 404
    assert client.post("/public/current-visit/resolve", json={"secret": secret}, headers={"X-Workbai-Public-Client-IP": "203.0.113.8", "X-Workbai-Public-Edge-Verified": "1"}).status_code == 404
    public = client.post("/public/current-visit/resolve", json={"secret": secret}, headers=public_headers)
    assert public.status_code == 200, public.text
    payload = public.json()
    assert set(payload) == {"schema_version", "vehicle_label", "shop", "visit", "contact", "access_expires_at", "disclosure"}
    rendered = str(payload).lower()
    for forbidden in ("vibration", "vin", "mileage", "finding", "rationale", "brake pedal"):
        assert forbidden not in rendered, forbidden

    as_actor(ids["advisor"], ids["shop"], UserRole.advisor, "Advisor")
    progress = client.post(f"/sessions/{session_id}/current-visit/progress/request", json={"status_code": "team_reviewing"})
    assert progress.status_code == 200 and progress.json()["release"]["pending_projection"]["status_code"] == "team_reviewing", progress.text
    as_actor(ids["manager"], ids["shop"], UserRole.admin, "Manager")
    published = client.post(f"/sessions/{session_id}/current-visit/progress/approve")
    assert published.status_code == 200 and published.json()["release"]["active_projection"]["status_code"] == "team_reviewing", published.text
    updated_public = client.post("/public/current-visit/resolve", json={"secret": secret}, headers=public_headers)
    assert updated_public.status_code == 200 and updated_public.json()["visit"]["status_code"] == "team_reviewing", updated_public.text

    revoked = client.post(f"/sessions/{session_id}/current-visit/revoke", json={"reason": "customer_requested"})
    assert revoked.status_code == 200 and revoked.json()["release"]["state"] == "revoked", revoked.text
    unavailable = client.post("/public/current-visit/resolve", json={"secret": secret}, headers=public_headers)
    assert unavailable.status_code == 404 and unavailable.json()["detail"] == "Visit link is unavailable", unavailable.text
    with SessionLocal() as db:
        assert db.query(CurrentVisitReleaseAudit).count() >= 6
        from app.db.models import CustomerPublicAccessAudit, CurrentVisitRateLimitBucket
        assert db.query(CustomerPublicAccessAudit).filter(CustomerPublicAccessAudit.expires_at > datetime.utcnow()).count() >= 1
        assert db.query(CurrentVisitRateLimitBucket).count() >= 2

app.dependency_overrides.clear()
print("PASS: optional consent capture, explicit manager delegation, source-bound approval, fragment-only counter link, edge-gated atomic public limits, bounded audit, public allowlist, manager-gated progress, revocation, and no delivery route")
