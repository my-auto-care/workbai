"""add vehicle_mileage and ai_intel to inspection_sessions

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-05-20 23:00:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "b2c3d4e5f6a7"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("inspection_sessions", sa.Column("vehicle_mileage", sa.Integer(), nullable=True))
    op.add_column("inspection_sessions", sa.Column("vehicle_intel", JSONB(), nullable=True))


def downgrade():
    op.drop_column("inspection_sessions", "vehicle_intel")
    op.drop_column("inspection_sessions", "vehicle_mileage")
