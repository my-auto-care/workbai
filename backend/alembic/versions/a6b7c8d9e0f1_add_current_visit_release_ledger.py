"""add current visit release ledger

Revision ID: a6b7c8d9e0f1
Revises: f5a6b7c8d9e0
Create Date: 2026-10-22 20:14:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB


revision = "a6b7c8d9e0f1"
down_revision = "f5a6b7c8d9e0"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "customer_contact_points",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("shop_id", UUID(as_uuid=True), sa.ForeignKey("shops.id"), nullable=False),
        sa.Column("session_id", UUID(as_uuid=True), sa.ForeignKey("inspection_sessions.id"), nullable=False),
        sa.Column("channel", sa.String(length=16), nullable=False),
        sa.Column("encrypted_destination", sa.Text(), nullable=False),
        sa.Column("encryption_key_id", sa.String(length=128), nullable=False),
        sa.Column("lookup_hmac", sa.String(length=64), nullable=False),
        sa.Column("verification_state", sa.String(length=32), nullable=False, server_default="unverified"),
        sa.Column("verification_method", sa.String(length=64), nullable=True),
        sa.Column("verified_at", sa.DateTime(), nullable=True),
        sa.Column("verified_by_user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_by_user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("session_id", "channel", name="uq_customer_contact_points_session_channel"),
        sa.CheckConstraint("channel IN ('sms', 'email')", name="ck_customer_contact_points_channel"),
    )
    op.create_index("ix_customer_contact_points_shop_lookup", "customer_contact_points", ["shop_id", "lookup_hmac"])

    op.create_table(
        "communication_consents",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("contact_point_id", UUID(as_uuid=True), sa.ForeignKey("customer_contact_points.id"), nullable=False),
        sa.Column("purpose", sa.String(length=48), nullable=False),
        sa.Column("state", sa.String(length=32), nullable=False),
        sa.Column("policy_version", sa.String(length=64), nullable=False),
        sa.Column("captured_by_user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("captured_at", sa.DateTime(), nullable=False),
        sa.Column("revoked_by_user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("contact_point_id", "purpose", name="uq_communication_consents_contact_purpose"),
        sa.CheckConstraint("purpose IN ('current_visit_link', 'current_visit_progress')", name="ck_communication_consents_purpose"),
        sa.CheckConstraint("state IN ('granted', 'declined', 'not_asked', 'revoked')", name="ck_communication_consents_state"),
    )

    op.create_table(
        "customer_release_manager_grants",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("shop_id", UUID(as_uuid=True), sa.ForeignKey("shops.id"), nullable=False),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("granted_by_user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("granted_at", sa.DateTime(), nullable=False),
        sa.Column("revoked_by_user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("shop_id", "user_id", name="uq_customer_release_manager_grant"),
    )

    op.create_table(
        "current_visit_releases",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("shop_id", UUID(as_uuid=True), sa.ForeignKey("shops.id"), nullable=False),
        sa.Column("inspection_session_id", UUID(as_uuid=True), sa.ForeignKey("inspection_sessions.id"), nullable=False),
        sa.Column("state", sa.String(length=32), nullable=False, server_default="draft"),
        sa.Column("human_owner_user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("source_template_sha256", sa.String(length=64), nullable=False),
        sa.Column("source_advisor_reviewed_at", sa.DateTime(), nullable=False),
        sa.Column("source_advisor_reviewed_by_user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("active_projection_revision", sa.Integer(), nullable=True),
        sa.Column("prepared_by_user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("prepared_at", sa.DateTime(), nullable=False),
        sa.Column("approved_by_user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("approved_at", sa.DateTime(), nullable=True),
        sa.Column("revoked_by_user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
        sa.Column("revocation_reason", sa.String(length=64), nullable=True),
        sa.UniqueConstraint("inspection_session_id", name="uq_current_visit_release_session"),
        sa.CheckConstraint("state IN ('draft', 'manager_approved', 'active', 'revoked')", name="ck_current_visit_releases_state"),
    )

    op.create_table(
        "current_visit_projection_revisions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("release_id", UUID(as_uuid=True), sa.ForeignKey("current_visit_releases.id"), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("state", sa.String(length=32), nullable=False, server_default="draft"),
        sa.Column("status_code", sa.String(length=64), nullable=False),
        sa.Column("schema_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("payload_json", JSONB(), nullable=False),
        sa.Column("payload_sha256", sa.String(length=64), nullable=False),
        sa.Column("prepared_by_user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("prepared_at", sa.DateTime(), nullable=False),
        sa.Column("approved_by_user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("approved_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("release_id", "revision", name="uq_current_visit_projection_revision"),
        sa.CheckConstraint("state IN ('draft', 'manager_approved')", name="ck_current_visit_projection_revisions_state"),
        sa.CheckConstraint("status_code IN ('checked_in', 'inspection_underway', 'team_reviewing', 'shop_update_available')", name="ck_current_visit_projection_status"),
    )

    op.create_table(
        "customer_public_links",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("release_id", UUID(as_uuid=True), sa.ForeignKey("current_visit_releases.id"), nullable=False),
        sa.Column("purpose", sa.String(length=16), nullable=False),
        sa.Column("secret_hmac", sa.String(length=64), nullable=False, unique=True),
        sa.Column("hmac_key_id", sa.String(length=128), nullable=False),
        sa.Column("state", sa.String(length=32), nullable=False, server_default="active"),
        sa.Column("issued_by_user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("issued_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("revoked_by_user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
        sa.Column("revocation_reason", sa.String(length=64), nullable=True),
        sa.Column("last_accessed_at", sa.DateTime(), nullable=True),
        sa.CheckConstraint("purpose IN ('counter', 'sms', 'email')", name="ck_customer_public_links_purpose"),
        sa.CheckConstraint("state IN ('active', 'revoked', 'expired')", name="ck_customer_public_links_state"),
    )
    op.execute("CREATE UNIQUE INDEX uq_customer_public_links_one_active_per_release ON customer_public_links (release_id) WHERE state = 'active'")

    op.create_table(
        "current_visit_release_audits",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("shop_id", UUID(as_uuid=True), sa.ForeignKey("shops.id"), nullable=False),
        sa.Column("inspection_session_id", UUID(as_uuid=True), sa.ForeignKey("inspection_sessions.id"), nullable=False),
        sa.Column("release_id", UUID(as_uuid=True), sa.ForeignKey("current_visit_releases.id"), nullable=True),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("actor_user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("reason_code", sa.String(length=64), nullable=True),
        sa.Column("release_state", sa.String(length=32), nullable=True),
        sa.Column("projection_sha256", sa.String(length=64), nullable=True),
        sa.Column("occurred_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_current_visit_release_audits_session_time", "current_visit_release_audits", ["inspection_session_id", "occurred_at"])

    op.create_table(
        "customer_public_access_audits",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("link_id", UUID(as_uuid=True), sa.ForeignKey("customer_public_links.id"), nullable=True),
        sa.Column("outcome", sa.String(length=32), nullable=False),
        sa.Column("client_ip_hmac", sa.String(length=64), nullable=False),
        sa.Column("occurred_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_customer_public_access_audits_expires", "customer_public_access_audits", ["expires_at"])
    op.create_table(
        "current_visit_rate_limit_buckets",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("scope", sa.String(length=16), nullable=False),
        sa.Column("key_hmac", sa.String(length=64), nullable=False),
        sa.Column("window_started_at", sa.DateTime(), nullable=False),
        sa.Column("request_count", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("scope", "key_hmac", "window_started_at", name="uq_current_visit_rate_limit_bucket"),
        sa.CheckConstraint("scope IN ('ip', 'link')", name="ck_current_visit_rate_limit_scope"),
    )
    op.create_index("ix_current_visit_rate_limit_buckets_expires", "current_visit_rate_limit_buckets", ["expires_at"])


def downgrade():
    op.drop_index("ix_current_visit_rate_limit_buckets_expires", table_name="current_visit_rate_limit_buckets")
    op.drop_table("current_visit_rate_limit_buckets")
    op.drop_index("ix_current_visit_release_audits_session_time", table_name="current_visit_release_audits")
    op.drop_table("current_visit_release_audits")
    op.drop_index("ix_customer_public_access_audits_expires", table_name="customer_public_access_audits")
    op.drop_table("customer_public_access_audits")
    op.execute("DROP INDEX IF EXISTS uq_customer_public_links_one_active_per_release")
    op.drop_table("customer_public_links")
    op.drop_table("current_visit_projection_revisions")
    op.drop_table("current_visit_releases")
    op.drop_table("customer_release_manager_grants")
    op.drop_table("communication_consents")
    op.drop_index("ix_customer_contact_points_shop_lookup", table_name="customer_contact_points")
    op.drop_table("customer_contact_points")
