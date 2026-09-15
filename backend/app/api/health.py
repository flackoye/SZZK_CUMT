"""Health check endpoint."""
from __future__ import annotations

from fastapi import APIRouter
from app.config import DEFAULT_MODEL_ID, DEVICE
from app.schemas import HealthResponse
from app.services.model_service import model_service

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def get_health():
    """Return backend status and model readiness."""
    is_ready = model_service.is_ready
    error_msg = model_service.error_message
    return HealthResponse(
        status="ok" if is_ready else "degraded",
        model_ready=is_ready,
        model_id=DEFAULT_MODEL_ID,
        device=str(DEVICE),
        message=error_msg,
    )

