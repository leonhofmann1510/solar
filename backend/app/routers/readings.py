from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.models import InverterReading
from app.schemas import HealthResponse, InverterStatus, ReadingOut

router = APIRouter(prefix="/api", tags=["readings"])


@router.get("/health", response_model=HealthResponse)
async def health(session: AsyncSession = Depends(get_session)):
    """Health check with last-seen status per inverter."""
    inverters: list[InverterStatus] = []
    for inv_id in ("inv1", "inv2"):
        result = await session.execute(
            select(InverterReading.timestamp)
            .where(InverterReading.inverter_id == inv_id)
            .order_by(InverterReading.timestamp.desc())
            .limit(1)
        )
        last_seen = result.scalar_one_or_none()
        inverters.append(InverterStatus(
            id=inv_id,
            last_seen=last_seen,
            connected=last_seen is not None,
        ))
    return HealthResponse(status="ok", inverters=inverters)


@router.get("/readings/latest", response_model=list[ReadingOut])
async def latest_readings(session: AsyncSession = Depends(get_session)):
    """Most recent reading for each inverter."""
    readings: list[InverterReading] = []
    for inv_id in ("inv1", "inv2"):
        result = await session.execute(
            select(InverterReading)
            .where(InverterReading.inverter_id == inv_id)
            .order_by(InverterReading.timestamp.desc())
            .limit(1)
        )
        row = result.scalar_one_or_none()
        if row:
            readings.append(row)
    return readings


@router.get("/readings", response_model=list[ReadingOut])
async def list_readings(
    session: AsyncSession = Depends(get_session),
    inverter_id: str | None = Query(None),
    from_ts: datetime | None = Query(None, alias="from"),
    to_ts: datetime | None = Query(None, alias="to"),
    limit: int = Query(100, ge=1, le=10000),
):
    """Query readings with optional filters, newest first."""
    query = select(InverterReading).order_by(InverterReading.timestamp.desc())

    if inverter_id:
        query = query.where(InverterReading.inverter_id == inverter_id)
    if from_ts:
        query = query.where(InverterReading.timestamp >= from_ts)
    if to_ts:
        query = query.where(InverterReading.timestamp <= to_ts)

    query = query.limit(limit)
    result = await session.execute(query)
    return result.scalars().all()
