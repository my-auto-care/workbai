"""add controlled template governance

Revision ID: f5a6b7c8d9e0
Revises: e4f5a6b7c8d9
Create Date: 2026-10-22 19:33:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


revision = "f5a6b7c8d9e0"
down_revision = "e4f5a6b7c8d9"
branch_labels = None
depends_on = None


template_lifecycle = sa.Enum("draft", "approved", "retired", name="templatelifecyclestatus")


def upgrade():
    template_lifecycle.create(op.get_bind(), checkfirst=True)
    op.add_column(
        "checklist_templates",
        sa.Column("lifecycle_status", template_lifecycle, nullable=False, server_default="draft"),
    )
    # Every pre-governance template is treated as legacy/provisional. A later
    # admin cannot turn it into an approved controlled artifact by entering a
    # convenient string/hash; a new governed draft is required instead.
    op.add_column(
        "checklist_templates",
        sa.Column("is_provisional", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.add_column(
        "checklist_templates",
        sa.Column("locked_provisional", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.add_column(
        "checklist_templates",
        sa.Column("active_for_new_visits", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column("checklist_templates", sa.Column("source_reference", sa.Text(), nullable=True))
    op.add_column("checklist_templates", sa.Column("source_sha256", sa.String(length=64), nullable=True))
    op.add_column("checklist_templates", sa.Column("approved_at", sa.DateTime(), nullable=True))
    op.add_column("checklist_templates", sa.Column("approved_by_user_id", UUID(as_uuid=True), nullable=True))
    op.add_column("checklist_templates", sa.Column("retired_at", sa.DateTime(), nullable=True))
    op.add_column("checklist_templates", sa.Column("retired_by_user_id", UUID(as_uuid=True), nullable=True))
    op.create_foreign_key("fk_checklist_templates_approved_by", "checklist_templates", "users", ["approved_by_user_id"], ["id"])
    op.create_foreign_key("fk_checklist_templates_retired_by", "checklist_templates", "users", ["retired_by_user_id"], ["id"])

    # Preserve the provenance that governed a real visit independently of later
    # template lifecycle transitions or future template revisions.
    op.add_column("inspection_sessions", sa.Column("template_source_reference", sa.Text(), nullable=True))
    op.add_column("inspection_sessions", sa.Column("template_source_sha256", sa.String(length=64), nullable=True))
    op.add_column("inspection_sessions", sa.Column("template_approved_at", sa.DateTime(), nullable=True))
    op.add_column("inspection_sessions", sa.Column("template_approved_by_user_id", UUID(as_uuid=True), nullable=True))
    op.create_foreign_key(
        "fk_inspection_sessions_template_approver",
        "inspection_sessions",
        "users",
        ["template_approved_by_user_id"],
        ["id"],
    )

    op.create_check_constraint(
        "ck_checklist_templates_active_requires_approved",
        "checklist_templates",
        "NOT active_for_new_visits OR (lifecycle_status = 'approved' AND NOT is_provisional)",
    )
    op.create_check_constraint(
        "ck_checklist_templates_locked_is_provisional",
        "checklist_templates",
        "NOT locked_provisional OR is_provisional",
    )
    op.create_check_constraint(
        "ck_checklist_templates_approved_provenance",
        "checklist_templates",
        "lifecycle_status <> 'approved' OR "
        "(NOT is_provisional AND source_reference IS NOT NULL AND length(trim(source_reference)) >= 3 "
        "AND source_sha256 ~ '^[a-f0-9]{64}$' AND approved_at IS NOT NULL AND approved_by_user_id IS NOT NULL)",
    )
    op.create_check_constraint(
        "ck_checklist_templates_retired_audit",
        "checklist_templates",
        "lifecycle_status <> 'retired' OR "
        "(NOT active_for_new_visits AND retired_at IS NOT NULL AND retired_by_user_id IS NOT NULL)",
    )
    op.execute(
        "CREATE UNIQUE INDEX uq_checklist_templates_single_active_approved "
        "ON checklist_templates (active_for_new_visits) WHERE active_for_new_visits = TRUE"
    )
    op.alter_column("checklist_templates", "lifecycle_status", server_default=None)
    op.alter_column("checklist_templates", "is_provisional", server_default=None)
    op.alter_column("checklist_templates", "locked_provisional", server_default=None)
    op.alter_column("checklist_templates", "active_for_new_visits", server_default=None)


def downgrade():
    op.execute("DROP INDEX IF EXISTS uq_checklist_templates_single_active_approved")
    op.drop_constraint("ck_checklist_templates_retired_audit", "checklist_templates", type_="check")
    op.drop_constraint("ck_checklist_templates_approved_provenance", "checklist_templates", type_="check")
    op.drop_constraint("ck_checklist_templates_locked_is_provisional", "checklist_templates", type_="check")
    op.drop_constraint("ck_checklist_templates_active_requires_approved", "checklist_templates", type_="check")
    op.drop_constraint("fk_inspection_sessions_template_approver", "inspection_sessions", type_="foreignkey")
    op.drop_column("inspection_sessions", "template_approved_by_user_id")
    op.drop_column("inspection_sessions", "template_approved_at")
    op.drop_column("inspection_sessions", "template_source_sha256")
    op.drop_column("inspection_sessions", "template_source_reference")
    op.drop_constraint("fk_checklist_templates_retired_by", "checklist_templates", type_="foreignkey")
    op.drop_constraint("fk_checklist_templates_approved_by", "checklist_templates", type_="foreignkey")
    op.drop_column("checklist_templates", "retired_by_user_id")
    op.drop_column("checklist_templates", "retired_at")
    op.drop_column("checklist_templates", "approved_by_user_id")
    op.drop_column("checklist_templates", "approved_at")
    op.drop_column("checklist_templates", "source_sha256")
    op.drop_column("checklist_templates", "source_reference")
    op.drop_column("checklist_templates", "active_for_new_visits")
    op.drop_column("checklist_templates", "locked_provisional")
    op.drop_column("checklist_templates", "is_provisional")
    op.drop_column("checklist_templates", "lifecycle_status")
    template_lifecycle.drop(op.get_bind(), checkfirst=True)
