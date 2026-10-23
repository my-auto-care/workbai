"""The voice worker's service credential: works where it must, nowhere else."""

import hmac as real_hmac
import logging

import pytest

import app.auth as auth_module
from app.db.models import Finding, InspectionSession, SessionStatus
from app.voice import backend_client

from .conftest import VOICE_AGENT_TOKEN


def test_agent_can_run_an_active_legacy_inspection(client, world, agent_headers, db):
    session = world.legacy_session(world.tech_a1, template=world.template_a)

    read = client.get(f"/sessions/{session.id}", headers=agent_headers)
    assert read.status_code == 200, read.text
    assert read.json()["checklist_template_id"] == str(world.template_a.id)

    checklist = client.get(f"/checklists/{world.template_a.id}", headers=agent_headers)
    assert checklist.status_code == 200, checklist.text
    assert checklist.json()["items"]["sections"][0]["items"][0]["id"] == "brk_front"

    finding = client.post(
        f"/sessions/{session.id}/findings",
        json={"checklist_item_id": "brk_front", "transcript": "pads at 3mm", "condition": "poor"},
        headers=agent_headers,
    )
    assert finding.status_code == 201, finding.text
    assert db.query(Finding).filter(Finding.session_id == session.id).count() == 1

    done = client.post(f"/sessions/{session.id}/complete", headers=agent_headers)
    assert done.status_code == 200, done.text
    db.expire_all()
    assert db.get(InspectionSession, session.id).status == SessionStatus.completed


@pytest.mark.parametrize("status", [SessionStatus.pending, SessionStatus.completed, SessionStatus.abandoned])
def test_agent_cannot_touch_an_inactive_session(client, world, agent_headers, status):
    session = world.legacy_session(world.tech_a1, status=status)
    assert client.get(f"/sessions/{session.id}", headers=agent_headers).status_code == 404
    assert client.post(f"/sessions/{session.id}/findings", json={"transcript": "x"}, headers=agent_headers).status_code == 404


def test_agent_cannot_touch_a_template_driven_visit(client, world, agent_headers):
    session = world.template_session(world.tech_a1, world.template_a, status=SessionStatus.in_progress)
    assert client.get(f"/sessions/{session.id}", headers=agent_headers).status_code == 404
    assert client.post(f"/sessions/{session.id}/complete", headers=agent_headers).status_code == 404


def test_agent_cannot_read_a_checklist_no_active_inspection_uses(client, world, agent_headers):
    world.legacy_session(world.tech_a1, template=world.template_a)
    assert client.get(f"/checklists/{world.template_b.id}", headers=agent_headers).status_code == 404


def test_agent_cannot_list_or_write_anything_else(client, world, agent_headers):
    session = world.legacy_session(world.tech_a1, template=world.template_a)
    assert client.get("/sessions", headers=agent_headers).status_code == 401
    assert client.get("/checklists", headers=agent_headers).status_code == 401
    assert client.post(f"/checklists/{world.template_a.id}/retire", json={"confirm_retirement": True}, headers=agent_headers).status_code == 401
    assert client.get("/check-in/options", headers=agent_headers).status_code == 401
    assert client.post("/media/upload-url", json={"session_id": str(session.id), "filename": "a.jpg"}, headers=agent_headers).status_code == 401
    assert client.get(f"/sessions/{session.id}/report", headers=agent_headers).status_code == 401
    assert client.get(f"/billing/subscription/{world.shop_a.id}", headers=agent_headers).status_code == 401


def test_wrong_token_is_rejected(client, world):
    session = world.legacy_session(world.tech_a1)
    response = client.get(f"/sessions/{session.id}", headers={"X-Workbai-Service-Token": VOICE_AGENT_TOKEN[:-1] + "x"})
    assert response.status_code == 401


def test_credential_is_off_when_unset_or_short(client, world, monkeypatch):
    session = world.legacy_session(world.tech_a1)
    monkeypatch.delenv("WORKBAI_VOICE_AGENT_TOKEN")
    assert client.get(f"/sessions/{session.id}", headers={"X-Workbai-Service-Token": VOICE_AGENT_TOKEN}).status_code == 401
    assert client.get(f"/sessions/{session.id}", headers={"X-Workbai-Service-Token": ""}).status_code == 401
    monkeypatch.setenv("WORKBAI_VOICE_AGENT_TOKEN", "short-but-equal")
    assert client.get(f"/sessions/{session.id}", headers={"X-Workbai-Service-Token": "short-but-equal"}).status_code == 401


def test_staff_token_plus_service_token_is_rejected(client, world, bearer, agent_headers):
    session = world.legacy_session(world.tech_a1)
    headers = {**bearer(world.tech_a1), **agent_headers}
    assert client.get(f"/sessions/{session.id}", headers=headers).status_code == 401


def test_service_token_is_not_a_bearer_token(client, world):
    session = world.legacy_session(world.tech_a1)
    response = client.get(f"/sessions/{session.id}", headers={"Authorization": f"Bearer {VOICE_AGENT_TOKEN}"})
    assert response.status_code == 401


def test_token_is_compared_in_constant_time(client, world, agent_headers, monkeypatch):
    calls = []
    original = real_hmac.compare_digest

    def spy(a, b):
        calls.append((type(a), type(b)))
        return original(a, b)

    monkeypatch.setattr(auth_module.hmac, "compare_digest", spy)
    session = world.legacy_session(world.tech_a1)
    assert client.get(f"/sessions/{session.id}", headers=agent_headers).status_code == 200
    assert calls == [(bytes, bytes)]


def test_worker_client_sends_the_credential(monkeypatch):
    assert backend_client.SERVICE_TOKEN_HEADER == auth_module.SERVICE_TOKEN_HEADER
    assert backend_client.VOICE_AGENT_TOKEN_ENV == auth_module.VOICE_AGENT_TOKEN_ENV
    assert backend_client.service_headers() == {"X-Workbai-Service-Token": VOICE_AGENT_TOKEN}


def test_worker_client_logs_loudly_when_unconfigured(monkeypatch, caplog):
    monkeypatch.delenv("WORKBAI_VOICE_AGENT_TOKEN")
    with caplog.at_level(logging.ERROR, logger="workbay.voice"):
        assert backend_client.service_headers() == {}
    assert "WORKBAI_VOICE_AGENT_TOKEN is not set" in caplog.text


def test_worker_reads_sectioned_and_flat_checklists():
    from app.voice.agent import checklist_items

    assert [item["id"] for item in checklist_items({"sections": [{"items": [{"id": "a"}, {"id": "b"}]}]})] == ["a", "b"]
    assert [item["id"] for item in checklist_items({"items": [{"id": "x"}]})] == ["x"]
    assert checklist_items(None) == []
