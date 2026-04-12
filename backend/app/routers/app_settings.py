from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from app.services import app_settings as svc

router = APIRouter(prefix="/api/settings", tags=["settings"])


class AppSettingsOut(BaseModel):
    timezone: str
    ev_wallbox_device_id: int | None = None
    ev_charging_capability_key: str = ""
    ev_charging_value: str = "charging"
    ev_charging_power_kw: float = 11.0
    ev_battery_threshold_pct: float = 15.0
    ev_efficiency_km_per_kwh: float = 6.0
    ev_cost_per_100km_solar_eur: float = 0.5
    ev_cost_per_100km_grid_eur: float = 4.5
    ev_cost_per_100km_gas_eur: float = 10.0


class AppSettingsPatch(BaseModel):
    timezone: str | None = None
    ev_wallbox_device_id: int | None = None
    ev_charging_capability_key: str | None = None
    ev_charging_value: str | None = None
    ev_charging_power_kw: float | None = None
    ev_battery_threshold_pct: float | None = None
    ev_efficiency_km_per_kwh: float | None = None
    ev_cost_per_100km_solar_eur: float | None = None
    ev_cost_per_100km_grid_eur: float | None = None
    ev_cost_per_100km_gas_eur: float | None = None


@router.get("", response_model=AppSettingsOut)
async def get_settings() -> AppSettingsOut:
    return AppSettingsOut(**svc.get_all())


@router.patch("", response_model=AppSettingsOut)
async def patch_settings(body: AppSettingsPatch) -> AppSettingsOut:
    patch = body.model_dump(exclude_unset=True)
    return AppSettingsOut(**svc.update(patch))
