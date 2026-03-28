"""add battery_running_state to inverter_readings

Revision ID: 006
Revises: 005
Create Date: 2026-03-15
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "006"
down_revision: Union[str, None] = "005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "inverter_readings",
        sa.Column("battery_running_state", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("inverter_readings", "battery_running_state")
