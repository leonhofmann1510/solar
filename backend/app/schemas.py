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
    grid_power_w: float
    house_load_w: float
    pv_yield_today_kwh: float
    feed_in_today_kwh: float
    grid_buy_today_kwh: float
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
