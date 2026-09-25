"""CandidateSession model: one unguessable link per candidate."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Enum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.enums import SessionStatus


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


class CandidateSession(Base):
    __tablename__ = "candidate_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    template_id: Mapped[str] = mapped_column(
        ForeignKey("templates.id", ondelete="CASCADE"), nullable=False, index=True
    )
    token: Mapped[str] = mapped_column(String(128), unique=True, index=True, nullable=False)
    candidate_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    candidate_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[SessionStatus] = mapped_column(
        Enum(SessionStatus), default=SessionStatus.pending, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    opened_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    template: Mapped["Template"] = relationship(back_populates="sessions")  # noqa: F821
    submissions: Mapped[list["Submission"]] = relationship(  # noqa: F821
        back_populates="session", cascade="all, delete-orphan"
    )

    def is_expired(self, now: datetime | None = None) -> bool:
        if self.expires_at is None:
            return False
        now = now or datetime.now(timezone.utc)
        expires = self.expires_at
        if expires.tzinfo is None:  # SQLite may return naive datetimes
            expires = expires.replace(tzinfo=timezone.utc)
        return now >= expires
