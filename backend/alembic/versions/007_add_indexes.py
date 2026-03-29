"""add indexes on frequently queried columns

Revision ID: 007
Revises: 006
Create Date: 2026-03-29
"""
from typing import Sequence, Union

from alembic import op

revision: str = "007"
down_revision: Union[str, None] = "006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_INDEXES = [
    ("ix_inverter_readings_inverter_id", "inverter_readings", ["inverter_id"]),
    ("ix_rule_events_timestamp", "rule_events", ["timestamp"]),
    ("ix_rule_events_rule_id", "rule_events", ["rule_id"]),
    ("ix_devices_raw_id", "devices", ["raw_id"]),
    ("ix_device_states_device_id", "device_states", ["device_id"]),
]


def upgrade() -> None:
    for name, table, columns in _INDEXES:
        op.create_index(name, table, columns)


def downgrade() -> None:
    for name, _table, _columns in _INDEXES:
        op.drop_index(name)
