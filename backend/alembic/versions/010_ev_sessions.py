"""add ev_sessions table

Revision ID: 010
Revises: 009
Create Date: 2026-04-12
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "010"
down_revision: Union[str, None] = "009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "ev_sessions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("kwh_total", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("kwh_solar", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("kwh_grid", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("duration_solar_seconds", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("duration_grid_seconds", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("charging_power_kw", sa.Float(), nullable=False),
        sa.Column("efficiency_km_per_kwh", sa.Float(), nullable=False),
        sa.Column("cost_per_100km_solar_eur", sa.Float(), nullable=False),
        sa.Column("cost_per_100km_grid_eur", sa.Float(), nullable=False),
        sa.Column("cost_per_100km_gas_eur", sa.Float(), nullable=False),
        sa.Column("cost_eur", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("savings_vs_gas_eur", sa.Float(), nullable=False, server_default="0.0"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ev_sessions_started_at", "ev_sessions", ["started_at"])


def downgrade() -> None:
    op.drop_index("ix_ev_sessions_started_at", table_name="ev_sessions")
    op.drop_table("ev_sessions")
