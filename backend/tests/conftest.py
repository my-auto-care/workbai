"""Shared fixtures for the Workbai API tests.

Needs a THROWAWAY Postgres (the schema is dropped and rebuilt with Alembic):

    docker run -d --rm --name workbai-testpg -e POSTGRES_USER=workbai \\
      -e POSTGRES_PASSWORD=workbai -e POSTGRES_DB=workbai_test \\
      -p 127.0.0.1:55432:5432 --tmpfs /var/lib/postgresql/data postgres:16
    WORKBAI_TEST_DATABASE_URL=postgresql://workbai:workbai@127.0.0.1:55432/workbai_test \\
      python -m pytest tests/ -v
    docker rm -f -v workbai-testpg

No network: Auth0's JWKS endpoint is replaced by an in-process RSA key, and
Stripe / AssemblyAI / Anthropic / VehicleDatabases calls are patched in the
tests that reach them.
"""

from __future__ import annotations

import os
import secrets
import sys
import time
import uuid
from datetime import datetime
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

_TEST_DB = os.environ.get("WORKBAI_TEST_DATABASE_URL", "").strip()
if not _TEST_DB:
    raise pytest.UsageError(
        "WORKBAI_TEST_DATABASE_URL is not set. Point it at a throwaway Postgres whose database "
        "name ends in _test (see tests/conftest.py). The tests DROP and rebuild its schema."
    )

from sqlalchemy.engine import make_url  # noqa: E402

if not (make_url(_TEST_DB).database or "").endswith("_test"):
    raise pytest.UsageError("Refusing to run: the WORKBAI_TEST_DATABASE_URL database name must end in _test.")

AUTH0_DOMAIN = "workbai-tests.example.auth0.com"
AUTH0_AUDIENCE = "https://api.workbai.test"
VOICE_AGENT_TOKEN = secrets.token_hex(24)
STRIPE_WEBHOOK_SECRET = "whsec_" + secrets.token_hex(16)
LIVEKIT_SECRET = secrets.token_hex(32)

os.environ.update(
    {
        "DATABASE_URL": _TEST_DB,
        "AUTH0_DOMAIN": AUTH0_DOMAIN,
        "AUTH0_API_AUDIENCE": AUTH0_AUDIENCE,
        "WORKBAI_VOICE_AGENT_TOKEN": VOICE_AGENT_TOKEN,
        "STRIPE_WEBHOOK_SECRET": STRIPE_WEBHOOK_SECRET,
        "STRIPE_SECRET_KEY": "sk_test_not_used",
        "LIVEKIT_API_KEY": "lk-test",
        "LIVEKIT_API_SECRET": LIVEKIT_SECRET,
        "LIVEKIT_URL": "wss://livekit.invalid",
        "WORKBAI_SCHEDULER_SECRET": secrets.token_hex(24),
    }
)
# Defaults under test: optional routers unset (=> on); no real provider keys.
for _name in (
    "WORKBAI_ENABLE_VOICE_INSPECTION",
    "WORKBAI_ENABLE_VEHICLE_LOOKUP",
    "WORKBAI_ENABLE_EXPERIMENTAL_VEHICLE_AI",
    "WORKBAI_ENABLE_BILLING",
    "WORKBAI_ENABLE_LEGACY_MOBILE_SESSIONS",
    "WORKBAI_ENABLE_CURRENT_VISIT_RELEASE",
    "WORKBAI_CURRENT_VISIT_EDGE_VERIFIED",
    "ANTHROPIC_API_KEY",
    "ASSEMBLYAI_API_KEY",
    "PLATE_RECOGNIZER_TOKEN",
    "VEHICLE_DATABASES_KEY",
    "WORKBAI_CUSTOMER_DATA_ENCRYPTION_KEY",
    "WORKBAI_CUSTOMER_DATA_ENCRYPTION_KEY_ID",
    "WORKBAI_CUSTOMER_SEARCH_HMAC_PEPPER",
):
    os.environ.pop(_name, None)

import jwt  # noqa: E402
from cryptography.hazmat.primitives.asymmetric import rsa  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text  # noqa: E402

import app.auth as auth_module  # noqa: E402
from app.db.models import (  # noqa: E402
    ChecklistTemplate,
    InspectionSession,
    SessionStatus,
    Shop,
    TemplateLifecycleStatus,
    User,
    UserRole,
)
from app.db.session import SessionLocal, engine  # noqa: E402

KID = "workbai-test-key"
TEMPLATE_DOC = {
    "name": "Controlled test template",
    "sections": [
        {
            "id": "brakes",
            "name": "Brakes",
            "items": [
                {"id": "brk_front", "name": "Front pads", "type": "condition"},
                {"id": "brk_rear", "name": "Rear pads", "type": "condition", "allow_na": True},
            ],
        }
    ],
}


# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------


def _reenable_loggers() -> None:
    # alembic/env.py calls logging.config.fileConfig(), which disables every
    # logger that already exists in this process (the API runs migrations in a
    # separate process, so this only matters inside the test run).
    import logging

    for logger in logging.Logger.manager.loggerDict.values():
        if isinstance(logger, logging.Logger):
            logger.disabled = False


def reset_schema_to(revision: str = "head") -> None:
    from alembic import command
    from alembic.config import Config

    engine.dispose()
    with engine.begin() as connection:
        connection.execute(text("DROP SCHEMA public CASCADE"))
        connection.execute(text("CREATE SCHEMA public"))
    config = Config(str(BACKEND / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND / "alembic"))
    command.upgrade(config, revision)
    engine.dispose()
    _reenable_loggers()


def alembic_upgrade(revision: str = "head") -> None:
    from alembic import command
    from alembic.config import Config

    config = Config(str(BACKEND / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND / "alembic"))
    command.upgrade(config, revision)
    engine.dispose()
    _reenable_loggers()


@pytest.fixture(scope="session", autouse=True)
def migrated_database():
    reset_schema_to("head")
    yield


def _truncate_all() -> None:
    with engine.begin() as connection:
        tables = [
            row[0]
            for row in connection.execute(
                text("SELECT tablename FROM pg_tables WHERE schemaname = 'public' AND tablename <> 'alembic_version'")
            )
        ]
        if tables:
            connection.execute(text("TRUNCATE " + ", ".join(f'"{name}"' for name in tables) + " CASCADE"))


@pytest.fixture
def db():
    _truncate_all()
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


# ---------------------------------------------------------------------------
# Auth0 stand-in
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def signing_key():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


@pytest.fixture(scope="session")
def other_signing_key():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


class JwksStub:
    def __init__(self, keys: dict[str, dict]):
        self.keys = keys
        self.calls = 0
        self.fail = False

    def __call__(self):
        self.calls += 1
        if self.fail:
            import httpx

            raise httpx.ConnectError("auth0 down")
        return dict(self.keys)


@pytest.fixture(autouse=True)
def jwks(monkeypatch, signing_key):
    public_jwk = jwt.algorithms.RSAAlgorithm.to_jwk(signing_key.public_key(), as_dict=True)
    public_jwk.update({"kid": KID, "use": "sig", "alg": "RS256"})
    stub = JwksStub({KID: public_jwk})
    monkeypatch.setattr(auth_module, "_fetch_jwks", stub)
    auth_module._jwks_cache.update({"expires_at": 0.0, "keys": {}, "fetched_at": None})
    yield stub
    auth_module._jwks_cache.update({"expires_at": 0.0, "keys": {}, "fetched_at": None})


@pytest.fixture
def make_token(signing_key):
    def _make(sub: str, *, key=None, kid: object = KID, algorithm: str = "RS256", drop: tuple[str, ...] = (), **claims):
        now = int(time.time())
        payload = {
            "iss": f"https://{AUTH0_DOMAIN}/",
            "aud": AUTH0_AUDIENCE,
            "sub": sub,
            "iat": now,
            "exp": now + 600,
            **claims,
        }
        for name in drop:
            payload.pop(name, None)
        headers = {"kid": kid} if kid is not None else {}
        return jwt.encode(payload, key if key is not None else signing_key, algorithm=algorithm, headers=headers)

    return _make


@pytest.fixture
def bearer(make_token):
    def _bearer(user: "User | str", **kwargs) -> dict[str, str]:
        sub = user if isinstance(user, str) else user.auth0_id
        return {"Authorization": f"Bearer {make_token(sub, **kwargs)}"}

    return _bearer


@pytest.fixture
def agent_headers():
    return {"X-Workbai-Service-Token": VOICE_AGENT_TOKEN}


# ---------------------------------------------------------------------------
# App and data
# ---------------------------------------------------------------------------


@pytest.fixture
def client():
    from app.main import create_app

    return TestClient(create_app())


class World:
    """Two shops with staff and one active approved template each."""

    def __init__(self, db):
        self.db = db
        self.shop_a = Shop(name="Shop A", created_at=datetime(2026, 1, 1))
        self.shop_b = Shop(name="Shop B", created_at=datetime(2026, 2, 1))
        db.add_all([self.shop_a, self.shop_b])
        db.flush()
        self.tech_a1 = self._user(self.shop_a, UserRole.technician, "Tech A1")
        self.tech_a2 = self._user(self.shop_a, UserRole.technician, "Tech A2")
        self.advisor_a = self._user(self.shop_a, UserRole.advisor, "Advisor A")
        self.admin_a = self._user(self.shop_a, UserRole.admin, "Admin A")
        self.tech_b = self._user(self.shop_b, UserRole.technician, "Tech B")
        self.admin_b = self._user(self.shop_b, UserRole.admin, "Admin B")
        self.inactive_tech_a = self._user(self.shop_a, UserRole.technician, "Gone A", active=False)
        db.flush()
        self.template_a = self._approved_template(self.shop_a, self.admin_a, "A inspection")
        self.template_b = self._approved_template(self.shop_b, self.admin_b, "B inspection")
        db.commit()

    def _user(self, shop, role, name, active=True):
        user = User(shop_id=shop.id, auth0_id=f"auth0|{uuid.uuid4().hex}", role=role, name=name, active=active)
        self.db.add(user)
        return user

    def _approved_template(self, shop, admin, name):
        template = ChecklistTemplate(
            shop_id=shop.id,
            name=name,
            items=TEMPLATE_DOC,
            version=1,
            lifecycle_status=TemplateLifecycleStatus.approved,
            is_provisional=False,
            locked_provisional=False,
            active_for_new_visits=True,
            source_reference=f"controlled sheet for {name}",
            source_sha256=secrets.token_hex(32),
            approved_at=datetime.utcnow(),
            approved_by_user_id=admin.id,
        )
        self.db.add(template)
        self.db.flush()
        return template

    def legacy_session(self, technician, *, status=SessionStatus.in_progress, template=None, started_at=None):
        session = InspectionSession(
            shop_id=technician.shop_id,
            technician_id=technician.id,
            assigned_technician_id=technician.id,
            checklist_template_id=template.id if template else None,
            vehicle_year="2017",
            vehicle_make="Toyota",
            vehicle_model="Highlander",
            status=status,
            started_at=started_at or datetime.utcnow(),
        )
        self.db.add(session)
        self.db.commit()
        return session

    def template_session(self, technician, template, *, status=SessionStatus.pending, started_at=None):
        session = InspectionSession(
            shop_id=technician.shop_id,
            technician_id=technician.id,
            assigned_technician_id=technician.id,
            checklist_template_id=template.id,
            template_snapshot=TEMPLATE_DOC,
            template_version=template.version,
            template_source_reference=template.source_reference,
            template_source_sha256=template.source_sha256,
            template_approved_at=template.approved_at,
            template_approved_by_user_id=template.approved_by_user_id,
            presence_mode="waiter",
            vehicle_year="2019",
            vehicle_make="Honda",
            vehicle_model="Civic",
            customer_concern="Squeal when braking",
            status=status,
            started_at=started_at or datetime.utcnow(),
        )
        self.db.add(session)
        self.db.commit()
        return session


@pytest.fixture
def world(db):
    return World(db)
