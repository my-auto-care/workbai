"""add vehicle fields and dispatch to sessions

Revision ID: a1b2c3d4e5f6
Revises: cdd85abe09c1
Create Date: 2026-05-19 12:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision = "a1b2c3d4e5f6"
down_revision = "cdd85abe09c1"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("inspection_sessions", sa.Column("vehicle_year", sa.String(10), nullable=True))
    op.add_column("inspection_sessions", sa.Column("vehicle_make", sa.String(100), nullable=True))
    op.add_column("inspection_sessions", sa.Column("vehicle_model", sa.String(100), nullable=True))
    op.add_column("inspection_sessions", sa.Column("vehicle_vin", sa.String(50), nullable=True))
    op.add_column("inspection_sessions", sa.Column("assigned_technician_id", sa.UUID(), nullable=True))
    op.create_foreign_key(
        "fk_sessions_assigned_tech",
        "inspection_sessions", "users",
        ["assigned_technician_id"], ["id"]
    )
    op.alter_column("inspection_sessions", "vehicle_id", nullable=True)
    op.execute("ALTER TYPE sessionstatus ADD VALUE IF NOT EXISTS 'pending' BEFORE 'in_progress'")


def downgrade():
    op.drop_constraint("fk_sessions_assigned_tech", "inspection_sessions", type_="foreignkey")
    op.drop_column("inspection_sessions", "assigned_technician_id")
    op.drop_column("inspection_sessions", "vehicle_vin")
    op.drop_column("inspection_sessions", "vehicle_model")
    op.drop_column("inspection_sessions", "vehicle_make")
    op.drop_column("inspection_sessions", "vehicle_year")
