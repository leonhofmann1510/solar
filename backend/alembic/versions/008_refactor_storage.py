"""refactor storage: drop inverter_readings, downsample meter_readings, create inverter_daily_stats

Revision ID: 008
Revises: 007
Create Date: 2026-04-11
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "008"
down_revision: Union[str, None] = "007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Downsample meter_readings to one row per hour (keep MAX of cumulative counters)
    op.execute("""
        CREATE TEMP TABLE _meter_hourly AS
        SELECT
            date_trunc('hour', timestamp) AS ts,
            MAX(consumption_kwh)          AS consumption_kwh,
            MAX(feed_in_kwh)              AS feed_in_kwh
        FROM meter_readings
        GROUP BY date_trunc('hour', timestamp)
    """)
    op.execute("TRUNCATE meter_readings")
    op.execute("""
        INSERT INTO meter_readings (timestamp, consumption_kwh, feed_in_kwh)
        SELECT ts, consumption_kwh, feed_in_kwh FROM _meter_hourly
    """)
    op.execute("DROP TABLE _meter_hourly")

    # 2. Drop inverter_readings (no longer written to)
    op.drop_table("inverter_readings")

    # 3. Create inverter_daily_stats table
    op.create_table(
        "inverter_daily_stats",
        sa.Column("id",                   sa.Integer(),    primary_key=True, autoincrement=True),
        sa.Column("timestamp",            sa.DateTime(timezone=True), nullable=False),
        sa.Column("inverter_id",          sa.String(16),   nullable=False),
        sa.Column("date",                 sa.Date(),       nullable=False),
        sa.Column("hour",                 sa.SmallInteger(), nullable=False),
        sa.Column("pv_yield_today_kwh",   sa.Float(),      nullable=False),
        sa.Column("feed_in_today_kwh",    sa.Float(),      nullable=True),
        sa.Column("grid_buy_today_kwh",   sa.Float(),      nullable=True),
    )
    op.create_index("ix_inverter_daily_stats_date",     "inverter_daily_stats", ["date"])
    op.create_index("ix_inverter_daily_stats_inverter", "inverter_daily_stats", ["inverter_id"])


def downgrade() -> None:
    op.drop_index("ix_inverter_daily_stats_inverter", table_name="inverter_daily_stats")
    op.drop_index("ix_inverter_daily_stats_date",     table_name="inverter_daily_stats")
    op.drop_table("inverter_daily_stats")

    op.create_table(
        "inverter_readings",
        sa.Column("id",                   sa.Integer(),    primary_key=True, autoincrement=True),
        sa.Column("timestamp",            sa.DateTime(timezone=True), server_default=sa.func.now(), index=True),
        sa.Column("inverter_id",          sa.String(16),   index=True),
        sa.Column("pv_power_w",           sa.Float(),      nullable=False),
        sa.Column("pv_string1_w",         sa.Float(),      nullable=False),
        sa.Column("pv_string2_w",         sa.Float(),      nullable=False),
        sa.Column("battery_soc_pct",      sa.Float(),      nullable=True),
        sa.Column("battery_power_w",      sa.Float(),      nullable=True),
        sa.Column("battery_running_state",sa.Integer(),    nullable=True),
        sa.Column("grid_power_w",         sa.Float(),      nullable=True),
        sa.Column("pv_yield_today_kwh",   sa.Float(),      nullable=False),
        sa.Column("feed_in_today_kwh",    sa.Float(),      nullable=True),
        sa.Column("grid_buy_today_kwh",   sa.Float(),      nullable=True),
        sa.Column("inverter_temp_c",      sa.Float(),      nullable=False),
        sa.Column("grid_frequency_hz",    sa.Float(),      nullable=False),
    )
