from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Literal

from fastapi import APIRouter, Query
from pydantic import BaseModel
from sqlalchemy import text

from app.config import settings
from app.database import async_session
from app.models import MeterReading
from app.services import app_settings as app_svc
from sqlalchemy import select

router = APIRouter(prefix="/api/meter", tags=["meter"])


# ── Pydantic schemas ──────────────────────────────────────────────────────────

class MeterStatus(BaseModel):
    enabled: bool
    ip: str


class MeterReadingOut(BaseModel):
    id: int
    timestamp: datetime
    consumption_kwh: float
    feed_in_kwh: float

    model_config = {"from_attributes": True}


class MeterPoint(BaseModel):
    """One aggregated bucket for charts — delta kWh consumed/fed-in that period."""
    label: str
    consumption_kwh: float
    feed_in_kwh: float


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/status", response_model=MeterStatus)
async def get_status() -> MeterStatus:
    return MeterStatus(enabled=settings.smart_meter_enabled, ip=settings.smart_meter_ip)


@router.get("/latest", response_model=MeterReadingOut | None)
async def get_latest() -> MeterReading | None:
    async with async_session() as session:
        result = await session.execute(
            select(MeterReading).order_by(MeterReading.timestamp.desc()).limit(1)
        )
        return result.scalar_one_or_none()


@router.get("/readings", response_model=list[MeterPoint])
async def get_readings(
    view: Literal["day", "week", "month", "year"] = Query("day"),
) -> list[MeterPoint]:
    """Return per-bucket delta kWh (max − min within each bucket).

    Since E_in and E_out are ever-increasing counters, the delta per bucket
    is the actual energy consumed/fed-in during that period.

    Granularity:
      day   → per hour  (last 24 h)
      week  → per day   (last 7 days)
      month → per day   (last 30 days)
      year  → per month (last 12 months)
    """
    now = datetime.now(tz=timezone.utc)

    match view:
        case "day":
            since = now - timedelta(hours=24)
            trunc = "hour"
            fmt = "HH24:00"
        case "week":
            since = now - timedelta(days=7)
            trunc = "day"
            fmt = "Dy DD.MM"
        case "month":
            since = now - timedelta(days=30)
            trunc = "day"
            fmt = "DD.MM"
        case "year":
            since = now - timedelta(days=365)
            trunc = "month"
            fmt = "Mon YYYY"
        case _:
            since = now - timedelta(hours=24)
            trunc = "hour"
            fmt = "HH24:00"

    tz = app_svc.get("timezone") or "UTC"

    # Delta per bucket: how much kWh changed within the bucket
    query = text("""
        SELECT
            to_char(date_trunc(:trunc, timestamp AT TIME ZONE :tz), :fmt) AS label,
            date_trunc(:trunc, timestamp AT TIME ZONE :tz)                AS bucket,
            MAX(consumption_kwh) - MIN(consumption_kwh)                   AS consumption_kwh,
            MAX(feed_in_kwh)     - MIN(feed_in_kwh)                       AS feed_in_kwh
        FROM meter_readings
        WHERE timestamp >= :since
        GROUP BY bucket
        ORDER BY bucket
    """)

    async with async_session() as session:
        result = await session.execute(query, {"trunc": trunc, "fmt": fmt, "since": since, "tz": tz})
        rows = result.fetchall()

    return [
        MeterPoint(
            label=row.label,
            consumption_kwh=round(max(0.0, row.consumption_kwh or 0.0), 3),
            feed_in_kwh=round(max(0.0, row.feed_in_kwh or 0.0), 3),
        )
        for row in rows
    ]
