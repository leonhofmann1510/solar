from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class InverterReading(Base):
    __tablename__ = "inverter_readings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    inverter_id: Mapped[str] = mapped_column(String(16), index=True)
    pv_power_w: Mapped[float] = mapped_column(Float)
    pv_string1_w: Mapped[float] = mapped_column(Float)
    pv_string2_w: Mapped[float] = mapped_column(Float)
    battery_soc_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    battery_power_w: Mapped[float | None] = mapped_column(Float, nullable=True)
    battery_running_state: Mapped[int | None] = mapped_column(Integer, nullable=True)
    grid_power_w: Mapped[float | None] = mapped_column(Float, nullable=True)
    pv_yield_today_kwh: Mapped[float] = mapped_column(Float)
    feed_in_today_kwh: Mapped[float | None] = mapped_column(Float, nullable=True)
    grid_buy_today_kwh: Mapped[float | None] = mapped_column(Float, nullable=True)
    inverter_temp_c: Mapped[float] = mapped_column(Float)
    grid_frequency_hz: Mapped[float] = mapped_column(Float)


class MeterReading(Base):
    __tablename__ = "meter_readings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    consumption_kwh: Mapped[float] = mapped_column(Float)
    feed_in_kwh: Mapped[float] = mapped_column(Float)


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
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    rule_id: Mapped[int] = mapped_column(Integer, index=True)
    action_taken: Mapped[str] = mapped_column(String(255))
    mqtt_topic: Mapped[str] = mapped_column(Text)
    mqtt_payload: Mapped[str] = mapped_column(Text)


class Device(Base):
    __tablename__ = "devices"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255))
    protocol: Mapped[str] = mapped_column(String(16))
    confirmed: Mapped[bool] = mapped_column(Boolean, server_default="false")
    enabled: Mapped[bool] = mapped_column(Boolean, server_default="true")
    room: Mapped[str | None] = mapped_column(String(255), nullable=True)
    raw_id: Mapped[str] = mapped_column(String(255), index=True)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    mqtt_base_topic: Mapped[str | None] = mapped_column(String(512), nullable=True)
    tuya_local_key: Mapped[str | None] = mapped_column(String(255), nullable=True)
    meta: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    capabilities: Mapped[list["DeviceCapability"]] = relationship(
        back_populates="device", cascade="all, delete-orphan"
    )
    states: Mapped[list["DeviceState"]] = relationship(
        back_populates="device", cascade="all, delete-orphan"
    )


class DeviceCapability(Base):
    __tablename__ = "device_capabilities"
    __table_args__ = (
        UniqueConstraint("device_id", "key", name="uq_device_capability_key"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    device_id: Mapped[int] = mapped_column(ForeignKey("devices.id", ondelete="CASCADE"))
    key: Mapped[str] = mapped_column(String(255))
    display_name: Mapped[str] = mapped_column(String(255))
    capability_type: Mapped[str] = mapped_column(String(16))
    data_type: Mapped[str] = mapped_column(String(16))
    min_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    unit: Mapped[str | None] = mapped_column(String(16), nullable=True)
    mqtt_command_topic: Mapped[str | None] = mapped_column(String(512), nullable=True)
    mqtt_state_topic: Mapped[str | None] = mapped_column(String(512), nullable=True)
    tuya_dp_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

    device: Mapped["Device"] = relationship(back_populates="capabilities")


class DeviceState(Base):
    __tablename__ = "device_states"
    __table_args__ = (
        UniqueConstraint("device_id", "capability_key", name="uq_device_state_key"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    device_id: Mapped[int] = mapped_column(ForeignKey("devices.id", ondelete="CASCADE"), index=True)
    capability_key: Mapped[str] = mapped_column(String(255))
    value_boolean: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    value_numeric: Mapped[float | None] = mapped_column(Float, nullable=True)
    value_string: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    device: Mapped["Device"] = relationship(back_populates="states")
