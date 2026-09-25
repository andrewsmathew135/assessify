"""Candidate session schemas."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.enums import FileType, SessionStatus
from app.schemas.field_spec import FieldSpec


class SessionCreateRequest(BaseModel):
    template_id: str
    candidate_name: str | None = Field(default=None, max_length=200)
    candidate_email: EmailStr | None = None


class SessionResponse(BaseModel):
    """Admin-facing view of a session."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    template_id: str
    token: str
    candidate_name: str | None
    candidate_email: str | None
    status: SessionStatus
    created_at: datetime
    opened_at: datetime | None
    expires_at: datetime | None


class SessionLinkResponse(SessionResponse):
    """Session plus a ready-to-share candidate URL."""

    candidate_url: str


class CandidateAssignmentResponse(BaseModel):
    """Candidate-facing view returned when a link is opened (no secrets)."""

    session_token: str
    status: SessionStatus
    candidate_name: str | None
    template_name: str
    instructions: str
    file_type: FileType
    field_spec: FieldSpec
    expires_at: datetime | None
    already_submitted: bool
