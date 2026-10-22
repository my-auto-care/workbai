"""Disposable acceptance harness for the staff-only customer and intake-context domain.

Run only against an empty disposable database. It prints neither customer PII nor
raw context text and makes no provider, telephony, customer-message, or public call.
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta

from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

os.environ.update({
    "WORKBAI_CUSTOMER_DATA_ENCRYPTION_KEY": Fernet.generate_key().decode(),
    "WORKBAI_CUSTOMER_DATA_ENCRYPTION_KEY_ID": "customer-acceptance-v1",
    "WORKBAI_CUSTOMER_SEARCH_HMAC_PEPPER": "customer-search-acceptance-pepper",
    "WORKBAI_ENABLE_CURRENT_VISIT_RELEASE": "false",
})

from app.api.checkin import prune_expired_customer_context_records  # noqa: E402
from app.auth import StaffActor, get_current_actor  # noqa: E402
from app.db.models import (  # noqa: E402
    ChecklistTemplate,
    CustomerContextAccessAudit,
    CustomerContextRecord,
    CustomerProfileAccessAudit,
    IntakeReasonSuggestionSelection,
    Shop,
    TemplateLifecycleStatus,
    User,
    UserRole,
    VehicleCatalogEntry,
)
from app.db.session import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402


def as_actor(user_id, shop_id, role, name):
    app.dependency_overrides[get_current_actor] = lambda: StaffActor(user_id, shop_id, role, name, f"auth0|{name.lower()}")


with SessionLocal() as db:
    shop = Shop(name="Customer Intake Acceptance Shop")
    other_shop = Shop(name="Other Customer Shop")
    db.add_all([shop, other_shop])
    db.flush()
    advisor = User(shop_id=shop.id, auth0_id="auth0|intake-advisor", role=UserRole.advisor, name="Advisor", active=True)
    technician = User(shop_id=shop.id, auth0_id="auth0|intake-tech", role=UserRole.technician, name="Technician", active=True)
    other_advisor = User(shop_id=other_shop.id, auth0_id="auth0|intake-other", role=UserRole.advisor, name="Other Advisor", active=True)
    db.add_all([advisor, technician, other_advisor])
    db.flush()
    template = ChecklistTemplate(
        name="Customer intake controlled template",
        version=1,
        lifecycle_status=TemplateLifecycleStatus.approved,
        is_provisional=False,
        active_for_new_visits=True,
        source_reference="customer-intake acceptance fixture",
        source_sha256="c" * 64,
        approved_at=datetime.utcnow(),
        approved_by_user_id=advisor.id,
        items={"name": "Customer intake controlled template", "sections": [{"id": "safety", "name": "Safety", "items": [{"id": "fixture-1", "name": "Fixture", "type": "condition", "options": ["Good", "Needs attention"]}]}]},
    )
    catalog = VehicleCatalogEntry(
        source_name="nhtsa_vpic",
        source_make_id="448",
        source_model_id="2213",
        model_year=2017,
        make="TOYOTA",
        model="Highlander",
        search_text="2017 toyota highlander",
        source_url="https://vpic.nhtsa.dot.gov/api/vehicles/GetModelsForMakeYear/make/toyota/modelyear/2017?format=json",
        source_retrieved_at=datetime.utcnow(),
        active=True,
        created_at=datetime.utcnow(),
    )
    db.add_all([template, catalog])
    db.commit()
    ids = {"shop": shop.id, "advisor": advisor.id, "technician": technician.id, "other_shop": other_shop.id, "other_advisor": other_advisor.id, "catalog": catalog.id}

with TestClient(app) as client:
    as_actor(ids["advisor"], ids["shop"], UserRole.advisor, "Advisor")
    created = client.post("/check-in/sessions", json={
        "vehicle_year": 2017,
        "vehicle_make": "Toyota",
        "vehicle_model": "Highlander",
        "vehicle_mileage": 83000,
        "vehicle_vin": "5TDZA3EH0HS123456",
        "vehicle_catalog_entry_id": str(ids["catalog"]),
        "new_customer": {"display_name": "Jamie Example", "contacts": [{"channel": "sms", "destination": "+15551234567"}, {"channel": "email", "destination": "jamie@example.com"}]},
        "customer_vehicle_confirmation": True,
        "customer_concern": "A vibration is felt while braking.",
        "presence_mode": "dropoff",
        "assigned_technician_id": str(ids["technician"]),
    })
    assert created.status_code == 201, created.text
    payload = created.json()
    assert payload["customer_profile_recorded"] is True and payload["vehicle_id"] and payload["customer_id"]
    session_id, customer_id, vehicle_id = payload["id"], payload["customer_id"], payload["vehicle_id"]

    catalog_search = client.post("/check-in/search", json={"query": "2017 Toyota Highlander"})
    assert catalog_search.status_code == 200 and any(row["id"] == str(ids["catalog"]) for row in catalog_search.json()["catalog_vehicles"]), catalog_search.text
    name_search = client.post("/check-in/search", json={"query": "Jamie"})
    assert name_search.status_code == 200 and any(row["id"] == customer_id for row in name_search.json()["customers"]), name_search.text
    phone_search = client.post("/check-in/search", json={"query": "5551234567"})
    assert phone_search.status_code == 200 and any(row["id"] == customer_id for row in phone_search.json()["customers"]), phone_search.text
    vin_tail_search = client.post("/check-in/search", json={"query": "HS123456"})
    assert vin_tail_search.status_code == 200 and any(row["id"] == vehicle_id for row in vin_tail_search.json()["shop_vehicles"]), vin_tail_search.text

    before = client.get("/check-in/context", params={"customer_id": customer_id, "vehicle_id": vehicle_id})
    assert before.status_code == 200 and before.json()["history"] and any(row["kind"] == "reviewed_context" for row in before.json()["reason_suggestions"]), before.text
    assert "vibration" not in str(before.json()).lower() or any(row["kind"] == "reviewed_context" for row in before.json()["reason_suggestions"])

    record = client.post("/check-in/context-records", json={
        "inspection_session_id": session_id,
        "source_type": "phone_transcript",
        "source_label": "Reviewed call summary",
        "source_reference": "call-fixture-1",
        "raw_content": "This sensitive transcript fixture must not appear in normal history.",
        "reviewed_excerpt": "Customer asked about a recurring braking vibration.",
        "raw_retention_until": (datetime.utcnow() + timedelta(days=1)).isoformat() + "Z",
    })
    assert record.status_code == 201, record.text
    record_id = record.json()["id"]
    appointment = client.post("/check-in/context-records", json={
        "inspection_session_id": session_id,
        "source_type": "appointment_note",
        "source_label": "Scheduled appointment",
        "source_reference": "appointment-fixture-1",
        "raw_content": "Customer requested a Friday morning appointment.",
        "reviewed_excerpt": "Friday morning appointment requested.",
        "appointment_at": (datetime.utcnow() + timedelta(days=2)).isoformat(),
    })
    assert appointment.status_code == 201, appointment.text

    context = client.get("/check-in/context", params={"customer_id": customer_id, "vehicle_id": vehicle_id})
    assert context.status_code == 200, context.text
    rendered_context = str(context.json())
    assert "sensitive transcript fixture" not in rendered_context
    assert any(row["id"] == record_id for row in context.json()["reason_suggestions"])

    as_actor(ids["technician"], ids["shop"], UserRole.technician, "Technician")
    assert client.get(f"/check-in/context-records/{record_id}/raw").status_code == 403
    as_actor(ids["advisor"], ids["shop"], UserRole.advisor, "Advisor")
    raw = client.get(f"/check-in/context-records/{record_id}/raw", params={"purpose": "customer_conversation"})
    assert raw.status_code == 200 and raw.json()["raw_text"].startswith("This sensitive transcript"), raw.text
    call_card = client.post("/check-in/call-context", json={"caller_phone": "+15551234567"})
    assert call_card.status_code == 200 and call_card.json()["match_count"] == 1 and call_card.json()["matches"][0]["next_appointment"], call_card.text
    assert "sensitive transcript fixture" not in str(call_card.json())

    second = client.post("/check-in/sessions", json={
        "vehicle_year": 2017,
        "vehicle_make": "Toyota",
        "vehicle_model": "Highlander",
        "vehicle_id": vehicle_id,
        "customer_id": customer_id,
        "customer_concern": "Customer confirmed a recurring braking vibration.",
        "reason_context_record_id": record_id,
        "presence_mode": "waiter",
        "assigned_technician_id": str(ids["technician"]),
    })
    assert second.status_code == 201, second.text
    with SessionLocal() as db:
        assert db.query(IntakeReasonSuggestionSelection).count() == 1
        assert db.query(CustomerContextAccessAudit).count() == 1
        assert db.query(CustomerProfileAccessAudit).filter(CustomerProfileAccessAudit.purpose == "incoming_call_context").count() == 1
        expiring = db.query(CustomerContextRecord).filter(CustomerContextRecord.id == record_id).one()
        expiring.raw_retention_until = datetime.utcnow() - timedelta(seconds=1)
        db.commit()
    expired_read = client.get(f"/check-in/context-records/{record_id}/raw")
    assert expired_read.status_code == 410, expired_read.text
    with SessionLocal() as db:
        assert prune_expired_customer_context_records(db)["raw_context_purged"] == 0
        assert db.query(CustomerContextRecord).filter(CustomerContextRecord.id == record_id).one().raw_content_ciphertext is None

    as_actor(ids["other_advisor"], ids["other_shop"], UserRole.advisor, "Other Advisor")
    assert client.get("/check-in/context", params={"customer_id": customer_id}).status_code == 404
    assert client.post("/check-in/call-context", json={"caller_phone": "+15551234567"}).json()["match_count"] == 0

app.dependency_overrides.clear()
print("PASS: encrypted internal customer search, catalog proposal, confirmed vehicle link, staff-only context, source-backed reason draft, appointment call card, audited raw transcript, retention purge, and tenant isolation")
