"""Routes added in the Manus chain (42aa8db..b7f83a4): role, assignment and shop scope."""

import secrets

import pytest
from cryptography.fernet import Fernet

from app.db.models import SessionStatus

CHECKIN = {
    "vehicle_year": 2017,
    "vehicle_make": "Toyota",
    "vehicle_model": "Highlander",
    "customer_concern": "Grinding noise",
    "presence_mode": "dropoff",
}


@pytest.fixture
def customer_data(monkeypatch):
    monkeypatch.setenv("WORKBAI_CUSTOMER_DATA_ENCRYPTION_KEY", Fernet.generate_key().decode())
    monkeypatch.setenv("WORKBAI_CUSTOMER_DATA_ENCRYPTION_KEY_ID", "test-key-1")
    monkeypatch.setenv("WORKBAI_CUSTOMER_SEARCH_HMAC_PEPPER", secrets.token_hex(16))


# --- technician workspace -------------------------------------------------------


def test_technician_workspace_flow_is_assignment_scoped(client, world, bearer):
    session = world.template_session(world.tech_a1, world.template_a)
    tech, colleague, other_shop = bearer(world.tech_a1), bearer(world.tech_a2), bearer(world.tech_b)

    assert client.post(f"/sessions/{session.id}/start", headers=colleague).status_code == 403
    assert client.post(f"/sessions/{session.id}/start", headers=other_shop).status_code == 404
    assert client.post(f"/sessions/{session.id}/start", headers=tech).status_code == 200

    record = {"condition": "good"}
    assert client.put(f"/sessions/{session.id}/inspection-items/brk_front", json=record, headers=colleague).status_code == 403
    assert client.put(f"/sessions/{session.id}/inspection-items/brk_front", json=record, headers=other_shop).status_code == 404
    assert client.put(f"/sessions/{session.id}/inspection-items/brk_front", json=record, headers=bearer(world.advisor_a)).status_code == 403
    assert client.put(f"/sessions/{session.id}/inspection-items/brk_front", json={"condition": "poor", "note": "2mm left"}, headers=tech).status_code == 200
    assert client.put(f"/sessions/{session.id}/inspection-items/not_in_snapshot", json=record, headers=tech).status_code == 422
    assert client.post(f"/sessions/{session.id}/submit-inspection", headers=tech).status_code == 422  # brk_rear missing
    assert client.put(f"/sessions/{session.id}/inspection-items/brk_rear", json={"condition": "na", "note": "drums"}, headers=tech).status_code == 200
    submitted = client.post(f"/sessions/{session.id}/submit-inspection", headers=tech)
    assert submitted.status_code == 200, submitted.text
    assert submitted.json()["session"]["status"] == "submitted"


# --- advisor review -------------------------------------------------------------


def test_advisor_review_is_advisor_admin_and_shop_scoped(client, world, bearer, db):
    session = world.template_session(world.tech_a1, world.template_a, status=SessionStatus.in_progress)
    tech = bearer(world.tech_a1)
    client.put(f"/sessions/{session.id}/inspection-items/brk_front", json={"condition": "poor", "note": "2mm"}, headers=tech)
    client.put(f"/sessions/{session.id}/inspection-items/brk_rear", json={"condition": "good"}, headers=tech)
    assert client.post(f"/sessions/{session.id}/submit-inspection", headers=tech).status_code == 200

    decision = {"disposition": "safety", "rationale": "Replace front pads"}
    assert client.get(f"/sessions/{session.id}/advisor-review", headers=tech).status_code == 403
    assert client.put(f"/sessions/{session.id}/advisor-review/items/brk_front", json=decision, headers=bearer(world.admin_b)).status_code == 404
    assert client.post(f"/sessions/{session.id}/advisor-review/complete", headers=bearer(world.admin_b)).status_code == 404

    advisor = bearer(world.advisor_a)
    assert client.post(f"/sessions/{session.id}/advisor-review/complete", headers=advisor).status_code == 422
    assert client.put(f"/sessions/{session.id}/advisor-review/items/brk_front", json=decision, headers=advisor).status_code == 200
    done = client.post(f"/sessions/{session.id}/advisor-review/complete", headers=advisor)
    assert done.status_code == 200, done.text
    assert done.json()["current_visit_readiness"]["ready_for_future_customer_access"] is True


# --- Current Visit ----------------------------------------------------------------


def test_manager_grants_are_admin_only_and_shop_scoped(client, world, bearer, monkeypatch):
    monkeypatch.setenv("WORKBAI_ENABLE_CURRENT_VISIT_RELEASE", "true")
    assert client.get("/current-visit/manager-grants", headers=bearer(world.advisor_a)).status_code == 403
    listed = client.get("/current-visit/manager-grants", headers=bearer(world.admin_a)).json()
    assert {row["id"] for row in listed["users"]} == {str(world.advisor_a.id), str(world.admin_a.id)}
    cross = client.put("/current-visit/manager-grants", json={"user_id": str(world.admin_b.id), "active": True}, headers=bearer(world.admin_a))
    assert cross.status_code == 422
    own = client.put("/current-visit/manager-grants", json={"user_id": str(world.advisor_a.id), "active": True}, headers=bearer(world.admin_a))
    assert own.status_code == 200


def test_current_visit_commands_stay_off_by_default(client, world, bearer):
    session = world.template_session(world.tech_a1, world.template_a, status=SessionStatus.advisor_reviewed)
    assert client.post(f"/sessions/{session.id}/current-visit/prepare", json={}, headers=bearer(world.advisor_a)).status_code == 409


def test_public_resolver_is_unavailable_without_flags_edge_and_resolver_key(client, world, monkeypatch):
    body = {"secret": "A" * 43}
    assert client.post("/public/current-visit/resolve", json=body).status_code == 404
    monkeypatch.setenv("WORKBAI_ENABLE_CURRENT_VISIT_RELEASE", "true")
    monkeypatch.setenv("WORKBAI_CURRENT_VISIT_EDGE_VERIFIED", "true")
    monkeypatch.setenv("WORKBAI_PUBLIC_RESOLVER_SHARED_SECRET", secrets.token_hex(24))
    assert client.post("/public/current-visit/resolve", json=body).status_code == 404
    edge_only = {"X-Workbai-Public-Edge-Verified": "1", "X-Workbai-Public-Resolver-Key": "wrong-key"}
    assert client.post("/public/current-visit/resolve", json=body, headers=edge_only).status_code == 404
    # Raw latin-1 header bytes; compare_digest on that str used to raise TypeError (500).
    non_ascii = {"X-Workbai-Public-Edge-Verified": "1", "X-Workbai-Public-Resolver-Key": "caf\xe9".encode("latin-1")}
    assert client.post("/public/current-visit/resolve", json=body, headers=non_ascii).status_code == 404


# --- customer context -------------------------------------------------------------


def test_customer_records_never_cross_shops(client, world, bearer, customer_data):
    advisor_a, advisor_b = bearer(world.advisor_a), bearer(world.admin_b)
    created = client.post(
        "/check-in/sessions",
        json={
            **CHECKIN,
            "assigned_technician_id": str(world.tech_a1.id),
            "new_customer": {"display_name": "Pat Example", "contacts": [{"channel": "sms", "destination": "+15555550123"}]},
            "customer_vehicle_confirmation": True,
        },
        headers=advisor_a,
    )
    assert created.status_code == 201, created.text
    visit = created.json()

    assert client.post("/check-in/search", json={"query": "Pat"}, headers=advisor_a).json()["customers"]
    assert client.post("/check-in/search", json={"query": "Pat"}, headers=advisor_b).json()["customers"] == []
    assert client.post("/check-in/call-context", json={"caller_phone": "+15555550123"}, headers=advisor_a).json()["match_count"] == 1
    assert client.post("/check-in/call-context", json={"caller_phone": "+15555550123"}, headers=advisor_b).json()["match_count"] == 0
    assert client.get(f"/check-in/context?customer_id={visit['customer_id']}", headers=advisor_b).status_code == 404

    record = {
        "inspection_session_id": visit["id"],
        "source_type": "manual_note",
        "source_label": "Front desk note",
        "raw_content": "Customer mentioned the noise started last week.",
        "reviewed_excerpt": "Noise started last week.",
    }
    assert client.post("/check-in/context-records", json=record, headers=advisor_b).status_code == 404
    saved = client.post("/check-in/context-records", json=record, headers=advisor_a)
    assert saved.status_code == 201, saved.text
    assert client.get(f"/check-in/context-records/{saved.json()['id']}/raw", headers=advisor_b).status_code == 404
    assert client.get(f"/check-in/context-records/{saved.json()['id']}/raw", headers=bearer(world.tech_a1)).status_code == 403
    assert client.get(f"/check-in/context-records/{saved.json()['id']}/raw", headers=advisor_a).status_code == 200


def test_checkin_rejects_another_shops_customer_and_vehicle_ids(client, world, bearer, customer_data):
    created = client.post(
        "/check-in/sessions",
        json={**CHECKIN, "assigned_technician_id": str(world.tech_b.id), "new_customer": {"display_name": "B Person"}, "customer_vehicle_confirmation": True},
        headers=bearer(world.admin_b),
    ).json()
    body = {**CHECKIN, "assigned_technician_id": str(world.tech_a1.id), "customer_id": created["customer_id"], "customer_vehicle_confirmation": True}
    assert client.post("/check-in/sessions", json=body, headers=bearer(world.advisor_a)).status_code == 404
    body = {**CHECKIN, "assigned_technician_id": str(world.tech_a1.id), "vehicle_id": created["vehicle_id"]}
    assert client.post("/check-in/sessions", json=body, headers=bearer(world.advisor_a)).status_code == 404
