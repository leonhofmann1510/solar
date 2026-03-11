from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class InverterReading(Base):
    __tablename__ = "inverter_readings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    inverter_id: Mapped[str] = mapped_column(String(16))
    pv_power_w: Mapped[float] = mapped_column(Float)
    pv_string1_w: Mapped[float] = mapped_column(Float)
    pv_string2_w: Mapped[float] = mapped_column(Float)
    battery_soc_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    battery_power_w: Mapped[float | None] = mapped_column(Float, nullable=True)
    grid_power_w: Mapped[float] = mapped_column(Float)
    house_load_w: Mapped[float] = mapped_column(Float)
    pv_yield_today_kwh: Mapped[float] = mapped_column(Float)
    feed_in_today_kwh: Mapped[float] = mapped_column(Float)
    grid_buy_today_kwh: Mapped[float] = mapped_column(Float)
    inverter_temp_c: Mapped[float] = mapped_column(Float)
    grid_frequency_hz: Mapped[float] = mapped_column(Float)


class Rule(Base):
    __tablename__ = "rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), unique=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    condition_logic: Mapped[str] = mapped_column(String(3), default="AND")
    conditions: Mapped[dict] = mapped_column(JSONB)
    actions: Mapped[dict] = mapped_column(JSONB)
    on_clear_action: Mapped[str] = mapped_column(String(16), default="none")
    on_clear_payload: Mapped[str | None] = mapped_column(Text, nullable=True)
    cooldown_seconds: Mapped[int] = mapped_column(Integer, default=0)
    last_fired_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    state: Mapped[str] = mapped_column(String(16), default="idle")


class RuleEvent(Base):
    __tablename__ = "rule_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    rule_id: Mapped[int] = mapped_column(Integer)
    action_taken: Mapped[str] = mapped_column(String(255))
    mqtt_topic: Mapped[str] = mapped_column(Text)
    mqtt_payload: Mapped[str] = mapped_column(Text)
