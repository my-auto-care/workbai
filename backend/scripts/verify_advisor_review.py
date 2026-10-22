"""Isolated acceptance harness for the Phase 1.2 advisor review workbench.

Run only against a disposable database with the current application source mounted.
"""

from threading import Barrier, Thread
from datetime import datetime

from fastapi.testclient import TestClient

from app.auth import StaffActor, get_current_actor
from app.db.models import ChecklistTemplate, Shop, TemplateLifecycleStatus, User, UserRole
from app.db.session import SessionLocal
from app.main import app


def as_actor(user_id, shop_id, role, name):
    app.dependency_overrides[get_current_actor] = lambda: StaffActor(
        user_id, shop_id, role, name, f"auth0|{name.lower().replace(' ', '-')}"
    )


with SessionLocal() as db:
    shop = Shop(name="Advisor Review Shop")
    other_shop = Shop(name="Other Shop")
    db.add_all([shop, other_shop])
    db.flush()
    advisor = User(shop_id=shop.id, auth0_id="auth0|advisor", role=UserRole.advisor, name="Advisor", active=True)
    technician = User(shop_id=shop.id, auth0_id="auth0|tech", role=UserRole.technician, name="Technician", active=True)
    other_advisor = User(shop_id=other_shop.id, auth0_id="auth0|other-advisor", role=UserRole.advisor, name="Other advisor", active=True)
    db.add_all([advisor, technician, other_advisor])
    db.flush()
    template = ChecklistTemplate(
        name="Provisional reviewer template",
        version=1,
        lifecycle_status=TemplateLifecycleStatus.approved,
        is_provisional=False,
        active_for_new_visits=True,
        source_reference="isolated advisor-review acceptance fixture",
        source_sha256="a" * 64,
        approved_at=datetime.utcnow(),
        approved_by_user_id=advisor.id,
        items={
            "name": "Provisional reviewer template",
            "sections": [{
                "id": "brakes",
                "name": "Brakes",
                "items": [
                    {"id": "brk_001", "name": "Front pad depth", "type": "measurement", "unit": "mm"},
                    {"id": "brk_002", "name": "Rotor condition", "type": "condition", "options": ["Good", "Worn"]},
                ],
            }],
        },
    )
    db.add(template)
    db.commit()
    advisor_id, tech_id, other_advisor_id = advisor.id, technician.id, other_advisor.id
    shop_id, other_shop_id, template_id = shop.id, other_shop.id, template.id

with TestClient(app) as client:
    as_actor(advisor_id, shop_id, UserRole.advisor, "Advisor")
    # The legacy creation method is deliberately not available: the resource path permits GET only.
    assert client.post("/sessions", json={}).status_code == 405
    created = client.post(
        "/check-in/sessions",
        json={
            "vehicle_year": 2023,
            "vehicle_make": "Honda",
            "vehicle_model": "Accord",
            "vehicle_vin": "1HGCW2F61PA123456",
            "vehicle_mileage": 18300,
            "customer_concern": "Brake pedal vibration on a highway stop.",
            "presence_mode": "dropoff",
            "assigned_technician_id": str(tech_id),
        },
    )
    assert created.status_code == 201, created.text
    session_id = created.json()["id"]
    assert client.get(f"/sessions/{session_id}/advisor-review").status_code == 409

    as_actor(tech_id, shop_id, UserRole.technician, "Technician")
    assert client.post(f"/sessions/{session_id}/start").status_code == 200
    assert client.put(f"/sessions/{session_id}/inspection-items/brk_001", json={"condition": "na", "note": "Not applicable"}).status_code == 422
    assert client.put(f"/sessions/{session_id}/inspection-items/brk_002", json={"condition": "poor", "selected_option": "Invented", "note": "Invalid option"}).status_code == 422
    assert client.post(f"/sessions/{session_id}/submit-inspection").status_code == 422
    assert client.put(f"/sessions/{session_id}/inspection-items/brk_001", json={"condition": "good", "measurement": "7"}).status_code == 200
    assert client.put(f"/sessions/{session_id}/inspection-items/brk_002", json={"condition": "poor", "selected_option": "Worn", "note": "Rotor surface is visibly grooved."}).status_code == 200
    assert client.post(f"/sessions/{session_id}/submit-inspection").status_code == 200
    assert client.get(f"/sessions/{session_id}/advisor-review").status_code == 403

    as_actor(other_advisor_id, other_shop_id, UserRole.advisor, "Other advisor")
    assert client.get(f"/sessions/{session_id}/advisor-review").status_code == 404

    as_actor(advisor_id, shop_id, UserRole.advisor, "Advisor")
    workspace = client.get(f"/sessions/{session_id}/advisor-review")
    assert workspace.status_code == 200, workspace.text
    assert workspace.json()["summary"] == {"attention_count": 1, "decisions_saved": 0, "good_count": 1, "na_count": 0}
    assert workspace.json()["customer_release_available"] is False
    assert workspace.json()["current_visit_readiness"] == {
        "ready_for_future_customer_access": False,
        "customer_access_enabled": False,
        "reasons": ["advisor_review_incomplete", "advisor_review_audit_missing"],
    }
    assert client.post(f"/sessions/{session_id}/advisor-review/complete").status_code == 422
    saved = client.put(
        f"/sessions/{session_id}/advisor-review/items/brk_002",
        json={
            "disposition": "safety",
            "rationale": "Confirm the observed grooving with the customer before any estimate is prepared.",
        },
    )
    assert saved.status_code == 200, saved.text
    barrier = Barrier(2)
    completion_statuses: list[int] = []
    completion_errors: list[Exception] = []

    def complete_at_once():
        try:
            with TestClient(app) as concurrent_client:
                barrier.wait(timeout=5)
                completion_statuses.append(concurrent_client.post(f"/sessions/{session_id}/advisor-review/complete").status_code)
        except Exception as error:  # pragma: no cover - assertion below reports any thread failure.
            completion_errors.append(error)

    first = Thread(target=complete_at_once)
    second = Thread(target=complete_at_once)
    first.start(); second.start(); first.join(); second.join()
    assert not completion_errors, completion_errors
    assert sorted(completion_statuses) == [200, 409], completion_statuses
    completed = client.get(f"/sessions/{session_id}/advisor-review")
    assert completed.status_code == 200 and completed.json()["session"]["status"] == "advisor_reviewed", completed.text
    assert completed.json()["customer_release_available"] is False
    assert completed.json()["current_visit_readiness"] == {
        "ready_for_future_customer_access": True,
        "customer_access_enabled": False,
        "reasons": [],
    }
    assert client.put(f"/sessions/{session_id}/advisor-review/items/brk_002", json={"disposition": "monitor", "rationale": "Attempted post-review rewrite."}).status_code == 409

    as_actor(tech_id, shop_id, UserRole.technician, "Technician")
    assert client.put(f"/sessions/{session_id}/inspection-items/brk_002", json={"condition": "good"}).status_code == 409

app.dependency_overrides.clear()
print("PASS: advisor review is submission-gated, role/shop scoped, requires complete human triage, and locks without customer-facing effects")
