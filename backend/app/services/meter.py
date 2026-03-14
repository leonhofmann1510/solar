"""
Bitshake SmartMeterReader — Tasmota HTTP API polling service.

The device runs Tasmota firmware and exposes sensor data via:
  GET http://<ip>/cm?cmnd=Status+10

Response shape:
{
    "StatusSNS": {
        "Time": "2026-03-14T21:08:38",
        "MT631": {
            "E_in": 678,
            "E_out": 10679,
            "Power": 0,
            "power_L1": 0,
            "power_L2": 0,
            "power_L3": 0,
            "Curr_p1": 0,
            "Curr_p2": 0,
            "Curr_p3": 0,
            "Volt_p1": 0,
            "Volt_p2": 0,
            "Volt_p3": 0,
            "angle_L2_L1": 0,
            "angle_L3_L1": 0,
            "angle_L1": 0,
            "angle_L2": 0,
            "angle_L3": 0,
            "Freq": 0,
            "server_id": ""
        }
    }
}

We split the signed Power field into two non-negative metrics:
  consumption_w = max(0,  Power)
  feed_in_w     = max(0, -Power)
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone

import httpx

logger = logging.getLogger(__name__)

_TASMOTA_STATUS_URL = "http://{ip}/cm?cmnd=Status+10"


@dataclass
class MeterData:
    timestamp: datetime
    consumption_kwh: float  # E_in  — total kWh consumed from grid (ever-increasing)
    feed_in_kwh: float      # E_out — total kWh fed into grid   (ever-increasing)


class BitshakeSmartMeter:
    def __init__(self, ip: str, timeout: float = 5.0) -> None:
        self.ip = ip
        self._url = _TASMOTA_STATUS_URL.format(ip=ip)
        self._timeout = timeout

    async def fetch(self) -> MeterData | None:
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.get(self._url)
                resp.raise_for_status()
                data = resp.json()
        except httpx.HTTPError as exc:
            logger.warning("Smart meter HTTP error (%s): %s", self.ip, exc)
            return None
        except Exception as exc:
            logger.warning("Smart meter fetch error (%s): %s", self.ip, exc)
            return None

        return self._parse(data)

    @staticmethod
    def _parse(data: dict) -> MeterData | None:
        try:
            sensor = data["StatusSNS"]
            meter_key = next(k for k in sensor if k != "Time")
            mt = sensor[meter_key]
            consumption_kwh = float(mt["E_in"])
            feed_in_kwh = float(mt["E_out"])
        except (KeyError, StopIteration, TypeError, ValueError) as exc:
            logger.warning("Smart meter parse error: %s — raw: %s", exc, data)
            return None

        return MeterData(
            timestamp=datetime.now(tz=timezone.utc),
            consumption_kwh=consumption_kwh,
            feed_in_kwh=feed_in_kwh,
        )
