"""device tables

Revision ID: 002
Revises: 001
Create Date: 2026-03-13
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "devices",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("protocol", sa.String(16), nullable=False),
        sa.Column("confirmed", sa.Boolean, server_default=sa.text("false"), nullable=False),
        sa.Column("enabled", sa.Boolean, server_default=sa.text("true"), nullable=False),
        sa.Column("room", sa.String(255), nullable=True),
        sa.Column("raw_id", sa.String(255), nullable=False),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("mqtt_base_topic", sa.String(512), nullable=True),
        sa.Column("tuya_local_key", sa.String(255), nullable=True),
        sa.Column("meta", JSONB, nullable=True),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "device_capabilities",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("device_id", sa.Integer, sa.ForeignKey("devices.id", ondelete="CASCADE"), nullable=False),
        sa.Column("key", sa.String(255), nullable=False),
        sa.Column("display_name", sa.String(255), nullable=False),
        sa.Column("capability_type", sa.String(16), nullable=False),
        sa.Column("data_type", sa.String(16), nullable=False),
        sa.Column("min_value", sa.Float, nullable=True),
        sa.Column("max_value", sa.Float, nullable=True),
        sa.Column("unit", sa.String(16), nullable=True),
        sa.Column("mqtt_command_topic", sa.String(512), nullable=True),
        sa.Column("mqtt_state_topic", sa.String(512), nullable=True),
        sa.Column("tuya_dp_id", sa.Integer, nullable=True),
        sa.UniqueConstraint("device_id", "key", name="uq_device_capability_key"),
    )

    op.create_table(
        "device_states",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("device_id", sa.Integer, sa.ForeignKey("devices.id", ondelete="CASCADE"), nullable=False),
        sa.Column("capability_key", sa.String(255), nullable=False),
        sa.Column("value_boolean", sa.Boolean, nullable=True),
        sa.Column("value_numeric", sa.Float, nullable=True),
        sa.Column("value_string", sa.String(1024), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("device_id", "capability_key", name="uq_device_state_key"),
    )


def downgrade() -> None:
    op.drop_table("device_states")
    op.drop_table("device_capabilities")
    op.drop_table("devices")
