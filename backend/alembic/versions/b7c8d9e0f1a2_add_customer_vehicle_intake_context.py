"""add encrypted customer vehicle intake context

Revision ID: b7c8d9e0f1a2
Revises: a6b7c8d9e0f1
Create Date: 2026-10-22 21:52:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "b7c8d9e0f1a2"
down_revision = "a6b7c8d9e0f1"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "customers",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("shop_id", UUID(as_uuid=True), sa.ForeignKey("shops.id"), nullable=False),
        sa.Column("display_name_encrypted", sa.Text(), nullable=False),
        sa.Column("encryption_key_id", sa.String(length=128), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_by_user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("id", "shop_id", name="uq_customers_id_shop"),
    )
    op.create_table(
        "vehicle_catalog_entries",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("source_name", sa.String(length=64), nullable=False),
        sa.Column("source_make_id", sa.String(length=64), nullable=False),
        sa.Column("source_model_id", sa.String(length=64), nullable=False),
        sa.Column("model_year", sa.Integer(), nullable=False),
        sa.Column("make", sa.String(length=100), nullable=False),
        sa.Column("model", sa.String(length=100), nullable=False),
        sa.Column("vehicle_type", sa.String(length=64), nullable=True),
        sa.Column("search_text", sa.Text(), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("source_retrieved_at", sa.DateTime(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("source_name", "model_year", "source_make_id", "source_model_id", name="uq_vehicle_catalog_source_model"),
        sa.CheckConstraint("model_year BETWEEN 1886 AND 2100", name="ck_vehicle_catalog_model_year"),
    )
    op.create_index("ix_vehicle_catalog_search_text", "vehicle_catalog_entries", ["search_text"])

    op.add_column("vehicles", sa.Column("vehicle_catalog_entry_id", UUID(as_uuid=True), nullable=True))
    op.add_column("vehicles", sa.Column("vin_encrypted", sa.Text(), nullable=True))
    op.add_column("vehicles", sa.Column("vin_encryption_key_id", sa.String(length=128), nullable=True))
    op.add_column("vehicles", sa.Column("vin_lookup_hmac", sa.String(length=64), nullable=True))
    op.add_column("vehicles", sa.Column("vin_tail_lookup_hmac", sa.String(length=64), nullable=True))
    op.create_foreign_key("fk_vehicles_catalog_entry", "vehicles", "vehicle_catalog_entries", ["vehicle_catalog_entry_id"], ["id"])
    op.create_unique_constraint("uq_vehicles_id_shop", "vehicles", ["id", "shop_id"])
    op.create_index("ix_vehicles_shop_vin_lookup", "vehicles", ["shop_id", "vin_lookup_hmac"])
    op.create_index("ix_vehicles_shop_vin_tail_lookup", "vehicles", ["shop_id", "vin_tail_lookup_hmac"])

    op.create_table(
        "customer_contact_methods",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("shop_id", UUID(as_uuid=True), nullable=False),
        sa.Column("customer_id", UUID(as_uuid=True), nullable=False),
        sa.Column("channel", sa.String(length=16), nullable=False),
        sa.Column("encrypted_destination", sa.Text(), nullable=False),
        sa.Column("encryption_key_id", sa.String(length=128), nullable=False),
        sa.Column("lookup_hmac", sa.String(length=64), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_by_user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("retired_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["customer_id", "shop_id"], ["customers.id", "customers.shop_id"], name="fk_customer_contact_customer_shop"),
        sa.CheckConstraint("channel IN ('sms', 'email')", name="ck_customer_contact_methods_channel"),
    )
    op.create_index("ix_customer_contact_methods_shop_lookup", "customer_contact_methods", ["shop_id", "lookup_hmac"])
    op.create_table(
        "customer_search_tokens",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("shop_id", UUID(as_uuid=True), nullable=False),
        sa.Column("customer_id", UUID(as_uuid=True), nullable=False),
        sa.Column("field", sa.String(length=32), nullable=False),
        sa.Column("token_hmac", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["customer_id", "shop_id"], ["customers.id", "customers.shop_id"], name="fk_customer_search_token_customer_shop"),
        sa.UniqueConstraint("customer_id", "field", "token_hmac", name="uq_customer_search_token"),
        sa.CheckConstraint("field IN ('name', 'phone', 'email', 'customer_number')", name="ck_customer_search_tokens_field"),
    )
    op.create_index("ix_customer_search_tokens_shop_token", "customer_search_tokens", ["shop_id", "token_hmac"])

    op.create_table(
        "customer_vehicle_links",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("shop_id", UUID(as_uuid=True), nullable=False),
        sa.Column("customer_id", UUID(as_uuid=True), nullable=False),
        sa.Column("vehicle_id", UUID(as_uuid=True), nullable=False),
        sa.Column("relationship_code", sa.String(length=32), nullable=False, server_default="customer_confirmed"),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("confirmed_by_user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("confirmed_at", sa.DateTime(), nullable=False),
        sa.Column("ended_by_user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("ended_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("id", "shop_id", name="uq_customer_vehicle_links_id_shop"),
        sa.ForeignKeyConstraint(["customer_id", "shop_id"], ["customers.id", "customers.shop_id"], name="fk_customer_vehicle_link_customer_shop"),
        sa.ForeignKeyConstraint(["vehicle_id", "shop_id"], ["vehicles.id", "vehicles.shop_id"], name="fk_customer_vehicle_link_vehicle_shop"),
        sa.CheckConstraint("relationship_code = 'customer_confirmed'", name="ck_customer_vehicle_links_relationship"),
        sa.CheckConstraint("active OR ended_at IS NOT NULL", name="ck_customer_vehicle_links_ended_audit"),
    )
    op.execute("CREATE UNIQUE INDEX uq_customer_vehicle_links_active ON customer_vehicle_links (customer_id, vehicle_id) WHERE active")
    op.create_index("ix_customer_vehicle_links_shop_customer", "customer_vehicle_links", ["shop_id", "customer_id", "active"])

    op.add_column("inspection_sessions", sa.Column("customer_id", UUID(as_uuid=True), nullable=True))
    op.add_column("inspection_sessions", sa.Column("customer_vehicle_link_id", UUID(as_uuid=True), nullable=True))
    op.create_unique_constraint("uq_inspection_sessions_id_shop", "inspection_sessions", ["id", "shop_id"])
    op.create_foreign_key("fk_inspection_sessions_customer_shop", "inspection_sessions", "customers", ["customer_id", "shop_id"], ["id", "shop_id"])
    op.create_foreign_key("fk_inspection_sessions_customer_vehicle_link_shop", "inspection_sessions", "customer_vehicle_links", ["customer_vehicle_link_id", "shop_id"], ["id", "shop_id"])
    op.create_foreign_key("fk_inspection_sessions_vehicle_shop", "inspection_sessions", "vehicles", ["vehicle_id", "shop_id"], ["id", "shop_id"])
    op.create_index("ix_inspection_sessions_shop_customer_started", "inspection_sessions", ["shop_id", "customer_id", "started_at"])

    op.create_table(
        "customer_context_records",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("shop_id", UUID(as_uuid=True), nullable=False),
        sa.Column("customer_id", UUID(as_uuid=True), nullable=True),
        sa.Column("vehicle_id", UUID(as_uuid=True), nullable=True),
        sa.Column("inspection_session_id", UUID(as_uuid=True), nullable=False),
        sa.Column("source_type", sa.String(length=32), nullable=False),
        sa.Column("source_label", sa.String(length=160), nullable=False),
        sa.Column("source_reference_hmac", sa.String(length=64), nullable=True),
        sa.Column("source_recorded_at", sa.DateTime(), nullable=False),
        sa.Column("appointment_at", sa.DateTime(), nullable=True),
        sa.Column("raw_content_ciphertext", sa.Text(), nullable=True),
        sa.Column("reviewed_excerpt_ciphertext", sa.Text(), nullable=False),
        sa.Column("encryption_key_id", sa.String(length=128), nullable=False),
        sa.Column("review_state", sa.String(length=32), nullable=False, server_default="reviewed"),
        sa.Column("reviewed_by_user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(), nullable=False),
        sa.Column("raw_retention_until", sa.DateTime(), nullable=True),
        sa.Column("raw_purged_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("id", "shop_id", name="uq_customer_context_records_id_shop"),
        sa.ForeignKeyConstraint(["customer_id", "shop_id"], ["customers.id", "customers.shop_id"], name="fk_customer_context_customer_shop"),
        sa.ForeignKeyConstraint(["vehicle_id", "shop_id"], ["vehicles.id", "vehicles.shop_id"], name="fk_customer_context_vehicle_shop"),
        sa.ForeignKeyConstraint(["inspection_session_id", "shop_id"], ["inspection_sessions.id", "inspection_sessions.shop_id"], name="fk_customer_context_session_shop"),
        sa.CheckConstraint("source_type IN ('phone_transcript', 'appointment_note', 'service_history', 'prior_visit', 'manual_note', 'customer_stated_reason')", name="ck_customer_context_source_type"),
        sa.CheckConstraint("review_state IN ('captured', 'reviewed', 'rejected')", name="ck_customer_context_review_state"),
        sa.CheckConstraint("source_type <> 'appointment_note' OR appointment_at IS NOT NULL", name="ck_customer_context_appointment_time"),
        sa.CheckConstraint("raw_retention_until IS NULL OR raw_content_ciphertext IS NOT NULL OR raw_purged_at IS NOT NULL", name="ck_customer_context_raw_lifecycle"),
    )
    op.create_index("ix_customer_context_shop_customer_time", "customer_context_records", ["shop_id", "customer_id", "source_recorded_at"])
    op.create_index("ix_customer_context_raw_expiry", "customer_context_records", ["raw_retention_until"])
    op.create_table(
        "customer_context_access_audits",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("shop_id", UUID(as_uuid=True), nullable=False),
        sa.Column("context_record_id", UUID(as_uuid=True), nullable=False),
        sa.Column("actor_user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("purpose", sa.String(length=64), nullable=False),
        sa.Column("occurred_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["context_record_id", "shop_id"], ["customer_context_records.id", "customer_context_records.shop_id"], name="fk_context_access_audit_context_shop"),
    )
    op.create_index("ix_customer_context_access_audit_record_time", "customer_context_access_audits", ["context_record_id", "occurred_at"])
    op.create_table(
        "customer_profile_access_audits",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("shop_id", UUID(as_uuid=True), nullable=False),
        sa.Column("customer_id", UUID(as_uuid=True), nullable=False),
        sa.Column("actor_user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("purpose", sa.String(length=64), nullable=False),
        sa.Column("occurred_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["customer_id", "shop_id"], ["customers.id", "customers.shop_id"], name="fk_customer_profile_access_audit_customer_shop"),
        sa.CheckConstraint("purpose IN ('incoming_call_context')", name="ck_customer_profile_access_audit_purpose"),
    )
    op.create_index("ix_customer_profile_access_audit_customer_time", "customer_profile_access_audits", ["customer_id", "occurred_at"])

    op.create_table(
        "intake_reason_suggestions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("shop_id", UUID(as_uuid=True), nullable=False),
        sa.Column("customer_id", UUID(as_uuid=True), nullable=True),
        sa.Column("vehicle_catalog_entry_id", UUID(as_uuid=True), sa.ForeignKey("vehicle_catalog_entries.id"), nullable=True),
        sa.Column("source_context_record_id", UUID(as_uuid=True), nullable=True),
        sa.Column("scope", sa.String(length=32), nullable=False),
        sa.Column("phrase_ciphertext", sa.Text(), nullable=False),
        sa.Column("phrase_hmac", sa.String(length=64), nullable=False),
        sa.Column("encryption_key_id", sa.String(length=128), nullable=False),
        sa.Column("source_label", sa.String(length=160), nullable=False),
        sa.Column("source_revision", sa.String(length=128), nullable=False),
        sa.Column("state", sa.String(length=32), nullable=False, server_default="approved"),
        sa.Column("approved_by_user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("approved_at", sa.DateTime(), nullable=False),
        sa.Column("retired_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["customer_id", "shop_id"], ["customers.id", "customers.shop_id"], name="fk_reason_suggestion_customer_shop"),
        sa.ForeignKeyConstraint(["source_context_record_id", "shop_id"], ["customer_context_records.id", "customer_context_records.shop_id"], name="fk_reason_suggestion_context_shop"),
        sa.CheckConstraint("scope IN ('shop_curated', 'vehicle_curated', 'customer_specific')", name="ck_reason_suggestions_scope"),
        sa.CheckConstraint("scope <> 'customer_specific' OR customer_id IS NOT NULL", name="ck_reason_suggestions_customer_scope"),
        sa.CheckConstraint("scope <> 'vehicle_curated' OR customer_id IS NULL", name="ck_reason_suggestions_vehicle_scope"),
        sa.CheckConstraint("source_context_record_id IS NULL OR scope = 'customer_specific'", name="ck_reason_suggestions_context_scope"),
        sa.CheckConstraint("state IN ('approved', 'retired')", name="ck_reason_suggestions_state"),
    )
    op.create_index("ix_reason_suggestions_shop_scope", "intake_reason_suggestions", ["shop_id", "scope", "state"])
    op.create_table(
        "intake_reason_suggestion_selections",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("shop_id", UUID(as_uuid=True), nullable=False),
        sa.Column("inspection_session_id", UUID(as_uuid=True), nullable=False),
        sa.Column("context_record_id", UUID(as_uuid=True), nullable=True),
        sa.Column("curated_suggestion_id", UUID(as_uuid=True), sa.ForeignKey("intake_reason_suggestions.id"), nullable=True),
        sa.Column("source_key", sa.String(length=64), nullable=False),
        sa.Column("selected_by_user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("selected_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["inspection_session_id", "shop_id"], ["inspection_sessions.id", "inspection_sessions.shop_id"], name="fk_reason_selection_session_shop"),
        sa.ForeignKeyConstraint(["context_record_id", "shop_id"], ["customer_context_records.id", "customer_context_records.shop_id"], name="fk_reason_selection_context_shop"),
        sa.CheckConstraint("(CASE WHEN context_record_id IS NULL THEN 0 ELSE 1 END) + (CASE WHEN curated_suggestion_id IS NULL THEN 0 ELSE 1 END) <= 1", name="ck_reason_selection_one_source"),
    )
    op.create_index("ix_reason_selection_session_time", "intake_reason_suggestion_selections", ["inspection_session_id", "selected_at"])


def downgrade():
    op.drop_index("ix_reason_selection_session_time", table_name="intake_reason_suggestion_selections")
    op.drop_table("intake_reason_suggestion_selections")
    op.drop_index("ix_reason_suggestions_shop_scope", table_name="intake_reason_suggestions")
    op.drop_table("intake_reason_suggestions")
    op.drop_index("ix_customer_profile_access_audit_customer_time", table_name="customer_profile_access_audits")
    op.drop_table("customer_profile_access_audits")
    op.drop_index("ix_customer_context_access_audit_record_time", table_name="customer_context_access_audits")
    op.drop_table("customer_context_access_audits")
    op.drop_index("ix_customer_context_raw_expiry", table_name="customer_context_records")
    op.drop_index("ix_customer_context_shop_customer_time", table_name="customer_context_records")
    op.drop_table("customer_context_records")
    op.drop_index("ix_inspection_sessions_shop_customer_started", table_name="inspection_sessions")
    op.drop_constraint("fk_inspection_sessions_vehicle_shop", "inspection_sessions", type_="foreignkey")
    op.drop_constraint("fk_inspection_sessions_customer_vehicle_link_shop", "inspection_sessions", type_="foreignkey")
    op.drop_constraint("fk_inspection_sessions_customer_shop", "inspection_sessions", type_="foreignkey")
    op.drop_constraint("uq_inspection_sessions_id_shop", "inspection_sessions", type_="unique")
    op.drop_column("inspection_sessions", "customer_vehicle_link_id")
    op.drop_column("inspection_sessions", "customer_id")
    op.execute("DROP INDEX IF EXISTS uq_customer_vehicle_links_active")
    op.drop_index("ix_customer_vehicle_links_shop_customer", table_name="customer_vehicle_links")
    op.drop_table("customer_vehicle_links")
    op.drop_index("ix_customer_search_tokens_shop_token", table_name="customer_search_tokens")
    op.drop_table("customer_search_tokens")
    op.drop_index("ix_customer_contact_methods_shop_lookup", table_name="customer_contact_methods")
    op.drop_table("customer_contact_methods")
    op.drop_index("ix_vehicles_shop_vin_lookup", table_name="vehicles")
    op.drop_index("ix_vehicles_shop_vin_tail_lookup", table_name="vehicles")
    op.drop_constraint("uq_vehicles_id_shop", "vehicles", type_="unique")
    op.drop_constraint("fk_vehicles_catalog_entry", "vehicles", type_="foreignkey")
    op.drop_column("vehicles", "vin_lookup_hmac")
    op.drop_column("vehicles", "vin_encryption_key_id")
    op.drop_column("vehicles", "vin_encrypted")
    op.drop_column("vehicles", "vin_tail_lookup_hmac")
    op.drop_column("vehicles", "vehicle_catalog_entry_id")
    op.drop_index("ix_vehicle_catalog_search_text", table_name="vehicle_catalog_entries")
    op.drop_table("vehicle_catalog_entries")
    op.drop_table("customers")
