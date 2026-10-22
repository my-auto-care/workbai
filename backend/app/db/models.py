import uuid
import enum
from datetime import datetime
from sqlalchemy import (
    Column, String, Text, Integer, Boolean, DateTime,
    ForeignKey, Enum as SAEnum, JSON, UniqueConstraint
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from .base import Base


def new_uuid():
    return str(uuid.uuid4())


class SubscriptionStatus(str, enum.Enum):
    trial = "trial"
    active = "active"
    past_due = "past_due"
    canceled = "canceled"


class UserRole(str, enum.Enum):
    technician = "technician"
    advisor = "advisor"
    admin = "admin"


class SessionStatus(str, enum.Enum):
    pending = "pending"
    in_progress = "in_progress"
    submitted = "submitted"
    advisor_reviewed = "advisor_reviewed"
    completed = "completed"
    abandoned = "abandoned"


class FindingCondition(str, enum.Enum):
    good = "good"
    fair = "fair"
    poor = "poor"
    na = "na"


class AdvisorDisposition(str, enum.Enum):
    safety = "safety"
    maintenance = "maintenance"
    visit_concern = "visit_concern"
    monitor = "monitor"
    no_action = "no_action"
    needs_clarification = "needs_clarification"


class TemplateLifecycleStatus(str, enum.Enum):
    draft = "draft"
    approved = "approved"
    retired = "retired"


class MediaType(str, enum.Enum):
    photo = "photo"
    video = "video"
    audio = "audio"


class CheckpointType(str, enum.Enum):
    sprint = "sprint"
    deploy = "deploy"
    decision = "decision"
    daily = "daily"
    manual = "manual"


class Shop(Base):
    __tablename__ = "shops"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(Text, nullable=False)
    subscription_status = Column(SAEnum(SubscriptionStatus), default=SubscriptionStatus.trial)
    stripe_customer_id = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    users = relationship("User", back_populates="shop")
    vehicles = relationship("Vehicle", back_populates="shop")
    customers = relationship("Customer", back_populates="shop")
    sessions = relationship("InspectionSession", back_populates="shop")


class User(Base):
    __tablename__ = "users"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    shop_id = Column(UUID(as_uuid=True), ForeignKey("shops.id"), nullable=False)
    auth0_id = Column(Text, unique=True, nullable=False)
    role = Column(SAEnum(UserRole), default=UserRole.technician)
    name = Column(Text, nullable=False)
    preferred_language = Column(Text, default="en")
    active = Column(Boolean, default=True)
    audio_training_opt_in = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    shop = relationship("Shop", back_populates="users")
    sessions = relationship("InspectionSession", back_populates="technician", foreign_keys="InspectionSession.technician_id")


class Vehicle(Base):
    __tablename__ = "vehicles"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    shop_id = Column(UUID(as_uuid=True), ForeignKey("shops.id"), nullable=False)
    vin = Column(Text)
    year = Column(Integer)
    make = Column(Text)
    model = Column(Text)
    mileage = Column(Integer)
    vehicle_catalog_entry_id = Column(UUID(as_uuid=True), ForeignKey("vehicle_catalog_entries.id"), nullable=True)
    vin_encrypted = Column(Text, nullable=True)
    vin_encryption_key_id = Column(String(128), nullable=True)
    vin_lookup_hmac = Column(String(64), nullable=True)
    vin_tail_lookup_hmac = Column(String(64), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    shop = relationship("Shop", back_populates="vehicles")
    sessions = relationship("InspectionSession", back_populates="vehicle")
    catalog_entry = relationship("VehicleCatalogEntry", back_populates="shop_vehicles")
    customer_links = relationship("CustomerVehicleLink", back_populates="vehicle")


class Customer(Base):
    """Staff-only customer profile. PII stays encrypted; lookup uses blind indexes."""

    __tablename__ = "customers"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    shop_id = Column(UUID(as_uuid=True), ForeignKey("shops.id"), nullable=False)
    display_name_encrypted = Column(Text, nullable=False)
    encryption_key_id = Column(String(128), nullable=False)
    active = Column(Boolean, nullable=False, default=True)
    created_by_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    shop = relationship("Shop", back_populates="customers")
    contacts = relationship("CustomerContactMethod", back_populates="customer")
    search_tokens = relationship("CustomerSearchToken", back_populates="customer")
    vehicle_links = relationship("CustomerVehicleLink", back_populates="customer")
    sessions = relationship("InspectionSession", back_populates="customer", foreign_keys="InspectionSession.customer_id")
    context_records = relationship("CustomerContextRecord", back_populates="customer")


class CustomerContactMethod(Base):
    """Long-lived profile contact, distinct from the visit-scoped Current Visit contact."""

    __tablename__ = "customer_contact_methods"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    shop_id = Column(UUID(as_uuid=True), ForeignKey("shops.id"), nullable=False)
    customer_id = Column(UUID(as_uuid=True), ForeignKey("customers.id"), nullable=False)
    channel = Column(String(16), nullable=False)
    encrypted_destination = Column(Text, nullable=False)
    encryption_key_id = Column(String(128), nullable=False)
    lookup_hmac = Column(String(64), nullable=False)
    active = Column(Boolean, nullable=False, default=True)
    created_by_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    retired_at = Column(DateTime, nullable=True)

    customer = relationship("Customer", back_populates="contacts")


class CustomerSearchToken(Base):
    """HMAC-only typeahead token. It contains no plaintext PII or reversible query."""

    __tablename__ = "customer_search_tokens"
    __table_args__ = (UniqueConstraint("customer_id", "field", "token_hmac", name="uq_customer_search_token"),)

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    shop_id = Column(UUID(as_uuid=True), ForeignKey("shops.id"), nullable=False)
    customer_id = Column(UUID(as_uuid=True), ForeignKey("customers.id"), nullable=False)
    field = Column(String(32), nullable=False)
    token_hmac = Column(String(64), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    customer = relationship("Customer", back_populates="search_tokens")


class VehicleCatalogEntry(Base):
    """Provider-sourced reference vehicle data; never a customer vehicle or diagnostic source."""

    __tablename__ = "vehicle_catalog_entries"
    __table_args__ = (UniqueConstraint("source_name", "model_year", "source_make_id", "source_model_id", name="uq_vehicle_catalog_source_model"),)

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_name = Column(String(64), nullable=False)
    source_make_id = Column(String(64), nullable=False)
    source_model_id = Column(String(64), nullable=False)
    model_year = Column(Integer, nullable=False)
    make = Column(String(100), nullable=False)
    model = Column(String(100), nullable=False)
    vehicle_type = Column(String(64), nullable=True)
    search_text = Column(Text, nullable=False)
    source_url = Column(Text, nullable=False)
    source_retrieved_at = Column(DateTime, nullable=False)
    active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    shop_vehicles = relationship("Vehicle", back_populates="catalog_entry")
    reason_suggestions = relationship("IntakeReasonSuggestion", back_populates="vehicle_catalog_entry")


class CustomerVehicleLink(Base):
    """Human-confirmed relationship; it does not establish legal ownership or authority."""

    __tablename__ = "customer_vehicle_links"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    shop_id = Column(UUID(as_uuid=True), ForeignKey("shops.id"), nullable=False)
    customer_id = Column(UUID(as_uuid=True), ForeignKey("customers.id"), nullable=False)
    vehicle_id = Column(UUID(as_uuid=True), ForeignKey("vehicles.id"), nullable=False)
    relationship_code = Column(String(32), nullable=False, default="customer_confirmed")
    active = Column(Boolean, nullable=False, default=True)
    confirmed_by_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    confirmed_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    ended_by_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    ended_at = Column(DateTime, nullable=True)

    customer = relationship("Customer", back_populates="vehicle_links")
    vehicle = relationship("Vehicle", back_populates="customer_links")


class CustomerContextRecord(Base):
    """Encrypted, visit-bound imported context excluded from normal history/report payloads."""

    __tablename__ = "customer_context_records"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    shop_id = Column(UUID(as_uuid=True), ForeignKey("shops.id"), nullable=False)
    customer_id = Column(UUID(as_uuid=True), ForeignKey("customers.id"), nullable=True)
    vehicle_id = Column(UUID(as_uuid=True), ForeignKey("vehicles.id"), nullable=True)
    inspection_session_id = Column(UUID(as_uuid=True), ForeignKey("inspection_sessions.id"), nullable=False)
    source_type = Column(String(32), nullable=False)
    source_label = Column(String(160), nullable=False)
    source_reference_hmac = Column(String(64), nullable=True)
    source_recorded_at = Column(DateTime, nullable=False)
    appointment_at = Column(DateTime, nullable=True)
    raw_content_ciphertext = Column(Text, nullable=True)
    reviewed_excerpt_ciphertext = Column(Text, nullable=False)
    encryption_key_id = Column(String(128), nullable=False)
    review_state = Column(String(32), nullable=False, default="reviewed")
    reviewed_by_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    reviewed_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    raw_retention_until = Column(DateTime, nullable=True)
    raw_purged_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    customer = relationship("Customer", back_populates="context_records")
    session = relationship("InspectionSession", foreign_keys=[inspection_session_id])


class CustomerContextAccessAudit(Base):
    """Factual log of raw-context reads; it never contains the context, query, or customer name."""

    __tablename__ = "customer_context_access_audits"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    shop_id = Column(UUID(as_uuid=True), ForeignKey("shops.id"), nullable=False)
    context_record_id = Column(UUID(as_uuid=True), ForeignKey("customer_context_records.id"), nullable=False)
    actor_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    purpose = Column(String(64), nullable=False)
    occurred_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class CustomerProfileAccessAudit(Base):
    """Minimal staff access audit for a protected customer card; no caller query or PII is retained."""

    __tablename__ = "customer_profile_access_audits"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    shop_id = Column(UUID(as_uuid=True), ForeignKey("shops.id"), nullable=False)
    customer_id = Column(UUID(as_uuid=True), ForeignKey("customers.id"), nullable=False)
    actor_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    purpose = Column(String(64), nullable=False)
    occurred_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class IntakeReasonSuggestion(Base):
    """Human-curated wording prompt with provenance; never a diagnosis or maintenance claim."""

    __tablename__ = "intake_reason_suggestions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    shop_id = Column(UUID(as_uuid=True), ForeignKey("shops.id"), nullable=False)
    customer_id = Column(UUID(as_uuid=True), ForeignKey("customers.id"), nullable=True)
    vehicle_catalog_entry_id = Column(UUID(as_uuid=True), ForeignKey("vehicle_catalog_entries.id"), nullable=True)
    source_context_record_id = Column(UUID(as_uuid=True), ForeignKey("customer_context_records.id"), nullable=True)
    scope = Column(String(32), nullable=False)
    phrase_ciphertext = Column(Text, nullable=False)
    phrase_hmac = Column(String(64), nullable=False)
    encryption_key_id = Column(String(128), nullable=False)
    source_label = Column(String(160), nullable=False)
    source_revision = Column(String(128), nullable=False)
    state = Column(String(32), nullable=False, default="approved")
    approved_by_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    approved_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    retired_at = Column(DateTime, nullable=True)

    vehicle_catalog_entry = relationship("VehicleCatalogEntry", back_populates="reason_suggestions")


class IntakeReasonSuggestionSelection(Base):
    """Append-only record of a source-backed wording draft selected for a canonical visit."""

    __tablename__ = "intake_reason_suggestion_selections"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    shop_id = Column(UUID(as_uuid=True), ForeignKey("shops.id"), nullable=False)
    inspection_session_id = Column(UUID(as_uuid=True), ForeignKey("inspection_sessions.id"), nullable=False)
    context_record_id = Column(UUID(as_uuid=True), ForeignKey("customer_context_records.id"), nullable=True)
    curated_suggestion_id = Column(UUID(as_uuid=True), ForeignKey("intake_reason_suggestions.id"), nullable=True)
    source_key = Column(String(64), nullable=False)
    selected_by_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    selected_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class ChecklistTemplate(Base):
    __tablename__ = "checklist_templates"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(Text, nullable=False)
    vehicle_filter = Column(JSONB, default={})
    version = Column(Integer, default=1)
    items = Column(JSONB, nullable=False)
    lifecycle_status = Column(SAEnum(TemplateLifecycleStatus), default=TemplateLifecycleStatus.draft, nullable=False)
    is_provisional = Column(Boolean, default=True, nullable=False)
    locked_provisional = Column(Boolean, default=False, nullable=False)
    active_for_new_visits = Column(Boolean, default=False, nullable=False)
    source_reference = Column(Text, nullable=True)
    source_sha256 = Column(String(64), nullable=True)
    approved_at = Column(DateTime, nullable=True)
    approved_by_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    retired_at = Column(DateTime, nullable=True)
    retired_by_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    sessions = relationship("InspectionSession", back_populates="checklist_template")
    approved_by = relationship("User", foreign_keys=[approved_by_user_id])
    retired_by = relationship("User", foreign_keys=[retired_by_user_id])


class InspectionSession(Base):
    __tablename__ = "inspection_sessions"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    shop_id = Column(UUID(as_uuid=True), ForeignKey("shops.id"), nullable=False)
    technician_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    vehicle_id = Column(UUID(as_uuid=True), ForeignKey("vehicles.id"), nullable=True)
    customer_id = Column(UUID(as_uuid=True), ForeignKey("customers.id"), nullable=True)
    customer_vehicle_link_id = Column(UUID(as_uuid=True), ForeignKey("customer_vehicle_links.id"), nullable=True)
    checklist_template_id = Column(UUID(as_uuid=True), ForeignKey("checklist_templates.id"))
    customer_concern = Column(Text)
    # Denormalized vehicle info for MVP (no pre-existing vehicle record required)
    vehicle_year = Column(String(10))
    vehicle_make = Column(String(100))
    vehicle_model = Column(String(100))
    vehicle_vin = Column(String(50))
    vehicle_mileage = Column(Integer, nullable=True)
    vehicle_intel = Column(JSONB, nullable=True)
    # Controlled immutable snapshot of the exact approved template used by this visit.
    presence_mode = Column(String(16), nullable=True)
    template_snapshot = Column(JSONB, nullable=True)
    template_version = Column(Integer, nullable=True)
    template_source_reference = Column(Text, nullable=True)
    template_source_sha256 = Column(String(64), nullable=True)
    template_approved_at = Column(DateTime, nullable=True)
    template_approved_by_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    inspection_submitted_at = Column(DateTime, nullable=True)
    advisor_reviewed_at = Column(DateTime, nullable=True)
    advisor_reviewed_by_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    # Dispatch: technician assigned by shop manager
    assigned_technician_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    status = Column(SAEnum(SessionStatus), default=SessionStatus.in_progress)
    started_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    session_audio_s3_key = Column(Text)
    audio_retention_until = Column(DateTime)

    shop = relationship("Shop", back_populates="sessions")
    technician = relationship("User", back_populates="sessions", foreign_keys=[technician_id])
    assigned_technician = relationship("User", foreign_keys=[assigned_technician_id])
    advisor_reviewer = relationship("User", foreign_keys=[advisor_reviewed_by_user_id])
    template_approver = relationship("User", foreign_keys=[template_approved_by_user_id])
    vehicle = relationship("Vehicle", back_populates="sessions")
    customer = relationship("Customer", back_populates="sessions", foreign_keys=[customer_id])
    customer_vehicle_link = relationship("CustomerVehicleLink", foreign_keys=[customer_vehicle_link_id])
    checklist_template = relationship("ChecklistTemplate", back_populates="sessions")
    findings = relationship("Finding", back_populates="session")
    media = relationship("Media", back_populates="session")
    item_responses = relationship("InspectionItemResponse", back_populates="session")
    advisor_review_items = relationship("AdvisorReviewItem", back_populates="session")
    customer_contacts = relationship("CustomerContactPoint", back_populates="session")
    current_visit_release = relationship("CurrentVisitRelease", back_populates="session", uselist=False)


class Finding(Base):
    __tablename__ = "findings"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(UUID(as_uuid=True), ForeignKey("inspection_sessions.id"), nullable=False)
    checklist_item_id = Column(Text)
    transcript = Column(Text)
    structured_data = Column(JSONB, default={})
    condition = Column(SAEnum(FindingCondition), default=FindingCondition.na)
    created_at = Column(DateTime, default=datetime.utcnow)

    session = relationship("InspectionSession", back_populates="findings")
    media = relationship("Media", back_populates="finding")


class InspectionItemResponse(Base):
    """One technician-controlled response per item in a visit template snapshot."""

    __tablename__ = "inspection_item_responses"
    __table_args__ = (
        UniqueConstraint("session_id", "template_item_id", name="uq_inspection_item_response"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(UUID(as_uuid=True), ForeignKey("inspection_sessions.id"), nullable=False)
    template_item_id = Column(Text, nullable=False)
    condition = Column(SAEnum(FindingCondition), nullable=False)
    note = Column(Text, nullable=True)
    measurement = Column(Text, nullable=True)
    response_data = Column(JSONB, default={})
    recorded_by_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    recorded_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    session = relationship("InspectionSession", back_populates="item_responses")


class AdvisorReviewItem(Base):
    """Human advisor disposition; never a rewrite of technician evidence or customer action."""

    __tablename__ = "advisor_review_items"
    __table_args__ = (
        UniqueConstraint("session_id", "template_item_id", name="uq_advisor_review_item"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(UUID(as_uuid=True), ForeignKey("inspection_sessions.id"), nullable=False)
    template_item_id = Column(Text, nullable=False)
    disposition = Column(SAEnum(AdvisorDisposition), nullable=False)
    rationale = Column(Text, nullable=False)
    reviewed_by_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    session = relationship("InspectionSession", back_populates="advisor_review_items")
    reviewer = relationship("User", foreign_keys=[reviewed_by_user_id])


class CustomerContactPoint(Base):
    """Per-visit encrypted contact channel; never customer identity or authority."""

    __tablename__ = "customer_contact_points"
    __table_args__ = (UniqueConstraint("session_id", "channel", name="uq_customer_contact_points_session_channel"),)

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    shop_id = Column(UUID(as_uuid=True), ForeignKey("shops.id"), nullable=False)
    session_id = Column(UUID(as_uuid=True), ForeignKey("inspection_sessions.id"), nullable=False)
    channel = Column(String(16), nullable=False)
    encrypted_destination = Column(Text, nullable=False)
    encryption_key_id = Column(String(128), nullable=False)
    lookup_hmac = Column(String(64), nullable=False)
    verification_state = Column(String(32), nullable=False, default="unverified")
    verification_method = Column(String(64), nullable=True)
    verified_at = Column(DateTime, nullable=True)
    verified_by_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    created_by_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    session = relationship("InspectionSession", back_populates="customer_contacts")


class CommunicationConsent(Base):
    """Purpose-specific consent. Verification and contact possession are not consent."""

    __tablename__ = "communication_consents"
    __table_args__ = (UniqueConstraint("contact_point_id", "purpose", name="uq_communication_consents_contact_purpose"),)

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    contact_point_id = Column(UUID(as_uuid=True), ForeignKey("customer_contact_points.id"), nullable=False)
    purpose = Column(String(48), nullable=False)
    state = Column(String(32), nullable=False)
    policy_version = Column(String(64), nullable=False)
    captured_by_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    captured_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    revoked_by_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    revoked_at = Column(DateTime, nullable=True)


class CustomerReleaseManagerGrant(Base):
    """Explicit per-shop delegation; admin/advisor role alone never permits release."""

    __tablename__ = "customer_release_manager_grants"
    __table_args__ = (UniqueConstraint("shop_id", "user_id", name="uq_customer_release_manager_grant"),)

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    shop_id = Column(UUID(as_uuid=True), ForeignKey("shops.id"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    active = Column(Boolean, nullable=False, default=True)
    granted_by_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    granted_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    revoked_by_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    revoked_at = Column(DateTime, nullable=True)


class CurrentVisitRelease(Base):
    """Server-owned state for a scoped customer projection, separate from inspection state."""

    __tablename__ = "current_visit_releases"
    __table_args__ = (UniqueConstraint("inspection_session_id", name="uq_current_visit_release_session"),)

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    shop_id = Column(UUID(as_uuid=True), ForeignKey("shops.id"), nullable=False)
    inspection_session_id = Column(UUID(as_uuid=True), ForeignKey("inspection_sessions.id"), nullable=False)
    state = Column(String(32), nullable=False, default="draft")
    human_owner_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    source_template_sha256 = Column(String(64), nullable=False)
    source_advisor_reviewed_at = Column(DateTime, nullable=False)
    source_advisor_reviewed_by_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    active_projection_revision = Column(Integer, nullable=True)
    prepared_by_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    prepared_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    approved_by_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    approved_at = Column(DateTime, nullable=True)
    revoked_by_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    revoked_at = Column(DateTime, nullable=True)
    revocation_reason = Column(String(64), nullable=True)

    session = relationship("InspectionSession", back_populates="current_visit_release")
    projections = relationship("CurrentVisitProjectionRevision", back_populates="release")
    links = relationship("CustomerPublicLink", back_populates="release")


class CurrentVisitProjectionRevision(Base):
    """Immutable allowlisted customer-safe content revision, never an internal report dump."""

    __tablename__ = "current_visit_projection_revisions"
    __table_args__ = (UniqueConstraint("release_id", "revision", name="uq_current_visit_projection_revision"),)

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    release_id = Column(UUID(as_uuid=True), ForeignKey("current_visit_releases.id"), nullable=False)
    revision = Column(Integer, nullable=False)
    state = Column(String(32), nullable=False, default="draft")
    status_code = Column(String(64), nullable=False)
    schema_version = Column(Integer, nullable=False, default=1)
    payload_json = Column(JSONB, nullable=False)
    payload_sha256 = Column(String(64), nullable=False)
    prepared_by_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    prepared_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    approved_by_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    approved_at = Column(DateTime, nullable=True)

    release = relationship("CurrentVisitRelease", back_populates="projections")


class CustomerPublicLink(Base):
    """Opaque bearer view link. Its plaintext secret is never persisted."""

    __tablename__ = "customer_public_links"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    release_id = Column(UUID(as_uuid=True), ForeignKey("current_visit_releases.id"), nullable=False)
    purpose = Column(String(16), nullable=False)
    secret_hmac = Column(String(64), nullable=False, unique=True)
    hmac_key_id = Column(String(128), nullable=False)
    state = Column(String(32), nullable=False, default="active")
    issued_by_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    issued_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    revoked_by_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    revoked_at = Column(DateTime, nullable=True)
    revocation_reason = Column(String(64), nullable=True)
    last_accessed_at = Column(DateTime, nullable=True)

    release = relationship("CurrentVisitRelease", back_populates="links")


class CurrentVisitReleaseAudit(Base):
    """Append-only factual release audit. Never store contacts, URLs, or plaintext link secrets."""

    __tablename__ = "current_visit_release_audits"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    shop_id = Column(UUID(as_uuid=True), ForeignKey("shops.id"), nullable=False)
    inspection_session_id = Column(UUID(as_uuid=True), ForeignKey("inspection_sessions.id"), nullable=False)
    release_id = Column(UUID(as_uuid=True), ForeignKey("current_visit_releases.id"), nullable=True)
    action = Column(String(64), nullable=False)
    actor_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    reason_code = Column(String(64), nullable=True)
    release_state = Column(String(32), nullable=True)
    projection_sha256 = Column(String(64), nullable=True)
    occurred_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class CustomerPublicAccessAudit(Base):
    """Token-free, minimized public audit evidence with explicit retention."""

    __tablename__ = "customer_public_access_audits"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    link_id = Column(UUID(as_uuid=True), ForeignKey("customer_public_links.id"), nullable=True)
    outcome = Column(String(32), nullable=False)
    client_ip_hmac = Column(String(64), nullable=False)
    occurred_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    expires_at = Column(DateTime, nullable=False)


class CurrentVisitRateLimitBucket(Base):
    """Short-lived atomic public rate counter; no raw IP, token, or user agent."""

    __tablename__ = "current_visit_rate_limit_buckets"
    __table_args__ = (UniqueConstraint("scope", "key_hmac", "window_started_at", name="uq_current_visit_rate_limit_bucket"),)

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    scope = Column(String(16), nullable=False)
    key_hmac = Column(String(64), nullable=False)
    window_started_at = Column(DateTime, nullable=False)
    request_count = Column(Integer, nullable=False, default=1)
    expires_at = Column(DateTime, nullable=False)


class Media(Base):
    __tablename__ = "media"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(UUID(as_uuid=True), ForeignKey("inspection_sessions.id"), nullable=False)
    finding_id = Column(UUID(as_uuid=True), ForeignKey("findings.id"), nullable=True)
    media_type = Column(SAEnum(MediaType), default=MediaType.photo)
    s3_key = Column(Text, nullable=False)
    ai_analysis = Column(JSONB, default={})
    created_at = Column(DateTime, default=datetime.utcnow)

    session = relationship("InspectionSession", back_populates="media")
    finding = relationship("Finding", back_populates="media")


class Checkpoint(Base):
    __tablename__ = "checkpoints"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    checkpoint_id = Column(Text, unique=True, nullable=False)
    type = Column(SAEnum(CheckpointType), default=CheckpointType.manual)
    created_at = Column(DateTime, default=datetime.utcnow)
    git_tag = Column(Text)
    db_snapshot_id = Column(Text)
    spaces_manifest_key = Column(Text)
    zeptoclaw_memory_key = Column(Text)
    metrics_snapshot = Column(JSONB, default={})
    decision_log_delta = Column(JSONB, default={})
    sha256_manifest = Column(Text)
    notes = Column(Text)
    created_by = Column(Text, default="zeptoclaw")
