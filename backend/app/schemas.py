from datetime import datetime

from pydantic import BaseModel


# --- Readings ---


class ReadingOut(BaseModel):
    id: int
    timestamp: datetime
    inverter_id: str
    pv_power_w: float
    pv_string1_w: float
    pv_string2_w: float
    battery_soc_pct: float | None
    battery_power_w: float | None
    grid_power_w: float | None
    house_load_w: float | None
    pv_yield_today_kwh: float
    feed_in_today_kwh: float | None
    grid_buy_today_kwh: float | None
    inverter_temp_c: float
    grid_frequency_hz: float

    model_config = {"from_attributes": True}


class InverterStatus(BaseModel):
    id: str
    last_seen: datetime | None
    connected: bool


class HealthResponse(BaseModel):
    status: str
    inverters: list[InverterStatus]


# --- Rules ---


class ConditionSchema(BaseModel):
    field: str
    operator: str  # gt, lt, gte, lte, eq, neq
    value: float


class ActionSchema(BaseModel):
    mqtt_topic: str
    mqtt_payload: str


class RuleCreate(BaseModel):
    name: str
    enabled: bool = True
    condition_logic: str = "AND"
    conditions: list[ConditionSchema]
    actions: list[ActionSchema]
    on_clear_action: str = "none"
    on_clear_payload: str | None = None
    cooldown_seconds: int = 0


class RuleUpdate(RuleCreate):
    pass


class RuleOut(RuleCreate):
    id: int
    last_fired_at: datetime | None
    state: str

    model_config = {"from_attributes": True}


class RuleEventOut(BaseModel):
    id: int
    timestamp: datetime
    rule_id: int
    action_taken: str
    mqtt_topic: str
    mqtt_payload: str

    model_config = {"from_attributes": True}


# --- Devices ---


class DeviceCapabilitySchema(BaseModel):
    key: str
    display_name: str
    capability_type: str
    data_type: str
    min_value: float | None = None
    max_value: float | None = None
    unit: str | None = None
    mqtt_command_topic: str | None = None
    mqtt_state_topic: str | None = None
    tuya_dp_id: int | None = None


class DeviceCapabilityOut(DeviceCapabilitySchema):
    id: int
    device_id: int

    model_config = {"from_attributes": True}


class DeviceStateOut(BaseModel):
    capability_key: str
    value_boolean: bool | None
    value_numeric: float | None
    value_string: str | None
    updated_at: datetime

    model_config = {"from_attributes": True}


class DeviceOut(BaseModel):
    id: int
    name: str
    protocol: str
    confirmed: bool
    enabled: bool
    room: str | None
    raw_id: str
    ip_address: str | None
    mqtt_base_topic: str | None
    first_seen_at: datetime
    last_seen_at: datetime
    capabilities: list[DeviceCapabilityOut] = []
    states: list[DeviceStateOut] = []

    model_config = {"from_attributes": True}


class DeviceConfirm(BaseModel):
    name: str
    room: str | None = None


class DeviceUpdate(BaseModel):
    name: str | None = None
    room: str | None = None
    enabled: bool | None = None


class DeviceActionRequest(BaseModel):
    capability_key: str
    value: bool | int | float | str


class TuyaLoginStart(BaseModel):
    user_code: str
