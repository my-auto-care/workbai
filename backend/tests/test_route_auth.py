"""Every route requires a credential, and the formerly open routes are scoped."""

import re
import uuid
from types import SimpleNamespace

import pytest
from fastapi.routing import APIRoute

import app.api.transcript_processor as transcript_module
import app.api.vehicle_intel as intel_module
import app.api.vehicle_lookup as lookup_module
from app.db.models import InspectionSession, SessionStatus, Shop
from app.features import feature_enabled
from app.main import OPTIONAL_ROUTER_FLAGS, create_app

# Routes that are public on purpose, with what an anonymous caller gets.
PUBLIC_ROUTES = {
    ("GET", "/health"): {200},
    # Stripe signature is its credential (see test_stripe_webhook.py).
    ("POST", "/billing/webhook"): {400},
    # Current Visit counter view: default-off flags + edge header + resolver secret.
    ("POST", "/public/current-visit/resolve"): {404, 422},
}
# Routes the voice worker's service credential may reach (each still scoped).
VOICE_AGENT_ROUTES = {
    ("GET", "/sessions/{session_id}"),
    ("POST", "/sessions/{session_id}/findings"),
    ("POST", "/sessions/{session_id}/complete"),
    ("GET", "/checklists/{checklist_id}"),
    ("POST", "/vehicle-intelligence"),
    ("POST", "/sessions/{session_id}/vehicle-intelligence"),
}


def _all_routes():
    app = create_app()
    for route in app.routes:
        if isinstance(route, APIRoute):
            for method in sorted(route.methods - {"HEAD", "OPTIONS"}):
                yield method, route.path


def _concrete(path: str) -> str:
    return re.sub(r"\{[^}]+\}", str(uuid.uuid4()), path)


ROUTES = sorted(set(_all_routes()))


def test_route_inventory_includes_every_optional_router():
    paths = {path for _, path in ROUTES}
    for expected in ("/voice/token", "/vehicle/decode-vin", "/vehicle-intelligence", "/sessions/{session_id}/process-transcript", "/billing/create-customer", "/sessions"):
        assert expected in paths, expected


@pytest.mark.parametrize("method,path", ROUTES)
def test_anonymous_callers_are_refused_everywhere(client, world, method, path):
    response = client.request(method, _concrete(path), json={})
    expected = PUBLIC_ROUTES.get((method, path), {401})
    assert response.status_code in expected, (method, path, response.status_code, response.text[:200])


@pytest.mark.parametrize("method,path", ROUTES)
def test_voice_agent_credential_only_reaches_its_routes(client, world, agent_headers, method, path):
    response = client.request(method, _concrete(path), json={}, headers=agent_headers)
    if (method, path) in VOICE_AGENT_ROUTES:
        assert response.status_code != 401, (method, path)
    elif (method, path) in PUBLIC_ROUTES:
        assert response.status_code in PUBLIC_ROUTES[(method, path)]
    else:
        assert response.status_code == 401, (method, path, response.status_code)


# --- flags -----------------------------------------------------------------------


def test_optional_routers_default_on_and_can_be_switched_off(monkeypatch):
    for name in OPTIONAL_ROUTER_FLAGS:
        monkeypatch.delenv(name, raising=False)
    paths = {route.path for route in create_app().routes}
    assert {"/voice/token", "/vehicle/ocr-vin", "/vehicle-intelligence", "/billing/webhook"} <= paths
    for name in OPTIONAL_ROUTER_FLAGS:
        monkeypatch.setenv(name, "false")
    paths = {route.path for route in create_app().routes}
    assert not {"/voice/token", "/vehicle/ocr-vin", "/vehicle-intelligence", "/billing/webhook"} & paths


@pytest.mark.parametrize("raw,expected", [(None, True), ("", True), ("true", True), ("ON", True), ("false", False), ("0", False), ("nope", False)])
def test_feature_flag_parsing(monkeypatch, raw, expected):
    if raw is None:
        monkeypatch.delenv("WORKBAI_TEST_FLAG", raising=False)
    else:
        monkeypatch.setenv("WORKBAI_TEST_FLAG", raw)
    assert feature_enabled("WORKBAI_TEST_FLAG", True) is expected


# --- transcript ------------------------------------------------------------------


@pytest.fixture
def no_paid_calls(monkeypatch):
    def boom(*args, **kwargs):
        raise AssertionError("a paid upstream API was called")

    async def aboom(*args, **kwargs):
        raise AssertionError("a paid upstream API was called")

    monkeypatch.setattr(transcript_module, "_upload_to_assemblyai", aboom)
    monkeypatch.setattr(intel_module, "_generate_vehicle_intelligence", aboom)
    monkeypatch.setattr(lookup_module, "_ocr_plate", aboom)
    monkeypatch.setattr(lookup_module, "_vdb_ocr_vin", aboom)
    monkeypatch.setattr(lookup_module, "decode_vin_full", aboom)
    return boom


AUDIO = {"audio": ("inspection.m4a", b"\x00" * 64, "audio/aac")}


def test_transcript_unknown_session_is_404_and_creates_nothing(client, world, bearer, db, no_paid_calls):
    before = db.query(InspectionSession).count()
    response = client.post(f"/sessions/{uuid.uuid4()}/process-transcript", files=AUDIO, headers=bearer(world.tech_a1))
    assert response.status_code == 404
    assert db.query(InspectionSession).count() == before


def test_transcript_other_shop_or_unassigned_is_refused(client, world, bearer, no_paid_calls):
    other_shop = world.legacy_session(world.tech_b)
    assert client.post(f"/sessions/{other_shop.id}/process-transcript", files=AUDIO, headers=bearer(world.tech_a1)).status_code == 404
    colleague = world.legacy_session(world.tech_a2)
    assert client.post(f"/sessions/{colleague.id}/process-transcript", files=AUDIO, headers=bearer(world.tech_a1)).status_code == 403
    assert client.post(f"/sessions/{colleague.id}/process-transcript", files=AUDIO, headers=bearer(world.advisor_a)).status_code == 403


def test_transcript_refuses_template_and_inactive_sessions(client, world, bearer, no_paid_calls):
    template = world.template_session(world.tech_a1, world.template_a, status=SessionStatus.in_progress)
    assert client.post(f"/sessions/{template.id}/process-transcript", files=AUDIO, headers=bearer(world.tech_a1)).status_code == 409
    done = world.legacy_session(world.tech_a1, status=SessionStatus.completed)
    assert client.post(f"/sessions/{done.id}/process-transcript", files=AUDIO, headers=bearer(world.tech_a1)).status_code == 409


def test_transcript_for_the_assigned_technician_reaches_transcription(client, world, bearer, monkeypatch):
    session = world.legacy_session(world.tech_a1)
    monkeypatch.setattr(transcript_module, "ASSEMBLYAI_API_KEY", None)
    # Authorised and in scope; stops at the missing provider key, not at auth.
    assert client.post(f"/sessions/{session.id}/process-transcript", files=AUDIO, headers=bearer(world.tech_a1)).status_code == 503


# --- vehicle intelligence ----------------------------------------------------------


@pytest.fixture
def fake_intel(monkeypatch):
    calls = []

    async def fake(body):
        calls.append(body)
        return {"vehicle": {"year": body.year}}

    monkeypatch.setattr(intel_module, "_generate_vehicle_intelligence", fake)
    return calls


def test_vehicle_intelligence_for_staff(client, world, bearer, fake_intel):
    body = {"year": 2017, "make": "Toyota", "model": "Highlander"}
    assert client.post("/vehicle-intelligence", json=body, headers=bearer(world.advisor_a)).status_code == 200
    other = world.legacy_session(world.tech_b)
    assert client.post("/vehicle-intelligence", json={**body, "session_id": str(other.id)}, headers=bearer(world.advisor_a)).status_code == 404
    assert len(fake_intel) == 1


def test_vehicle_intelligence_for_the_voice_agent_needs_its_active_session(client, world, agent_headers, fake_intel):
    body = {"year": 2017, "make": "Toyota", "model": "Highlander"}
    assert client.post("/vehicle-intelligence", json=body, headers=agent_headers).status_code == 422
    inactive = world.legacy_session(world.tech_a1, status=SessionStatus.completed)
    assert client.post("/vehicle-intelligence", json={**body, "session_id": str(inactive.id)}, headers=agent_headers).status_code == 404
    active = world.legacy_session(world.tech_a1)
    assert client.post("/vehicle-intelligence", json={**body, "session_id": str(active.id)}, headers=agent_headers).status_code == 200
    assert client.post(f"/sessions/{active.id}/vehicle-intelligence", headers=agent_headers).status_code == 200
    assert len(fake_intel) == 2


def test_vehicle_intelligence_provider_errors_are_not_echoed(client, world, bearer, monkeypatch):
    class Exploding:
        def __init__(self, *args, **kwargs):
            self.messages = SimpleNamespace(create=self.create)

        def create(self, **kwargs):
            raise RuntimeError("org-secret-billing-detail")

    monkeypatch.setattr(intel_module, "ANTHROPIC_API_KEY", "sk-ant-test")
    monkeypatch.setattr(intel_module.anthropic, "Anthropic", Exploding)
    response = client.post("/vehicle-intelligence", json={"year": 2017, "make": "Toyota", "model": "Highlander"}, headers=bearer(world.tech_a1))
    assert response.status_code == 502
    assert "org-secret" not in response.text


# --- vehicle lookup --------------------------------------------------------------------


def test_vehicle_lookup_needs_active_staff(client, world, bearer, monkeypatch, no_paid_calls):
    assert client.post("/vehicle/decode-vin", data={"vin": "5TDJZRFH0HS123456"}).status_code == 401
    assert client.post("/vehicle/decode-vin", data={"vin": "5TDJZRFH0HS123456"}, headers=bearer(world.inactive_tech_a)).status_code == 403

    async def fake_decode(vin):
        return {"vehicle": {"vin": vin}}

    monkeypatch.setattr(lookup_module, "decode_vin_full", fake_decode)
    response = client.post("/vehicle/decode-vin", data={"vin": "5TDJZRFH0HS123456"}, headers=bearer(world.tech_a1))
    assert response.status_code == 200, response.text


# --- billing -------------------------------------------------------------------------------


def test_billing_is_admin_only(client, world, bearer, no_paid_calls):
    for user in (world.tech_a1, world.advisor_a):
        assert client.get(f"/billing/subscription/{world.shop_a.id}", headers=bearer(user)).status_code == 403
        assert client.post("/billing/create-customer", json={"email": "a@b.co", "name": "A"}, headers=bearer(user)).status_code == 403


def test_billing_never_acts_on_another_shop(client, world, bearer, monkeypatch, db):
    created = []
    monkeypatch.setattr(
        "stripe.Customer.create",
        lambda **kwargs: created.append(kwargs) or SimpleNamespace(id="cus_test_a"),
    )
    headers = bearer(world.admin_a)
    assert client.get(f"/billing/subscription/{world.shop_b.id}", headers=headers).status_code == 404
    assert client.post("/billing/create-customer", json={"shop_id": str(world.shop_b.id), "email": "a@b.co", "name": "A"}, headers=headers).status_code == 403
    assert created == []

    ok = client.post("/billing/create-customer", json={"email": "a@b.co", "name": "A"}, headers=headers)
    assert ok.status_code == 201, ok.text
    assert created[0]["metadata"] == {"shop_id": str(world.shop_a.id)}
    db.expire_all()
    assert db.get(Shop, world.shop_a.id).stripe_customer_id == "cus_test_a"
    assert db.get(Shop, world.shop_b.id).stripe_customer_id is None
    assert client.get(f"/billing/subscription/{world.shop_a.id}", headers=headers).json()["stripe_customer_id"] == "cus_test_a"


def test_subscription_uses_the_shops_own_stripe_customer(client, world, bearer, monkeypatch, db):
    db.get(Shop, world.shop_a.id).stripe_customer_id = "cus_mine"
    db.commit()
    seen = []
    monkeypatch.setattr(
        "stripe.Subscription.create",
        lambda **kwargs: seen.append(kwargs) or SimpleNamespace(id="sub_1", status="active"),
    )
    headers = bearer(world.admin_a)
    refused = client.post("/billing/create-subscription", json={"customer_id": "cus_someone_else", "price_id": "price_1"}, headers=headers)
    assert refused.status_code == 403
    ok = client.post("/billing/create-subscription", json={"price_id": "price_1"}, headers=headers)
    assert ok.status_code == 201, ok.text
    assert [call["customer"] for call in seen] == ["cus_mine"]
