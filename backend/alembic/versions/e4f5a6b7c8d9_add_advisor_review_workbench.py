"""add advisor review workbench

Revision ID: e4f5a6b7c8d9
Revises: d3e4f5a6b7c8
Create Date: 2026-10-22 19:25:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "e4f5a6b7c8d9"
down_revision = "d3e4f5a6b7c8"
branch_labels = None
depends_on = None


def upgrade():
    # PostgreSQL enum values cannot be safely removed during a downgrade.
    op.execute("ALTER TYPE sessionstatus ADD VALUE IF NOT EXISTS 'advisor_reviewed'")
    op.add_column("inspection_sessions", sa.Column("advisor_reviewed_at", sa.DateTime(), nullable=True))
    op.add_column("inspection_sessions", sa.Column("advisor_reviewed_by_user_id", UUID(as_uuid=True), nullable=True))
    op.create_foreign_key(
        "fk_inspection_sessions_advisor_reviewer",
        "inspection_sessions",
        "users",
        ["advisor_reviewed_by_user_id"],
        ["id"],
    )
    op.create_table(
        "advisor_review_items",
        sa.Column("id", UUID(as_uuid=True), nullable=False),
        sa.Column("session_id", UUID(as_uuid=True), nullable=False),
        sa.Column("template_item_id", sa.Text(), nullable=False),
        sa.Column(
            "disposition",
            sa.Enum(
                "safety",
                "maintenance",
                "visit_concern",
                "monitor",
                "no_action",
                "needs_clarification",
                name="advisordisposition",
            ),
            nullable=False,
        ),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("reviewed_by_user_id", UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["reviewed_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["session_id"], ["inspection_sessions.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("session_id", "template_item_id", name="uq_advisor_review_item"),
    )
    op.create_index("ix_advisor_review_items_session_id", "advisor_review_items", ["session_id"])


def downgrade():
    op.drop_index("ix_advisor_review_items_session_id", table_name="advisor_review_items")
    op.drop_table("advisor_review_items")
    op.drop_constraint("fk_inspection_sessions_advisor_reviewer", "inspection_sessions", type_="foreignkey")
    op.drop_column("inspection_sessions", "advisor_reviewed_by_user_id")
    op.drop_column("inspection_sessions", "advisor_reviewed_at")
