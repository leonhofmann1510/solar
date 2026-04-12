"""Mutable app settings persisted to a JSON file.

These are settings that the user can change at runtime via the API/UI,
as opposed to environment-variable settings that require a restart.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

from app.config import settings

logger = logging.getLogger(__name__)

_SETTINGS_FILE = Path(settings.app_settings_path)

_DEFAULTS: dict = {
    "timezone": "UTC",
    # EV Charging
    "ev_wallbox_device_id": None,
    "ev_charging_capability_key": "",
    "ev_charging_value": "charging",
    "ev_charging_power_kw": 11.0,
    "ev_battery_threshold_pct": 15.0,
    "ev_efficiency_km_per_kwh": 6.0,
    "ev_cost_per_100km_solar_eur": 0.5,
    "ev_cost_per_100km_grid_eur": 4.5,
    "ev_cost_per_100km_gas_eur": 10.0,
}


def _load() -> dict:
    if _SETTINGS_FILE.exists():
        try:
            return {**_DEFAULTS, **json.loads(_SETTINGS_FILE.read_text())}
        except Exception:
            logger.warning("Failed to read app_settings.json, using defaults")
    return dict(_DEFAULTS)


def _save(data: dict) -> None:
    _SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    _SETTINGS_FILE.write_text(json.dumps(data, indent=2))


def get_all() -> dict:
    return _load()


def get(key: str):
    return _load().get(key, _DEFAULTS.get(key))


def update(patch: dict) -> dict:
    data = _load()
    data.update(patch)
    _save(data)
    return data
