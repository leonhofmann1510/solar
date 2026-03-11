"""initial schema

Revision ID: 001
Revises:
Create Date: 2026-03-11
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "inverter_readings",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), server_default=sa.func.now(), index=True),
        sa.Column("inverter_id", sa.String(16), nullable=False),
        sa.Column("pv_power_w", sa.Float, nullable=False),
        sa.Column("pv_string1_w", sa.Float, nullable=False),
        sa.Column("pv_string2_w", sa.Float, nullable=False),
        sa.Column("battery_soc_pct", sa.Float, nullable=True),
        sa.Column("battery_power_w", sa.Float, nullable=True),
        sa.Column("grid_power_w", sa.Float, nullable=False),
        sa.Column("house_load_w", sa.Float, nullable=False),
        sa.Column("pv_yield_today_kwh", sa.Float, nullable=False),
        sa.Column("feed_in_today_kwh", sa.Float, nullable=False),
        sa.Column("grid_buy_today_kwh", sa.Float, nullable=False),
        sa.Column("inverter_temp_c", sa.Float, nullable=False),
        sa.Column("grid_frequency_hz", sa.Float, nullable=False),
    )

    op.create_table(
        "rules",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(255), unique=True, nullable=False),
        sa.Column("enabled", sa.Boolean, default=True),
        sa.Column("condition_logic", sa.String(3), default="AND"),
        sa.Column("conditions", JSONB, nullable=False),
        sa.Column("actions", JSONB, nullable=False),
        sa.Column("on_clear_action", sa.String(16), default="none"),
        sa.Column("on_clear_payload", sa.Text, nullable=True),
        sa.Column("cooldown_seconds", sa.Integer, default=0),
        sa.Column("last_fired_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("state", sa.String(16), default="idle"),
    )

    op.create_table(
        "rule_events",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("rule_id", sa.Integer, nullable=False),
        sa.Column("action_taken", sa.String(255), nullable=False),
        sa.Column("mqtt_topic", sa.Text, nullable=False),
        sa.Column("mqtt_payload", sa.Text, nullable=False),
    )


def downgrade() -> None:
    op.drop_table("rule_events")
    op.drop_table("rules")
    op.drop_table("inverter_readings")
