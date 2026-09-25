"""Health / readiness endpoints."""
from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from app.config import get_settings
from app.schemas.common import MessageResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=MessageResponse)
def health() -> MessageResponse:
    return MessageResponse(message="ok")


class PublicConfig(BaseModel):
    app_name: str
    auth_enabled: bool


@router.get("/config", response_model=PublicConfig)
def public_config() -> PublicConfig:
    settings = get_settings()
    return PublicConfig(app_name=settings.app_name, auth_enabled=settings.auth_enabled)
