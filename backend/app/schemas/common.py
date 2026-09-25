"""Shared/common response schemas."""
from __future__ import annotations

from pydantic import BaseModel


class ErrorResponse(BaseModel):
    """Uniform error envelope returned for every handled error."""

    code: str
    message: str
    details: dict | None = None


class MessageResponse(BaseModel):
    message: str
