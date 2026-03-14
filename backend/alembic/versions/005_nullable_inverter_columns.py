"""make grid_power_w, house_load_w, feed_in_today_kwh, grid_buy_today_kwh nullable

Revision ID: 005
Revises: 004
Create Date: 2026-03-14
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "005"
down_revision: Union[str, None] = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column("inverter_readings", "grid_power_w", existing_type=sa.Float(), nullable=True)
    op.alter_column("inverter_readings", "house_load_w", existing_type=sa.Float(), nullable=True)
    op.alter_column("inverter_readings", "feed_in_today_kwh", existing_type=sa.Float(), nullable=True)
    op.alter_column("inverter_readings", "grid_buy_today_kwh", existing_type=sa.Float(), nullable=True)


def downgrade() -> None:
    op.execute("UPDATE inverter_readings SET grid_power_w = 0 WHERE grid_power_w IS NULL")
    op.execute("UPDATE inverter_readings SET house_load_w = 0 WHERE house_load_w IS NULL")
    op.execute("UPDATE inverter_readings SET feed_in_today_kwh = 0 WHERE feed_in_today_kwh IS NULL")
    op.execute("UPDATE inverter_readings SET grid_buy_today_kwh = 0 WHERE grid_buy_today_kwh IS NULL")
    op.alter_column("inverter_readings", "grid_power_w", existing_type=sa.Float(), nullable=False)
    op.alter_column("inverter_readings", "house_load_w", existing_type=sa.Float(), nullable=False)
    op.alter_column("inverter_readings", "feed_in_today_kwh", existing_type=sa.Float(), nullable=False)
    op.alter_column("inverter_readings", "grid_buy_today_kwh", existing_type=sa.Float(), nullable=False)
