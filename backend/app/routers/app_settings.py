from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from app.services import app_settings as svc

router = APIRouter(prefix="/api/settings", tags=["settings"])


class AppSettingsOut(BaseModel):
    timezone: str


class AppSettingsPatch(BaseModel):
    timezone: str | None = None


@router.get("", response_model=AppSettingsOut)
async def get_settings() -> AppSettingsOut:
    return AppSettingsOut(**svc.get_all())


@router.patch("", response_model=AppSettingsOut)
async def patch_settings(body: AppSettingsPatch) -> AppSettingsOut:
    patch = {k: v for k, v in body.model_dump().items() if v is not None}
    return AppSettingsOut(**svc.update(patch))
