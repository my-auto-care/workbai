"""The 24-hour abandon timer runs from the technician's start, not from check-in."""

from datetime import datetime, timedelta

from app.api.sessions import expire_stale_sessions
from app.db.models import InspectionSession, SessionStatus


def _status(db, session_id):
    db.expire_all()
    return db.get(InspectionSession, session_id).status


def test_visit_checked_in_yesterday_and_started_now_is_not_abandoned(client, world, bearer, db):
    checked_in = datetime.utcnow() - timedelta(hours=30)
    session = world.template_session(world.tech_a1, world.template_a, status=SessionStatus.pending, started_at=checked_in)

    started = client.post(f"/sessions/{session.id}/start", headers=bearer(world.tech_a1))
    assert started.status_code == 200, started.text

    result = expire_stale_sessions(db)
    assert str(session.id) not in result["expired_ids"]
    assert _status(db, session.id) == SessionStatus.in_progress


def test_start_resets_started_at_to_the_start_time(client, world, bearer, db):
    checked_in = datetime.utcnow() - timedelta(hours=30)
    session = world.template_session(world.tech_a1, world.template_a, status=SessionStatus.pending, started_at=checked_in)
    client.post(f"/sessions/{session.id}/start", headers=bearer(world.tech_a1))
    db.expire_all()
    assert datetime.utcnow() - db.get(InspectionSession, session.id).started_at < timedelta(minutes=1)


def test_inspection_started_more_than_24_hours_ago_is_abandoned(world, db):
    stale = world.legacy_session(world.tech_a1, started_at=datetime.utcnow() - timedelta(hours=25))
    fresh = world.legacy_session(world.tech_a1, started_at=datetime.utcnow() - timedelta(hours=23))
    result = expire_stale_sessions(db)
    assert result["expired_ids"] == [str(stale.id)]
    assert _status(db, stale.id) == SessionStatus.abandoned
    assert _status(db, fresh.id) == SessionStatus.in_progress


def test_pending_and_submitted_visits_are_not_expired(world, db):
    long_ago = datetime.utcnow() - timedelta(days=3)
    pending = world.template_session(world.tech_a1, world.template_a, status=SessionStatus.pending, started_at=long_ago)
    submitted = world.template_session(world.tech_a1, world.template_a, status=SessionStatus.submitted, started_at=long_ago)
    assert expire_stale_sessions(db)["expired_count"] == 0
    assert _status(db, pending.id) == SessionStatus.pending
    assert _status(db, submitted.id) == SessionStatus.submitted


def test_scheduler_endpoint_requires_its_secret(client, world):
    assert client.post("/sessions/expire-stale").status_code == 401
    assert client.post("/sessions/expire-stale", headers={"X-Workbai-Scheduler-Secret": "wrong"}).status_code == 401
