from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Query
from pydantic import BaseModel
from sqlalchemy import select, func

from app.config import settings
from app.database import async_session
from app.models import DeviceState, EVSession
from app.services import app_settings as app_svc

router = APIRouter(prefix="/api/ev", tags=["ev"])


# ── Pydantic schemas ──────────────────────────────────────────────────────────

class EVSessionOut(BaseModel):
    id: int
    started_at: datetime
    ended_at: datetime | None
    kwh_total: float
    kwh_solar: float
    kwh_grid: float
    duration_solar_seconds: int
    duration_grid_seconds: int
    charging_power_kw: float
    efficiency_km_per_kwh: float
    cost_per_100km_solar_eur: float
    cost_per_100km_grid_eur: float
    cost_per_100km_gas_eur: float
    cost_eur: float
    savings_vs_gas_eur: float

    model_config = {"from_attributes": True}


class EVStatus(BaseModel):
    enabled: bool
    configured: bool
    active_session: EVSessionOut | None


class EVSummary(BaseModel):
    this_week_kwh: float
    last_week_kwh: float
    this_week_km: float
    last_week_km: float
    total_savings_eur: float
    total_sessions: int


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/status", response_model=EVStatus)
async def get_ev_status() -> EVStatus:
    ev_settings = app_svc.get_all()
    configured = bool(
        ev_settings.get("ev_wallbox_device_id") is not None
        and ev_settings.get("ev_charging_capability_key")
    )

    # Check for an open session (ended_at is NULL)
    active: EVSession | None = None
    if settings.ev_charging_enabled:
        async with async_session() as session:
            result = await session.execute(
                select(EVSession)
                .where(EVSession.ended_at.is_(None))
                .order_by(EVSession.started_at.desc())
                .limit(1)
            )
            active = result.scalar_one_or_none()

    return EVStatus(
        enabled=settings.ev_charging_enabled,
        configured=configured,
        active_session=EVSessionOut.model_validate(active) if active else None,
    )


@router.get("/sessions", response_model=list[EVSessionOut])
async def get_ev_sessions(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> list[EVSession]:
    async with async_session() as session:
        result = await session.execute(
            select(EVSession)
            .where(EVSession.ended_at.is_not(None))
            .order_by(EVSession.started_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())


@router.get("/debug")
async def get_ev_debug():
    """Returns the live EV charging detection state — useful for diagnosing config issues."""
    ev_settings = app_svc.get_all()
    device_id = ev_settings.get("ev_wallbox_device_id")
    cap_key = ev_settings.get("ev_charging_capability_key", "")
    charging_value = ev_settings.get("ev_charging_value", "charging")

    current_value = None
    last_updated = None

    if device_id and cap_key:
        async with async_session() as db:
            result = await db.execute(
                select(DeviceState).where(
                    DeviceState.device_id == device_id,
                    DeviceState.capability_key == cap_key,
                )
            )
            ds = result.scalar_one_or_none()
            if ds:
                current_value = ds.value_string
                last_updated = ds.updated_at

    return {
        "enabled": settings.ev_charging_enabled,
        "configured": bool(device_id and cap_key),
        "wallbox_device_id": device_id,
        "capability_key": cap_key,
        "charging_value": charging_value,
        "current_value": current_value,
        "is_match": current_value == charging_value if current_value is not None else False,
        "last_updated": last_updated,
    }


@router.get("/summary", response_model=EVSummary)
async def get_ev_summary() -> EVSummary:
    now = datetime.now(tz=timezone.utc)
    week_start = now - timedelta(days=now.weekday(), hours=now.hour, minutes=now.minute, seconds=now.second)
    last_week_start = week_start - timedelta(weeks=1)

    ev_settings = app_svc.get_all()
    efficiency = float(ev_settings.get("ev_efficiency_km_per_kwh", 6.0))

    async with async_session() as db:
        # This week
        tw = await db.execute(
            select(func.coalesce(func.sum(EVSession.kwh_total), 0.0))
            .where(EVSession.started_at >= week_start)
            .where(EVSession.ended_at.is_not(None))
        )
        this_week_kwh = float(tw.scalar())

        # Last week
        lw = await db.execute(
            select(func.coalesce(func.sum(EVSession.kwh_total), 0.0))
            .where(EVSession.started_at >= last_week_start)
            .where(EVSession.started_at < week_start)
            .where(EVSession.ended_at.is_not(None))
        )
        last_week_kwh = float(lw.scalar())

        # Total savings
        ts = await db.execute(
            select(func.coalesce(func.sum(EVSession.savings_vs_gas_eur), 0.0))
            .where(EVSession.ended_at.is_not(None))
        )
        total_savings = float(ts.scalar())

        # Total sessions
        tc = await db.execute(
            select(func.count(EVSession.id)).where(EVSession.ended_at.is_not(None))
        )
        total_sessions = int(tc.scalar())

    return EVSummary(
        this_week_kwh=round(this_week_kwh, 2),
        last_week_kwh=round(last_week_kwh, 2),
        this_week_km=round(this_week_kwh * efficiency, 1),
        last_week_km=round(last_week_kwh * efficiency, 1),
        total_savings_eur=round(total_savings, 2),
        total_sessions=total_sessions,
    )
