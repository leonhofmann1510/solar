from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.models import EVSession, InverterDailyStat, MeterReading
from app.services import app_settings as app_svc

router = APIRouter(prefix="/api/data", tags=["data"])


# ── Schemas ────────────────────────────────────────────────────────────────────

class InverterDailyStatOut(BaseModel):
    id: int
    timestamp: datetime
    inverter_id: str
    date: date
    hour: int
    pv_yield_today_kwh: float
    feed_in_today_kwh: float | None
    grid_buy_today_kwh: float | None

    model_config = {"from_attributes": True}


class InverterDailyStatUpdate(BaseModel):
    pv_yield_today_kwh: float | None = None
    feed_in_today_kwh: float | None = None
    grid_buy_today_kwh: float | None = None


class DataMeterReadingOut(BaseModel):
    id: int
    timestamp: datetime
    consumption_kwh: float
    feed_in_kwh: float

    model_config = {"from_attributes": True}


class DataMeterReadingUpdate(BaseModel):
    consumption_kwh: float | None = None
    feed_in_kwh: float | None = None


class DataEVSessionOut(BaseModel):
    id: int
    started_at: datetime
    ended_at: datetime | None
    kwh_total: float
    kwh_solar: float
    kwh_grid: float
    charging_power_kw: float
    cost_eur: float
    savings_vs_gas_eur: float

    model_config = {"from_attributes": True}


class DataEVSessionUpdate(BaseModel):
    started_at: datetime | None = None
    ended_at: datetime | None = None
    kwh_total: float | None = None
    kwh_solar: float | None = None
    kwh_grid: float | None = None
    charging_power_kw: float | None = None


class InverterDailyStatCreate(BaseModel):
    timestamp: datetime
    inverter_id: str
    pv_yield_today_kwh: float
    feed_in_today_kwh: float | None = None
    grid_buy_today_kwh: float | None = None


class DataMeterReadingCreate(BaseModel):
    timestamp: datetime
    consumption_kwh: float
    feed_in_kwh: float


class DataEVSessionCreate(BaseModel):
    started_at: datetime
    ended_at: datetime
    kwh_total: float
    kwh_solar: float
    kwh_grid: float
    charging_power_kw: float


class DataCounts(BaseModel):
    inverter_stats: int
    meter_readings: int
    ev_sessions: int


# ── Inverter Stats ─────────────────────────────────────────────────────────────

@router.get("/inverter-stats", response_model=list[InverterDailyStatOut])
async def list_inverter_stats(
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    inverter_id: str | None = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_session),
):
    q = select(InverterDailyStat).order_by(InverterDailyStat.timestamp.desc())
    if date_from:
        q = q.where(InverterDailyStat.date >= date_from)
    if date_to:
        q = q.where(InverterDailyStat.date <= date_to)
    if inverter_id:
        q = q.where(InverterDailyStat.inverter_id == inverter_id)
    q = q.limit(limit).offset(offset)
    result = await session.execute(q)
    return result.scalars().all()


@router.patch("/inverter-stats/{id}", response_model=InverterDailyStatOut)
async def update_inverter_stat(
    id: int,
    body: InverterDailyStatUpdate,
    session: AsyncSession = Depends(get_session),
):
    stat = await session.get(InverterDailyStat, id)
    if not stat:
        raise HTTPException(404, "Record not found")
    if body.pv_yield_today_kwh is not None:
        stat.pv_yield_today_kwh = body.pv_yield_today_kwh
    if body.feed_in_today_kwh is not None:
        stat.feed_in_today_kwh = body.feed_in_today_kwh
    if body.grid_buy_today_kwh is not None:
        stat.grid_buy_today_kwh = body.grid_buy_today_kwh
    await session.commit()
    await session.refresh(stat)
    return stat


@router.delete("/inverter-stats/{id}", status_code=204)
async def delete_inverter_stat(id: int, session: AsyncSession = Depends(get_session)):
    stat = await session.get(InverterDailyStat, id)
    if not stat:
        raise HTTPException(404, "Record not found")
    await session.delete(stat)
    await session.commit()


@router.post("/inverter-stats", response_model=InverterDailyStatOut, status_code=201)
async def create_inverter_stat(
    body: InverterDailyStatCreate,
    session: AsyncSession = Depends(get_session),
):
    stat = InverterDailyStat(
        timestamp=body.timestamp,
        inverter_id=body.inverter_id,
        date=body.timestamp.date(),
        hour=body.timestamp.hour,
        pv_yield_today_kwh=body.pv_yield_today_kwh,
        feed_in_today_kwh=body.feed_in_today_kwh,
        grid_buy_today_kwh=body.grid_buy_today_kwh,
    )
    session.add(stat)
    await session.commit()
    await session.refresh(stat)
    return stat


# ── Meter Readings ─────────────────────────────────────────────────────────────

@router.get("/meter-readings", response_model=list[DataMeterReadingOut])
async def list_meter_readings(
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_session),
):
    q = select(MeterReading).order_by(MeterReading.timestamp.desc())
    if date_from:
        q = q.where(func.date(MeterReading.timestamp) >= date_from)
    if date_to:
        q = q.where(func.date(MeterReading.timestamp) <= date_to)
    q = q.limit(limit).offset(offset)
    result = await session.execute(q)
    return result.scalars().all()


@router.patch("/meter-readings/{id}", response_model=DataMeterReadingOut)
async def update_meter_reading(
    id: int,
    body: DataMeterReadingUpdate,
    session: AsyncSession = Depends(get_session),
):
    reading = await session.get(MeterReading, id)
    if not reading:
        raise HTTPException(404, "Record not found")
    if body.consumption_kwh is not None:
        reading.consumption_kwh = body.consumption_kwh
    if body.feed_in_kwh is not None:
        reading.feed_in_kwh = body.feed_in_kwh
    await session.commit()
    await session.refresh(reading)
    return reading


@router.delete("/meter-readings/{id}", status_code=204)
async def delete_meter_reading(id: int, session: AsyncSession = Depends(get_session)):
    reading = await session.get(MeterReading, id)
    if not reading:
        raise HTTPException(404, "Record not found")
    await session.delete(reading)
    await session.commit()


@router.post("/meter-readings", response_model=DataMeterReadingOut, status_code=201)
async def create_meter_reading(
    body: DataMeterReadingCreate,
    session: AsyncSession = Depends(get_session),
):
    reading = MeterReading(
        timestamp=body.timestamp,
        consumption_kwh=body.consumption_kwh,
        feed_in_kwh=body.feed_in_kwh,
    )
    session.add(reading)
    await session.commit()
    await session.refresh(reading)
    return reading


# ── EV Sessions ────────────────────────────────────────────────────────────────

@router.get("/ev-sessions", response_model=list[DataEVSessionOut])
async def list_ev_sessions(
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_session),
):
    q = (
        select(EVSession)
        .where(EVSession.ended_at.is_not(None))
        .order_by(EVSession.started_at.desc())
    )
    if date_from:
        q = q.where(func.date(EVSession.started_at) >= date_from)
    if date_to:
        q = q.where(func.date(EVSession.started_at) <= date_to)
    q = q.limit(limit).offset(offset)
    result = await session.execute(q)
    return result.scalars().all()


@router.patch("/ev-sessions/{id}", response_model=DataEVSessionOut)
async def update_ev_session(
    id: int,
    body: DataEVSessionUpdate,
    session: AsyncSession = Depends(get_session),
):
    ev = await session.get(EVSession, id)
    if not ev:
        raise HTTPException(404, "Record not found")
    if body.started_at is not None:
        ev.started_at = body.started_at
    if body.ended_at is not None:
        ev.ended_at = body.ended_at
    # Recalculate stored durations when timestamps change
    if (body.started_at is not None or body.ended_at is not None) and ev.ended_at is not None:
        new_total = max(0, int((ev.ended_at - ev.started_at).total_seconds()))
        old_total = ev.duration_solar_seconds + ev.duration_grid_seconds
        if old_total > 0:
            solar_ratio = ev.duration_solar_seconds / old_total
            ev.duration_solar_seconds = int(new_total * solar_ratio)
            ev.duration_grid_seconds = new_total - ev.duration_solar_seconds
        else:
            ev.duration_solar_seconds = new_total
            ev.duration_grid_seconds = 0
    if body.kwh_total is not None:
        ev.kwh_total = body.kwh_total
    if body.kwh_solar is not None:
        ev.kwh_solar = body.kwh_solar
    if body.kwh_grid is not None:
        ev.kwh_grid = body.kwh_grid
    if body.charging_power_kw is not None:
        ev.charging_power_kw = body.charging_power_kw
    # Always recalculate cost and savings from kWh + stored price snapshots
    eff = ev.efficiency_km_per_kwh
    km_solar = ev.kwh_solar * eff
    km_grid = ev.kwh_grid * eff
    km_total = ev.kwh_total * eff
    ev.cost_eur = round((km_solar / 100 * ev.cost_per_100km_solar_eur) + (km_grid / 100 * ev.cost_per_100km_grid_eur), 2)
    ev.savings_vs_gas_eur = round((km_total / 100 * ev.cost_per_100km_gas_eur) - ev.cost_eur, 2)
    await session.commit()
    await session.refresh(ev)
    return ev


@router.delete("/ev-sessions/{id}", status_code=204)
async def delete_ev_session(id: int, session: AsyncSession = Depends(get_session)):
    ev = await session.get(EVSession, id)
    if not ev:
        raise HTTPException(404, "Record not found")
    await session.delete(ev)
    await session.commit()


@router.post("/ev-sessions", response_model=DataEVSessionOut, status_code=201)
async def create_ev_session(
    body: DataEVSessionCreate,
    session: AsyncSession = Depends(get_session),
):
    cfg = app_svc.get_all()
    efficiency = float(cfg.get("ev_efficiency_km_per_kwh", 6.0))
    cost_solar = float(cfg.get("ev_cost_per_100km_solar_eur", 0.5))
    cost_grid = float(cfg.get("ev_cost_per_100km_grid_eur", 4.5))
    cost_gas = float(cfg.get("ev_cost_per_100km_gas_eur", 10.0))

    total_seconds = max(0, int((body.ended_at - body.started_at).total_seconds()))
    km_solar = body.kwh_solar * efficiency
    km_grid = body.kwh_grid * efficiency
    km_total = body.kwh_total * efficiency
    cost_eur = round((km_solar / 100 * cost_solar) + (km_grid / 100 * cost_grid), 2)
    savings_vs_gas_eur = round((km_total / 100 * cost_gas) - cost_eur, 2)

    ev = EVSession(
        started_at=body.started_at,
        ended_at=body.ended_at,
        kwh_total=body.kwh_total,
        kwh_solar=body.kwh_solar,
        kwh_grid=body.kwh_grid,
        charging_power_kw=body.charging_power_kw,
        duration_solar_seconds=total_seconds,
        duration_grid_seconds=0,
        efficiency_km_per_kwh=efficiency,
        cost_per_100km_solar_eur=cost_solar,
        cost_per_100km_grid_eur=cost_grid,
        cost_per_100km_gas_eur=cost_gas,
        cost_eur=cost_eur,
        savings_vs_gas_eur=savings_vs_gas_eur,
    )
    session.add(ev)
    await session.commit()
    await session.refresh(ev)
    return ev


# ── Counts ─────────────────────────────────────────────────────────────────────

@router.get("/counts", response_model=DataCounts)
async def get_counts(
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    session: AsyncSession = Depends(get_session),
):
    q_inv = select(func.count()).select_from(InverterDailyStat)
    if date_from:
        q_inv = q_inv.where(InverterDailyStat.date >= date_from)
    if date_to:
        q_inv = q_inv.where(InverterDailyStat.date <= date_to)

    q_meter = select(func.count()).select_from(MeterReading)
    if date_from:
        q_meter = q_meter.where(func.date(MeterReading.timestamp) >= date_from)
    if date_to:
        q_meter = q_meter.where(func.date(MeterReading.timestamp) <= date_to)

    q_ev = select(func.count()).select_from(EVSession).where(EVSession.ended_at.is_not(None))
    if date_from:
        q_ev = q_ev.where(func.date(EVSession.started_at) >= date_from)
    if date_to:
        q_ev = q_ev.where(func.date(EVSession.started_at) <= date_to)

    inv_count = await session.scalar(q_inv)
    meter_count = await session.scalar(q_meter)
    ev_count = await session.scalar(q_ev)

    return DataCounts(
        inverter_stats=inv_count or 0,
        meter_readings=meter_count or 0,
        ev_sessions=ev_count or 0,
    )
