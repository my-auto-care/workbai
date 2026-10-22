"""Advisor/admin Check-in, customer lookup, and internal context for the canonical visit."""

from __future__ import annotations

import re
import uuid
from datetime import UTC, datetime, timedelta
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from sqlalchemy import String, or_
from sqlalchemy.orm import Session

from app.auth import StaffActor, require_roles
from app.current_visit_security import (
    contact_encryption_key_id,
    contact_lookup_hmac,
    current_visit_release_enabled,
    encrypt_contact,
    normalize_contact,
    require_current_visit_release_enabled,
)
from app.customer_data_security import (
    customer_blind_index_tokens,
    customer_data_enabled,
    customer_data_encryption_key_id,
    customer_search_token,
    decrypt_customer_data,
    encrypt_customer_data,
    normalize_customer_contact,
    normalize_search_text,
    query_blind_index_tokens,
    require_customer_data_enabled,
    safe_excerpt,
)
from app.db.models import (
    ChecklistTemplate,
    CommunicationConsent,
    Customer,
    CustomerContactMethod,
    CustomerContactPoint,
    CustomerContextAccessAudit,
    CustomerContextRecord,
    CustomerProfileAccessAudit,
    CustomerSearchToken,
    CustomerVehicleLink,
    InspectionSession,
    IntakeReasonSuggestion,
    IntakeReasonSuggestionSelection,
    SessionStatus,
    TemplateLifecycleStatus,
    User,
    UserRole,
    Vehicle,
    VehicleCatalogEntry,
)
from app.db.session import get_db
from app.inspection_template import validated_template_snapshot

router = APIRouter(prefix="/check-in", tags=["check-in"])
_ADVISOR_OR_ADMIN = require_roles(UserRole.advisor, UserRole.admin)
_ADMIN_ONLY = require_roles(UserRole.admin)
_VIN = re.compile(r"^[A-HJ-NPR-Z0-9]{17}$")
_CONSENT_POLICY_VERSION = "current-visit-pilot-v1"
_COMMON_INTAKE_WORDING = (
    "Routine maintenance request",
    "Warning light concern",
    "Noise or vibration concern",
    "Braking concern",
    "Steering or handling concern",
    "Starting or battery concern",
    "Heating or air conditioning concern",
    "Tire concern",
)


class CustomerContactAtCheckin(BaseModel):
    """Optional visit-scoped Current Visit contact; never treated as customer identity."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    channel: Literal["sms", "email"]
    destination: str = Field(min_length=3, max_length=320)
    current_visit_link_consent: Literal["granted", "declined", "not_asked"] = "not_asked"
    current_visit_progress_consent: Literal["granted", "declined", "not_asked"] = "not_asked"


class CustomerProfileContactInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    channel: Literal["sms", "email"]
    destination: str = Field(min_length=3, max_length=320)


class NewCustomerAtCheckin(BaseModel):
    """A staff-created internal profile; client payload never carries a shop or role."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    display_name: str = Field(min_length=2, max_length=160)
    contacts: list[CustomerProfileContactInput] = Field(default_factory=list, max_length=2)

    @model_validator(mode="after")
    def no_duplicate_channels(self):
        channels = [contact.channel for contact in self.contacts]
        if len(channels) != len(set(channels)):
            raise ValueError("Provide no more than one mobile number and one email address")
        return self


class CheckinCreate(BaseModel):
    """One canonical-Visit intake command. Customer matches remain staff-confirmed candidates."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    vehicle_year: int = Field(ge=1886, le=2100)
    vehicle_make: str = Field(min_length=1, max_length=100)
    vehicle_model: str = Field(min_length=1, max_length=100)
    vehicle_vin: str | None = Field(default=None, max_length=17)
    vehicle_mileage: int | None = Field(default=None, ge=0, le=2_000_000)
    vehicle_id: uuid.UUID | None = None
    vehicle_catalog_entry_id: uuid.UUID | None = None
    customer_id: uuid.UUID | None = None
    new_customer: NewCustomerAtCheckin | None = None
    customer_vehicle_confirmation: bool = False
    customer_concern: str = Field(min_length=3, max_length=1000)
    reason_context_record_id: uuid.UUID | None = None
    reason_suggestion_id: uuid.UUID | None = None
    presence_mode: Literal["waiter", "dropoff"]
    assigned_technician_id: uuid.UUID
    customer_contact: CustomerContactAtCheckin | None = None

    @field_validator("vehicle_vin")
    @classmethod
    def normalize_vin(cls, value: str | None) -> str | None:
        if value is None or not value.strip():
            return None
        normalized = value.replace(" ", "").upper()
        if not _VIN.fullmatch(normalized):
            raise ValueError("VIN must be 17 characters and cannot include I, O, or Q")
        return normalized

    @model_validator(mode="after")
    def sources_are_unambiguous(self):
        if self.customer_id and self.new_customer:
            raise ValueError("Choose an existing customer or create a new profile, not both")
        if self.reason_context_record_id and self.reason_suggestion_id:
            raise ValueError("Choose only one source-backed reason prompt")
        return self


class CustomerContextRecordCreate(BaseModel):
    """Explicit human-reviewed context ingestion; it never calls an external model/provider."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    inspection_session_id: uuid.UUID
    source_type: Literal["phone_transcript", "appointment_note", "service_history", "prior_visit", "manual_note"]
    source_label: str = Field(min_length=3, max_length=160)
    source_reference: str | None = Field(default=None, max_length=256)
    source_recorded_at: datetime = Field(default_factory=datetime.utcnow)
    appointment_at: datetime | None = None
    raw_content: str = Field(min_length=3, max_length=20_000)
    reviewed_excerpt: str = Field(min_length=3, max_length=1_000)
    raw_retention_until: datetime | None = None

    @field_validator("source_recorded_at", "appointment_at", "raw_retention_until")
    @classmethod
    def normalize_time_to_utc_storage(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is not None:
            return value.astimezone(UTC).replace(tzinfo=None)
        return value

    @model_validator(mode="after")
    def retained_raw_context_is_bounded(self):
        if self.source_type == "appointment_note" and not self.appointment_at:
            raise ValueError("An appointment note requires the scheduled appointment time")
        if self.source_type == "phone_transcript" and not self.raw_retention_until:
            raise ValueError("A phone transcript requires a raw retention expiry")
        if self.raw_retention_until and self.raw_retention_until <= datetime.utcnow():
            raise ValueError("Raw context retention expiry must be in the future")
        if self.raw_retention_until and self.raw_retention_until > datetime.utcnow() + timedelta(days=90):
            raise ValueError("Raw context retention cannot exceed 90 days in this pilot")
        return self


class CuratedReasonSuggestionCreate(BaseModel):
    """Admin-curated reusable customer wording; not a known-issue, service, or diagnostic feed."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    phrase: str = Field(min_length=3, max_length=280)
    scope: Literal["shop_curated", "vehicle_curated", "customer_specific"]
    vehicle_catalog_entry_id: uuid.UUID | None = None
    customer_id: uuid.UUID | None = None
    source_context_record_id: uuid.UUID | None = None
    source_label: str = Field(min_length=3, max_length=160)
    source_revision: str = Field(min_length=3, max_length=128)

    @model_validator(mode="after")
    def scope_matches_target(self):
        if self.scope == "vehicle_curated" and not self.vehicle_catalog_entry_id:
            raise ValueError("Vehicle-curated wording needs a vehicle catalog record")
        if self.scope == "vehicle_curated" and self.customer_id:
            raise ValueError("Vehicle-curated wording cannot include a customer target")
        if self.scope == "customer_specific" and not self.customer_id:
            raise ValueError("Customer-specific wording needs a customer record")
        if self.scope == "shop_curated" and (self.vehicle_catalog_entry_id or self.customer_id):
            raise ValueError("Shop-curated wording cannot include a customer or vehicle target")
        if self.source_context_record_id and self.scope != "customer_specific":
            raise ValueError("A customer-context source may only create customer-specific wording")
        return self


class IncomingCallContextLookup(BaseModel):
    """Authenticated reception lookup. A real PBX integration must verify its own webhook separately."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    caller_phone: str = Field(min_length=8, max_length=32)


class CheckinSearchRequest(BaseModel):
    """POST body keeps staff-entered search PII out of HTTP request URLs and standard access logs."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    query: str = Field(min_length=2, max_length=100)


def _session_payload(session: InspectionSession) -> dict:
    return {
        "id": str(session.id),
        "status": session.status.value if isinstance(session.status, SessionStatus) else str(session.status),
        "shop_id": str(session.shop_id),
        "assigned_technician_id": str(session.assigned_technician_id),
        "vehicle_id": str(session.vehicle_id) if session.vehicle_id else None,
        "customer_id": str(session.customer_id) if session.customer_id else None,
        "vehicle_year": session.vehicle_year,
        "vehicle_make": session.vehicle_make,
        "vehicle_model": session.vehicle_model,
        "vehicle_vin": session.vehicle_vin,
        "vehicle_mileage": session.vehicle_mileage,
        "presence_mode": session.presence_mode,
        "template_version": session.template_version,
        "customer_contact_recorded": bool(session.customer_contacts),
        "customer_profile_recorded": bool(session.customer_id),
        "started_at": session.started_at,
    }


def _vehicle_label(vehicle: Vehicle) -> str:
    return " ".join(str(value) for value in (vehicle.year, vehicle.make, vehicle.model) if value).strip() or "Vehicle information incomplete"


def _catalog_payload(entry: VehicleCatalogEntry) -> dict:
    return {
        "id": str(entry.id),
        "label": f"{entry.model_year} {entry.make.title()} {entry.model.title()}",
        "year": entry.model_year,
        "make": entry.make.title(),
        "model": entry.model.title(),
        "source": {"name": entry.source_name, "retrieved_at": entry.source_retrieved_at, "url": entry.source_url},
    }


def _vehicle_payload(vehicle: Vehicle, *, linked: bool) -> dict:
    return {
        "id": str(vehicle.id),
        "label": _vehicle_label(vehicle),
        "year": vehicle.year,
        "make": vehicle.make,
        "model": vehicle.model,
        "mileage": vehicle.mileage,
        "catalog_entry_id": str(vehicle.vehicle_catalog_entry_id) if vehicle.vehicle_catalog_entry_id else None,
        "customer_relationship_confirmed": linked,
    }


def _masked_contact(channel: str, destination: str) -> str:
    if channel == "sms":
        return f"•••• {destination[-4:]}"
    local, _, domain = destination.partition("@")
    return f"{local[:1]}•••@{domain}" if domain else "Protected contact"


def _add_search_tokens(db: Session, shop_id, customer_id, field: str, value: str) -> None:
    for token in customer_blind_index_tokens(shop_id, field, value):
        db.add(CustomerSearchToken(shop_id=shop_id, customer_id=customer_id, field=field, token_hmac=token, created_at=datetime.utcnow()))


def _create_customer(db: Session, actor: StaffActor, body: NewCustomerAtCheckin) -> Customer:
    require_customer_data_enabled()
    customer = Customer(
        shop_id=actor.shop_id,
        display_name_encrypted=encrypt_customer_data(body.display_name),
        encryption_key_id=customer_data_encryption_key_id(),
        active=True,
        created_by_user_id=actor.user_id,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.add(customer)
    db.flush()
    _add_search_tokens(db, actor.shop_id, customer.id, "name", body.display_name)
    for contact_input in body.contacts:
        normalized = normalize_customer_contact(contact_input.channel, contact_input.destination)
        field = "phone" if contact_input.channel == "sms" else "email"
        db.add(CustomerContactMethod(
            shop_id=actor.shop_id,
            customer_id=customer.id,
            channel=contact_input.channel,
            encrypted_destination=encrypt_customer_data(normalized),
            encryption_key_id=customer_data_encryption_key_id(),
            lookup_hmac=customer_search_token(actor.shop_id, field, normalized),
            active=True,
            created_by_user_id=actor.user_id,
            created_at=datetime.utcnow(),
        ))
        _add_search_tokens(db, actor.shop_id, customer.id, field, normalized)
    return customer


def _customer_payload(db: Session, customer: Customer) -> dict:
    contacts = [
        {"channel": contact.channel, "label": _masked_contact(contact.channel, decrypt_customer_data(contact.encrypted_destination))}
        for contact in customer.contacts if contact.active
    ]
    links = (
        db.query(CustomerVehicleLink)
        .join(Vehicle, CustomerVehicleLink.vehicle_id == Vehicle.id)
        .filter(CustomerVehicleLink.shop_id == customer.shop_id, CustomerVehicleLink.customer_id == customer.id, CustomerVehicleLink.active.is_(True))
        .order_by(CustomerVehicleLink.confirmed_at.desc())
        .limit(4)
        .all()
    )
    return {
        "id": str(customer.id),
        "display_name": decrypt_customer_data(customer.display_name_encrypted),
        "contacts": contacts,
        "vehicles": [_vehicle_payload(link.vehicle, linked=True) for link in links],
    }


def _scoped_customer_or_404(db: Session, customer_id: uuid.UUID, actor: StaffActor) -> Customer:
    customer = db.query(Customer).filter(Customer.id == customer_id, Customer.shop_id == actor.shop_id, Customer.active.is_(True)).one_or_none()
    if not customer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer record not found")
    return customer


def _scoped_vehicle_or_404(db: Session, vehicle_id: uuid.UUID, actor: StaffActor) -> Vehicle:
    vehicle = db.query(Vehicle).filter(Vehicle.id == vehicle_id, Vehicle.shop_id == actor.shop_id).one_or_none()
    if not vehicle:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vehicle record not found")
    return vehicle


def _matches_vehicle_input(vehicle: Vehicle, body: CheckinCreate) -> bool:
    return vehicle.year == body.vehicle_year and (vehicle.make or "").casefold() == body.vehicle_make.casefold() and (vehicle.model or "").casefold() == body.vehicle_model.casefold()


def _context_prompt_or_422(db: Session, record_id: uuid.UUID, actor: StaffActor, customer_id, vehicle_id) -> CustomerContextRecord:
    record = db.query(CustomerContextRecord).filter(CustomerContextRecord.id == record_id, CustomerContextRecord.shop_id == actor.shop_id, CustomerContextRecord.review_state == "reviewed").one_or_none()
    if not record or (record.customer_id and record.customer_id != customer_id) or (record.vehicle_id and record.vehicle_id != vehicle_id):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="The selected history prompt is not available for this customer and vehicle")
    return record


@router.get("/options")
def checkin_options(actor: StaffActor = Depends(_ADVISOR_OR_ADMIN), db: Session = Depends(get_db)):
    technicians = db.query(User).filter(User.shop_id == actor.shop_id, User.active.is_(True), User.role == UserRole.technician).order_by(User.name.asc()).all()
    templates = db.query(ChecklistTemplate).filter(ChecklistTemplate.lifecycle_status == TemplateLifecycleStatus.approved, ChecklistTemplate.is_provisional.is_(False), ChecklistTemplate.active_for_new_visits.is_(True)).order_by(ChecklistTemplate.name.asc(), ChecklistTemplate.version.desc()).all()
    return {
        "actor": {"name": actor.name, "role": actor.role.value, "shop_id": str(actor.shop_id)},
        "technicians": [{"id": str(user.id), "name": user.name} for user in technicians],
        "checklists": [{"id": str(template.id), "name": template.name, "version": template.version, "vehicle_filter": template.vehicle_filter or {}} for template in templates],
        "customer_contact_capture_enabled": current_visit_release_enabled(),
        "customer_context_enabled": customer_data_enabled(),
        "common_intake_wording": list(_COMMON_INTAKE_WORDING),
    }


@router.post("/search")
def checkin_search(body: CheckinSearchRequest, actor: StaffActor = Depends(_ADVISOR_OR_ADMIN), db: Session = Depends(get_db)):
    """Staff-only candidate search. This handler does not persist or log the typed query."""
    q = body.query
    hmacs = query_blind_index_tokens(actor.shop_id, q) if customer_data_enabled() else set()
    customer_ids = [row[0] for row in db.query(CustomerSearchToken.customer_id).filter(CustomerSearchToken.shop_id == actor.shop_id, CustomerSearchToken.token_hmac.in_(hmacs)).distinct().limit(12).all()] if hmacs else []
    customers = db.query(Customer).filter(Customer.id.in_(customer_ids), Customer.shop_id == actor.shop_id, Customer.active.is_(True)).limit(12).all() if customer_ids else []
    tokens = normalize_search_text(q).split()
    compact = re.sub(r"[^A-Za-z0-9]", "", q).upper()
    catalog_query = db.query(VehicleCatalogEntry).filter(VehicleCatalogEntry.active.is_(True))
    vehicle_query = db.query(Vehicle).filter(Vehicle.shop_id == actor.shop_id)
    for token in tokens[:5]:
        catalog_query = catalog_query.filter(VehicleCatalogEntry.search_text.ilike(f"%{token}%"))
    if compact and len(compact) in {8, 17} and customer_data_enabled():
        full_digest = customer_search_token(actor.shop_id, "vin", compact)
        vehicle_query = vehicle_query.filter(or_(Vehicle.vin_lookup_hmac == full_digest, Vehicle.vin_tail_lookup_hmac == full_digest))
    else:
        for token in tokens[:5]:
            vehicle_query = vehicle_query.filter(or_(Vehicle.make.ilike(f"%{token}%"), Vehicle.model.ilike(f"%{token}%"), Vehicle.year.cast(String).ilike(f"%{token}%")))
    catalog = catalog_query.order_by(VehicleCatalogEntry.model_year.desc(), VehicleCatalogEntry.make, VehicleCatalogEntry.model).limit(12).all() if tokens else []
    vehicles = vehicle_query.order_by(Vehicle.created_at.desc()).limit(12).all() if tokens else []
    return {"customers": [_customer_payload(db, customer) for customer in customers], "shop_vehicles": [_vehicle_payload(vehicle, linked=False) for vehicle in vehicles], "catalog_vehicles": [_catalog_payload(entry) for entry in catalog]}


@router.get("/context")
def checkin_context(customer_id: uuid.UUID | None = None, vehicle_id: uuid.UUID | None = None, actor: StaffActor = Depends(_ADVISOR_OR_ADMIN), db: Session = Depends(get_db)):
    """Bounded staff context only. Raw transcripts are deliberately excluded."""
    require_customer_data_enabled()
    if not customer_id and not vehicle_id:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Choose a customer or vehicle first")
    customer = _scoped_customer_or_404(db, customer_id, actor) if customer_id else None
    vehicle = _scoped_vehicle_or_404(db, vehicle_id, actor) if vehicle_id else None
    if customer_id and vehicle_id:
        filters = [CustomerContextRecord.customer_id == customer_id, CustomerContextRecord.vehicle_id == vehicle_id]
    elif customer_id:
        filters = [CustomerContextRecord.customer_id == customer_id, CustomerContextRecord.vehicle_id.is_(None)]
    else:
        filters = [CustomerContextRecord.vehicle_id == vehicle_id, CustomerContextRecord.customer_id.is_(None)]
    contexts = db.query(CustomerContextRecord).filter(CustomerContextRecord.shop_id == actor.shop_id, CustomerContextRecord.review_state == "reviewed", *filters).order_by(CustomerContextRecord.source_recorded_at.desc()).limit(8).all()
    context_suggestions = [{"id": str(row.id), "kind": "reviewed_context", "label": safe_excerpt(decrypt_customer_data(row.reviewed_excerpt_ciphertext)), "source_label": row.source_label, "source_type": row.source_type, "recorded_at": row.source_recorded_at} for row in contexts]
    catalog_entry_id = vehicle.vehicle_catalog_entry_id if vehicle else None
    suggestion_filters = [IntakeReasonSuggestion.scope == "shop_curated"]
    if customer_id:
        suggestion_filters.append((IntakeReasonSuggestion.scope == "customer_specific") & (IntakeReasonSuggestion.customer_id == customer_id))
    if catalog_entry_id:
        suggestion_filters.append((IntakeReasonSuggestion.scope == "vehicle_curated") & (IntakeReasonSuggestion.vehicle_catalog_entry_id == catalog_entry_id))
    curated = db.query(IntakeReasonSuggestion).filter(IntakeReasonSuggestion.shop_id == actor.shop_id, IntakeReasonSuggestion.state == "approved", or_(*suggestion_filters)).order_by(IntakeReasonSuggestion.approved_at.desc()).limit(8).all()
    curated_suggestions = [{"id": str(row.id), "kind": "curated_prompt", "label": safe_excerpt(decrypt_customer_data(row.phrase_ciphertext)), "source_label": row.source_label, "source_type": "curated_customer_wording"} for row in curated]
    history_filters = ([InspectionSession.customer_id == customer_id] if customer_id else []) + ([InspectionSession.vehicle_id == vehicle_id] if vehicle_id else [])
    history = db.query(InspectionSession).filter(InspectionSession.shop_id == actor.shop_id, or_(*history_filters)).order_by(InspectionSession.started_at.desc()).limit(8).all()
    generic = [{"id": f"common:{number}", "kind": "common_prompt", "label": phrase, "source_label": "Common customer wording", "source_type": "general_intake"} for number, phrase in enumerate(_COMMON_INTAKE_WORDING, start=1)]
    return {"customer": _customer_payload(db, customer) if customer else None, "vehicle": _vehicle_payload(vehicle, linked=False) if vehicle else None, "history": [{"session_id": str(row.id), "started_at": row.started_at, "status": row.status.value if isinstance(row.status, SessionStatus) else str(row.status), "vehicle_label": " ".join(filter(None, [row.vehicle_year, row.vehicle_make, row.vehicle_model]))} for row in history], "reason_suggestions": context_suggestions + curated_suggestions + generic}


@router.post("/context-records", status_code=status.HTTP_201_CREATED)
def create_context_record(body: CustomerContextRecordCreate, actor: StaffActor = Depends(_ADVISOR_OR_ADMIN), db: Session = Depends(get_db)):
    require_customer_data_enabled()
    session = db.query(InspectionSession).filter(InspectionSession.id == body.inspection_session_id, InspectionSession.shop_id == actor.shop_id).one_or_none()
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Inspection session not found")
    if not session.customer_id and not session.vehicle_id:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Link a customer or vehicle to the canonical visit before adding history context")
    reference = customer_search_token(actor.shop_id, "context_reference", body.source_reference) if body.source_reference else None
    record = CustomerContextRecord(shop_id=actor.shop_id, customer_id=session.customer_id, vehicle_id=session.vehicle_id, inspection_session_id=session.id, source_type=body.source_type, source_label=body.source_label, source_reference_hmac=reference, source_recorded_at=body.source_recorded_at, appointment_at=body.appointment_at, raw_content_ciphertext=encrypt_customer_data(body.raw_content), reviewed_excerpt_ciphertext=encrypt_customer_data(body.reviewed_excerpt), encryption_key_id=customer_data_encryption_key_id(), review_state="reviewed", reviewed_by_user_id=actor.user_id, reviewed_at=datetime.utcnow(), raw_retention_until=body.raw_retention_until, created_at=datetime.utcnow())
    db.add(record)
    db.commit()
    return {"id": str(record.id), "source_type": record.source_type, "source_label": record.source_label, "reviewed": True}


@router.post("/call-context")
def incoming_call_context(body: IncomingCallContextLookup, actor: StaffActor = Depends(_ADVISOR_OR_ADMIN), db: Session = Depends(get_db)):
    """Return a small, staff-only incoming-call card for an exact normalized phone match.

    This does not create a call, contact the customer, trust a caller identity, or
    expose raw transcripts. A future provider webhook must authenticate before it
    ever invokes a reception display.
    """
    require_customer_data_enabled()
    normalized = normalize_customer_contact("sms", body.caller_phone)
    digest = customer_search_token(actor.shop_id, "phone", normalized)
    customer_ids = [row[0] for row in db.query(CustomerSearchToken.customer_id).filter(CustomerSearchToken.shop_id == actor.shop_id, CustomerSearchToken.field == "phone", CustomerSearchToken.token_hmac == digest).distinct().limit(8).all()]
    customers = db.query(Customer).filter(Customer.id.in_(customer_ids), Customer.shop_id == actor.shop_id, Customer.active.is_(True)).limit(8).all() if customer_ids else []
    now = datetime.utcnow()
    matches = []
    for customer in customers:
        visits = db.query(InspectionSession).filter(InspectionSession.shop_id == actor.shop_id, InspectionSession.customer_id == customer.id).order_by(InspectionSession.started_at.desc()).limit(3).all()
        contexts = db.query(CustomerContextRecord).filter(CustomerContextRecord.shop_id == actor.shop_id, CustomerContextRecord.customer_id == customer.id, CustomerContextRecord.review_state == "reviewed").order_by(CustomerContextRecord.source_recorded_at.desc()).limit(3).all()
        appointment = db.query(CustomerContextRecord).filter(CustomerContextRecord.shop_id == actor.shop_id, CustomerContextRecord.customer_id == customer.id, CustomerContextRecord.source_type == "appointment_note", CustomerContextRecord.review_state == "reviewed", CustomerContextRecord.appointment_at >= now).order_by(CustomerContextRecord.appointment_at.asc()).first()
        matches.append({
            "customer": _customer_payload(db, customer),
            "conversation_summaries": [{"source_label": row.source_label, "source_type": row.source_type, "summary": safe_excerpt(decrypt_customer_data(row.reviewed_excerpt_ciphertext), 180), "recorded_at": row.source_recorded_at} for row in contexts],
            "recent_visits": [{"started_at": row.started_at, "status": row.status.value if isinstance(row.status, SessionStatus) else str(row.status), "vehicle_label": " ".join(filter(None, [row.vehicle_year, row.vehicle_make, row.vehicle_model]))} for row in visits],
            "next_appointment": ({"at": appointment.appointment_at, "summary": safe_excerpt(decrypt_customer_data(appointment.reviewed_excerpt_ciphertext), 180), "source_label": appointment.source_label} if appointment else None),
        })
        db.add(CustomerProfileAccessAudit(shop_id=actor.shop_id, customer_id=customer.id, actor_user_id=actor.user_id, purpose="incoming_call_context", occurred_at=datetime.utcnow()))
    if matches:
        db.commit()
    return {"match_count": len(matches), "matches": matches, "unverified_caller_notice": "A matching number is a staff candidate only; confirm identity before discussing account details."}


@router.get("/context-records/{record_id}/raw")
def read_raw_context_record(record_id: uuid.UUID, purpose: Literal["customer_conversation", "data_correction"] = "customer_conversation", actor: StaffActor = Depends(_ADVISOR_OR_ADMIN), db: Session = Depends(get_db)):
    """Audited advisor/admin read of retained raw context. It is never returned in search/history responses."""
    require_customer_data_enabled()
    record = db.query(CustomerContextRecord).filter(CustomerContextRecord.id == record_id, CustomerContextRecord.shop_id == actor.shop_id).one_or_none()
    if not record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Context record not found")
    if record.raw_retention_until and record.raw_retention_until <= datetime.utcnow():
        record.raw_content_ciphertext = None
        record.raw_purged_at = datetime.utcnow()
        db.commit()
        raise HTTPException(status_code=status.HTTP_410_GONE, detail="Raw context is no longer retained")
    if not record.raw_content_ciphertext:
        raise HTTPException(status_code=status.HTTP_410_GONE, detail="Raw context is no longer retained")
    db.add(CustomerContextAccessAudit(shop_id=actor.shop_id, context_record_id=record.id, actor_user_id=actor.user_id, purpose=purpose, occurred_at=datetime.utcnow()))
    db.commit()
    return {"id": str(record.id), "source_type": record.source_type, "source_label": record.source_label, "raw_text": decrypt_customer_data(record.raw_content_ciphertext)}


@router.post("/reason-suggestions", status_code=status.HTTP_201_CREATED)
def create_curated_reason_suggestion(body: CuratedReasonSuggestionCreate, actor: StaffActor = Depends(_ADMIN_ONLY), db: Session = Depends(get_db)):
    require_customer_data_enabled()
    if body.customer_id:
        _scoped_customer_or_404(db, body.customer_id, actor)
    if body.vehicle_catalog_entry_id and not db.query(VehicleCatalogEntry).filter(VehicleCatalogEntry.id == body.vehicle_catalog_entry_id, VehicleCatalogEntry.active.is_(True)).one_or_none():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vehicle catalog record not found")
    if body.source_context_record_id:
        source = db.query(CustomerContextRecord).filter(CustomerContextRecord.id == body.source_context_record_id, CustomerContextRecord.shop_id == actor.shop_id, CustomerContextRecord.review_state == "reviewed").one_or_none()
        if not source:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reviewed context source not found")
        if body.scope != "customer_specific" or source.customer_id != body.customer_id:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Customer-context wording must remain scoped to its source customer")
    suggestion = IntakeReasonSuggestion(shop_id=actor.shop_id, customer_id=body.customer_id, vehicle_catalog_entry_id=body.vehicle_catalog_entry_id, source_context_record_id=body.source_context_record_id, scope=body.scope, phrase_ciphertext=encrypt_customer_data(body.phrase), phrase_hmac=customer_search_token(actor.shop_id, "reason_phrase", body.phrase), encryption_key_id=customer_data_encryption_key_id(), source_label=body.source_label, source_revision=body.source_revision, state="approved", approved_by_user_id=actor.user_id, approved_at=datetime.utcnow())
    db.add(suggestion)
    db.commit()
    return {"id": str(suggestion.id), "scope": suggestion.scope, "state": suggestion.state}


@router.post("/sessions", status_code=status.HTTP_201_CREATED)
def create_pending_session(body: CheckinCreate, actor: StaffActor = Depends(_ADVISOR_OR_ADMIN), db: Session = Depends(get_db)):
    technician = db.query(User).filter(User.id == body.assigned_technician_id, User.shop_id == actor.shop_id, User.active.is_(True), User.role == UserRole.technician).one_or_none()
    if not technician:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Select an active technician in this shop")
    templates = db.query(ChecklistTemplate).with_for_update().filter(ChecklistTemplate.lifecycle_status == TemplateLifecycleStatus.approved, ChecklistTemplate.is_provisional.is_(False), ChecklistTemplate.active_for_new_visits.is_(True)).all()
    if len(templates) != 1:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="A single active approved inspection template is required before a new visit can be started")
    template = templates[0]
    if not template.source_reference or not template.source_sha256 or not template.approved_at or not template.approved_by_user_id:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="The active inspection template is missing required approval provenance")
    try:
        snapshot = validated_template_snapshot(template.items)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Selected inspection template is structurally invalid and cannot be used for a new visit") from exc

    customer = _scoped_customer_or_404(db, body.customer_id, actor) if body.customer_id else (_create_customer(db, actor, body.new_customer) if body.new_customer else None)
    catalog = None
    if body.vehicle_catalog_entry_id:
        catalog = db.query(VehicleCatalogEntry).filter(VehicleCatalogEntry.id == body.vehicle_catalog_entry_id, VehicleCatalogEntry.active.is_(True)).one_or_none()
        if not catalog or (catalog.model_year, catalog.make.casefold(), catalog.model.casefold()) != (body.vehicle_year, body.vehicle_make.casefold(), body.vehicle_model.casefold()):
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Confirm the selected catalog vehicle before starting the visit")
    vehicle = _scoped_vehicle_or_404(db, body.vehicle_id, actor) if body.vehicle_id else None
    if vehicle and not _matches_vehicle_input(vehicle, body):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="The selected vehicle no longer matches the confirmed check-in details")
    if not vehicle:
        if body.vehicle_vin:
            require_customer_data_enabled()
        vehicle = Vehicle(shop_id=actor.shop_id, year=body.vehicle_year, make=body.vehicle_make, model=body.vehicle_model, mileage=body.vehicle_mileage, vin=None, vehicle_catalog_entry_id=catalog.id if catalog else None, vin_encrypted=encrypt_customer_data(body.vehicle_vin) if body.vehicle_vin else None, vin_encryption_key_id=customer_data_encryption_key_id() if body.vehicle_vin else None, vin_lookup_hmac=customer_search_token(actor.shop_id, "vin", body.vehicle_vin) if body.vehicle_vin else None, vin_tail_lookup_hmac=customer_search_token(actor.shop_id, "vin", body.vehicle_vin[-8:]) if body.vehicle_vin else None, created_at=datetime.utcnow())
        db.add(vehicle)
        db.flush()
    link = None
    if customer:
        link = db.query(CustomerVehicleLink).filter(CustomerVehicleLink.shop_id == actor.shop_id, CustomerVehicleLink.customer_id == customer.id, CustomerVehicleLink.vehicle_id == vehicle.id, CustomerVehicleLink.active.is_(True)).one_or_none()
        if not link and not body.customer_vehicle_confirmation:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Confirm the customer–vehicle relationship before starting this visit")
        if not link:
            link = CustomerVehicleLink(shop_id=actor.shop_id, customer_id=customer.id, vehicle_id=vehicle.id, relationship_code="customer_confirmed", active=True, confirmed_by_user_id=actor.user_id, confirmed_at=datetime.utcnow())
            db.add(link)
            db.flush()
    session = InspectionSession(shop_id=actor.shop_id, technician_id=technician.id, assigned_technician_id=technician.id, vehicle_id=vehicle.id, customer_id=customer.id if customer else None, customer_vehicle_link_id=link.id if link else None, checklist_template_id=template.id, template_snapshot=snapshot, template_version=template.version, template_source_reference=template.source_reference, template_source_sha256=template.source_sha256, template_approved_at=template.approved_at, template_approved_by_user_id=template.approved_by_user_id, presence_mode=body.presence_mode, vehicle_year=str(body.vehicle_year), vehicle_make=body.vehicle_make, vehicle_model=body.vehicle_model, vehicle_vin=None, vehicle_mileage=body.vehicle_mileage, customer_concern=body.customer_concern, status=SessionStatus.pending, started_at=datetime.utcnow())
    db.add(session)
    db.flush()
    if customer:
        db.add(CustomerContextRecord(shop_id=actor.shop_id, customer_id=customer.id, vehicle_id=vehicle.id, inspection_session_id=session.id, source_type="customer_stated_reason", source_label="Prior check-in customer wording", source_reference_hmac=customer_search_token(actor.shop_id, "context_reference", str(session.id)), source_recorded_at=session.started_at, raw_content_ciphertext=encrypt_customer_data(body.customer_concern), reviewed_excerpt_ciphertext=encrypt_customer_data(body.customer_concern), encryption_key_id=customer_data_encryption_key_id(), review_state="reviewed", reviewed_by_user_id=actor.user_id, reviewed_at=datetime.utcnow(), created_at=datetime.utcnow()))
    if body.reason_context_record_id:
        _context_prompt_or_422(db, body.reason_context_record_id, actor, customer.id if customer else None, vehicle.id)
        db.add(IntakeReasonSuggestionSelection(shop_id=actor.shop_id, inspection_session_id=session.id, context_record_id=body.reason_context_record_id, source_key="reviewed_context", selected_by_user_id=actor.user_id, selected_at=datetime.utcnow()))
    elif body.reason_suggestion_id:
        suggestion = db.query(IntakeReasonSuggestion).filter(IntakeReasonSuggestion.id == body.reason_suggestion_id, IntakeReasonSuggestion.shop_id == actor.shop_id, IntakeReasonSuggestion.state == "approved").one_or_none()
        if not suggestion or (suggestion.customer_id and suggestion.customer_id != (customer.id if customer else None)) or (suggestion.vehicle_catalog_entry_id and suggestion.vehicle_catalog_entry_id != vehicle.vehicle_catalog_entry_id):
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="The selected wording prompt is not available for this customer and vehicle")
        db.add(IntakeReasonSuggestionSelection(shop_id=actor.shop_id, inspection_session_id=session.id, curated_suggestion_id=suggestion.id, source_key="curated_prompt", selected_by_user_id=actor.user_id, selected_at=datetime.utcnow()))
    if body.customer_contact:
        require_current_visit_release_enabled()
        normalized = normalize_contact(body.customer_contact.channel, body.customer_contact.destination)
        contact = CustomerContactPoint(shop_id=actor.shop_id, session_id=session.id, channel=body.customer_contact.channel, encrypted_destination=encrypt_contact(normalized), encryption_key_id=contact_encryption_key_id(), lookup_hmac=contact_lookup_hmac(normalized), verification_state="unverified", created_by_user_id=actor.user_id, created_at=datetime.utcnow())
        db.add(contact)
        db.flush()
        db.add_all([CommunicationConsent(contact_point_id=contact.id, purpose="current_visit_link", state=body.customer_contact.current_visit_link_consent, policy_version=_CONSENT_POLICY_VERSION, captured_by_user_id=actor.user_id, captured_at=datetime.utcnow()), CommunicationConsent(contact_point_id=contact.id, purpose="current_visit_progress", state=body.customer_contact.current_visit_progress_consent, policy_version=_CONSENT_POLICY_VERSION, captured_by_user_id=actor.user_id, captured_at=datetime.utcnow())])
    db.commit()
    db.refresh(session)
    return _session_payload(session)


def prune_expired_customer_context_records(db: Session) -> dict:
    """Purge expired raw context while retaining source metadata and reviewed excerpts for history."""
    now = datetime.utcnow()
    rows = db.query(CustomerContextRecord).filter(CustomerContextRecord.raw_content_ciphertext.isnot(None), CustomerContextRecord.raw_retention_until.isnot(None), CustomerContextRecord.raw_retention_until <= now).all()
    for row in rows:
        row.raw_content_ciphertext = None
        row.raw_purged_at = now
    if rows:
        db.commit()
    return {"raw_context_purged": len(rows)}
