from __future__ import annotations

from fastapi import APIRouter, Depends

from backend.api.deps import get_services
from backend.core.orchestration.services import AppServices

router = APIRouter(prefix="/api/chaos", tags=["chaos"])


@router.get("/status")
async def get_status(services: AppServices = Depends(get_services)) -> dict:
    return {"enabled": services.chaos_state.enabled}


@router.post("/enable")
async def enable(services: AppServices = Depends(get_services)) -> dict:
    services.chaos_state.enable()
    return {"enabled": True}


@router.post("/disable")
async def disable(services: AppServices = Depends(get_services)) -> dict:
    services.chaos_state.disable()
    return {"enabled": False}
