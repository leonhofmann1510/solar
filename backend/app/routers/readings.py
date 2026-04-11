from fastapi import APIRouter, Depends

from app.schemas import HealthResponse, InverterStatus, ReadingOut
from app.state import AppState, get_app_state

router = APIRouter(prefix="/api", tags=["readings"])


@router.get("/health", response_model=HealthResponse)
async def health(app_state: AppState = Depends(get_app_state)):
    """Health check with last-seen status per inverter."""
    inverters: list[InverterStatus] = []
    for inv_id in ("inv1", "inv2"):
        data = app_state.latest_readings.get(inv_id)
        inverters.append(InverterStatus(
            id=inv_id,
            last_seen=data.timestamp if data else None,
            connected=data is not None,
        ))
    return HealthResponse(status="ok", inverters=inverters)


@router.get("/readings/latest", response_model=list[ReadingOut])
async def latest_readings(app_state: AppState = Depends(get_app_state)):
    """Most recent reading for each inverter (in-memory, no DB)."""
    return list(app_state.latest_readings.values())
