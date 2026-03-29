"""rename meter_readings columns: _w → _kwh

Revision ID: 004
Revises: 003
Create Date: 2026-03-14
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    cols = {
        row[0]
        for row in conn.execute(
            sa.text(
                "SELECT column_name FROM information_schema.columns"
                " WHERE table_name='meter_readings'"
            )
        )
    }
    if "consumption_w" in cols:
        op.alter_column("meter_readings", "consumption_w", new_column_name="consumption_kwh")
        op.alter_column("meter_readings", "feed_in_w", new_column_name="feed_in_kwh")


def downgrade() -> None:
    op.alter_column("meter_readings", "consumption_kwh", new_column_name="consumption_w")
    op.alter_column("meter_readings", "feed_in_kwh", new_column_name="feed_in_w")
