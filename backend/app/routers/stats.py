from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import text

from app.database import async_session
from app.schemas import DailyStatOut, TodayStatOut
from app.state import AppState, get_app_state

router = APIRouter(prefix="/api/stats", tags=["stats"])


@router.get("/today", response_model=TodayStatOut)
async def today_stats(app_state: AppState = Depends(get_app_state)) -> TodayStatOut:
    """Today's cumulative stats from the latest in-memory inverter readings."""
    readings = list(app_state.latest_readings.values())
    yield_kwh = sum(r.pv_yield_today_kwh for r in readings)
    feed_in_kwh = sum((r.feed_in_today_kwh or 0.0) for r in readings)
    grid_buy_kwh = sum((r.grid_buy_today_kwh or 0.0) for r in readings)
    self_consumption_kwh = max(0.0, yield_kwh - feed_in_kwh)
    return TodayStatOut(
        yield_kwh=round(yield_kwh, 3),
        feed_in_kwh=round(feed_in_kwh, 3),
        grid_buy_kwh=round(grid_buy_kwh, 3),
        self_consumption_kwh=round(self_consumption_kwh, 3),
    )


@router.get("/daily", response_model=list[DailyStatOut])
async def daily_stats(days: int = Query(30, ge=1, le=365)) -> list[DailyStatOut]:
    """Historical daily stats from inverter_daily_stats.

    Per day: yield = SUM of per-inverter daily MAX (in case multiple inverters).
    feed_in / grid_buy = MAX across inverters for that day (nullable-safe).
    """
    since: date = (datetime.now(tz=timezone.utc) - timedelta(days=days)).date()

    query = text("""
        SELECT
            date,
            SUM(max_yield)      AS yield_kwh,
            MAX(max_feed_in)    AS feed_in_kwh,
            MAX(max_grid_buy)   AS grid_buy_kwh
        FROM (
            SELECT
                date,
                inverter_id,
                MAX(pv_yield_today_kwh)  AS max_yield,
                MAX(feed_in_today_kwh)   AS max_feed_in,
                MAX(grid_buy_today_kwh)  AS max_grid_buy
            FROM inverter_daily_stats
            WHERE date >= :since
            GROUP BY date, inverter_id
        ) sub
        GROUP BY date
        ORDER BY date
    """)

    async with async_session() as session:
        result = await session.execute(query, {"since": since})
        rows = result.fetchall()

    out: list[DailyStatOut] = []
    for row in rows:
        y = float(row.yield_kwh or 0.0)
        fi = float(row.feed_in_kwh or 0.0)
        gb = float(row.grid_buy_kwh or 0.0)
        out.append(DailyStatOut(
            date=row.date,
            yield_kwh=round(y, 3),
            feed_in_kwh=round(fi, 3),
            grid_buy_kwh=round(gb, 3),
            self_consumption_kwh=round(max(0.0, y - fi), 3),
        ))
    return out
