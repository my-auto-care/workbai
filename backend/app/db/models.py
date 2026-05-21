import uuid
import enum
from datetime import datetime
from sqlalchemy import (
    Column, String, Text, Integer, Boolean, DateTime,
    ForeignKey, Enum as SAEnum, JSON
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
    completed = "completed"
    abandoned = "abandoned"


class FindingCondition(str, enum.Enum):
    good = "good"
    fair = "fair"
    poor = "poor"
    na = "na"


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
    created_at = Column(DateTime, default=datetime.utcnow)

    shop = relationship("Shop", back_populates="vehicles")
    sessions = relationship("InspectionSession", back_populates="vehicle")


class ChecklistTemplate(Base):
    __tablename__ = "checklist_templates"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(Text, nullable=False)
    vehicle_filter = Column(JSONB, default={})
    version = Column(Integer, default=1)
    items = Column(JSONB, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    sessions = relationship("InspectionSession", back_populates="checklist_template")


class InspectionSession(Base):
    __tablename__ = "inspection_sessions"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    shop_id = Column(UUID(as_uuid=True), ForeignKey("shops.id"), nullable=False)
    technician_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    vehicle_id = Column(UUID(as_uuid=True), ForeignKey("vehicles.id"), nullable=True)
    checklist_template_id = Column(UUID(as_uuid=True), ForeignKey("checklist_templates.id"))
    customer_concern = Column(Text)
    # Denormalized vehicle info for MVP (no pre-existing vehicle record required)
    vehicle_year = Column(String(10))
    vehicle_make = Column(String(100))
    vehicle_model = Column(String(100))
    vehicle_vin = Column(String(50))
    vehicle_mileage = Column(Integer, nullable=True)
    vehicle_intel = Column(JSONB, nullable=True)
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
    vehicle = relationship("Vehicle", back_populates="sessions")
    checklist_template = relationship("ChecklistTemplate", back_populates="sessions")
    findings = relationship("Finding", back_populates="session")
    media = relationship("Media", back_populates="session")


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
