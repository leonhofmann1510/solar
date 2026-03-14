"""meter readings table

Revision ID: 003
Revises: 002
Create Date: 2026-03-14
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "meter_readings",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "timestamp",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("consumption_kwh", sa.Float, nullable=False),
        sa.Column("feed_in_kwh", sa.Float, nullable=False),
    )
    op.create_index("ix_meter_readings_timestamp", "meter_readings", ["timestamp"])


def downgrade() -> None:
    op.drop_index("ix_meter_readings_timestamp", table_name="meter_readings")
    op.drop_table("meter_readings")
