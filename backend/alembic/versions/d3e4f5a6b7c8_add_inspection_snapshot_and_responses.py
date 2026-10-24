"""add template snapshots and controlled inspection responses

Revision ID: d3e4f5a6b7c8
Revises: b2c3d4e5f6a7
Create Date: 2026-10-22 19:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ENUM, JSONB, UUID

revision = "d3e4f5a6b7c8"
down_revision = "b2c3d4e5f6a7"
branch_labels = None
depends_on = None


def upgrade():
    # PostgreSQL enum values cannot be safely removed in downgrade, so the enum
    # extension intentionally remains when rolling this migration back.
    op.execute("ALTER TYPE sessionstatus ADD VALUE IF NOT EXISTS 'submitted'")
    op.add_column("inspection_sessions", sa.Column("presence_mode", sa.String(length=16), nullable=True))
    op.add_column("inspection_sessions", sa.Column("template_snapshot", JSONB(), nullable=True))
    op.add_column("inspection_sessions", sa.Column("template_version", sa.Integer(), nullable=True))
    op.add_column("inspection_sessions", sa.Column("inspection_submitted_at", sa.DateTime(), nullable=True))
    op.create_check_constraint(
        "ck_inspection_sessions_presence_mode",
        "inspection_sessions",
        "presence_mode IS NULL OR presence_mode IN ('waiter', 'dropoff')",
    )
    op.create_table(
        "inspection_item_responses",
        sa.Column("id", UUID(as_uuid=True), nullable=False),
        sa.Column("session_id", UUID(as_uuid=True), nullable=False),
        sa.Column("template_item_id", sa.Text(), nullable=False),
        sa.Column("condition", ENUM("good", "fair", "poor", "na", name="findingcondition", create_type=False), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("measurement", sa.Text(), nullable=True),
        sa.Column("response_data", JSONB(), nullable=True),
        sa.Column("recorded_by_user_id", UUID(as_uuid=True), nullable=False),
        sa.Column("recorded_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["recorded_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["session_id"], ["inspection_sessions.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("session_id", "template_item_id", name="uq_inspection_item_response"),
    )
    op.create_index("ix_inspection_item_responses_session_id", "inspection_item_responses", ["session_id"])


def downgrade():
    op.drop_index("ix_inspection_item_responses_session_id", table_name="inspection_item_responses")
    op.drop_table("inspection_item_responses")
    op.drop_constraint("ck_inspection_sessions_presence_mode", "inspection_sessions", type_="check")
    op.drop_column("inspection_sessions", "inspection_submitted_at")
    op.drop_column("inspection_sessions", "template_version")
    op.drop_column("inspection_sessions", "template_snapshot")
    op.drop_column("inspection_sessions", "presence_mode")
