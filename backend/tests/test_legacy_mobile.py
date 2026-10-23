"""The mobile app's request bodies: legacy fields are accepted but never trusted."""

import jwt

from app.db.models import InspectionSession, SessionStatus

from .conftest import LIVEKIT_SECRET

# Exactly what released mobile builds send (mobile/lib/screens/new_session_screen.dart
# before this change): hard-coded shop, technician and checklist ids.
HARDCODED_SHOP = "00000000-0000-0000-0000-000000000001"
HARDCODED_TECH = "00000000-0000-0000-0000-000000000002"


def legacy_body(**overrides):
    body = {
        "shop_id": HARDCODED_SHOP,
        "technician_id": HARDCODED_TECH,
        "vehicle_year": 2017,
        "vehicle_make": "Toyota",
        "vehicle_model": "Highlander",
        "vehicle_vin": "5TDJZRFH0HS123456",
        "vehicle_mileage": 48000,
        "customer_concern": "Noise when braking",
    }
    body.update(overrides)
    return body


def test_legacy_mobile_body_creates_a_session_owned_by_the_token(client, world, bearer, db):
    response = client.post("/sessions", json=legacy_body(checklist_template_id=str(world.template_a.id)), headers=bearer(world.tech_a1))
    assert response.status_code == 201, response.text
    payload = response.json()
    assert payload["shop_id"] == str(world.shop_a.id)
    assert payload["technician_id"] == str(world.tech_a1.id)
    assert payload["assigned_technician_id"] == str(world.tech_a1.id)
    assert payload["status"] == "in_progress"
    assert payload["template_version"] is None
    session = db.get(InspectionSession, payload["id"])
    assert session.template_snapshot is None  # legacy: never enters advisor review / Current Visit


def test_body_shop_and_technician_ids_of_another_shop_are_ignored(client, world, bearer):
    body = legacy_body(shop_id=str(world.shop_b.id), technician_id=str(world.tech_b.id), assigned_technician_id=str(world.tech_b.id), status="pending")
    payload = client.post("/sessions", json=body, headers=bearer(world.tech_a1)).json()
    assert payload["shop_id"] == str(world.shop_a.id)
    assert payload["technician_id"] == str(world.tech_a1.id)
    assert payload["status"] == "in_progress"


def test_checklist_from_another_shop_is_refused(client, world, bearer):
    response = client.post("/sessions", json=legacy_body(checklist_template_id=str(world.template_b.id)), headers=bearer(world.tech_a1))
    assert response.status_code == 422


def test_without_a_checklist_the_shops_active_template_guides_the_voice_agent(client, world, bearer):
    payload = client.post("/sessions", json=legacy_body(), headers=bearer(world.tech_a1)).json()
    assert payload["checklist_template_id"] == str(world.template_a.id)


def test_unknown_fields_are_still_rejected(client, world, bearer):
    assert client.post("/sessions", json=legacy_body(is_admin=True), headers=bearer(world.tech_a1)).status_code == 422


def test_only_technicians_self_start(client, world, bearer):
    assert client.post("/sessions", json=legacy_body(), headers=bearer(world.advisor_a)).status_code == 403
    assert client.post("/sessions", json=legacy_body(), headers=bearer(world.admin_a)).status_code == 403


def test_legacy_path_can_be_switched_off(client, world, bearer, monkeypatch):
    monkeypatch.setenv("WORKBAI_ENABLE_LEGACY_MOBILE_SESSIONS", "false")
    assert client.post("/sessions", json=legacy_body(), headers=bearer(world.tech_a1)).status_code == 404


def test_voice_token_accepts_and_ignores_technician_name(client, world, bearer):
    session = world.legacy_session(world.tech_a1)
    response = client.post(
        "/voice/token",
        json={"session_id": str(session.id), "technician_name": "Somebody Else", "language": "en"},
        headers=bearer(world.tech_a1),
    )
    assert response.status_code == 200, response.text
    grant = jwt.decode(response.json()["token"], LIVEKIT_SECRET, algorithms=["HS256"], options={"verify_aud": False})
    assert grant["sub"] == str(world.tech_a1.id)
    assert grant["name"] == "Tech A1"
    assert grant["video"]["room"] == f"inspection-{session.id}"
    assert grant["roomConfig"]["agents"][0]["agentName"] == "workbai-inspection"


def test_voice_token_refuses_template_driven_visits(client, world, bearer):
    session = world.template_session(world.tech_a1, world.template_a, status=SessionStatus.in_progress)
    response = client.post("/voice/token", json={"session_id": str(session.id)}, headers=bearer(world.tech_a1))
    assert response.status_code == 409


def test_voice_token_for_another_technicians_session_is_refused(client, world, bearer):
    session = world.legacy_session(world.tech_a2)
    assert client.post("/voice/token", json={"session_id": str(session.id)}, headers=bearer(world.tech_a1)).status_code == 403


def test_complete_is_idempotent_for_a_legacy_session(client, world, bearer):
    session = world.legacy_session(world.tech_a1)
    first = client.post(f"/sessions/{session.id}/complete", headers=bearer(world.tech_a1))
    second = client.post(f"/sessions/{session.id}/complete", headers=bearer(world.tech_a1))
    assert (first.status_code, second.status_code) == (200, 200)
    assert second.json()["status"] == "completed"


def test_template_driven_visit_still_cannot_be_completed_by_the_technician(client, world, bearer):
    session = world.template_session(world.tech_a1, world.template_a, status=SessionStatus.in_progress)
    assert client.post(f"/sessions/{session.id}/complete", headers=bearer(world.tech_a1)).status_code == 409
