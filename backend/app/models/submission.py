"""Submission model: a candidate's submitted file plus its review outcome."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, Enum, Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.enums import ReviewStatus, SubmissionSource


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Submission(Base):
    __tablename__ = "submissions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    session_id: Mapped[str] = mapped_column(
        ForeignKey("candidate_sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    template_id: Mapped[str] = mapped_column(
        ForeignKey("templates.id", ondelete="CASCADE"), nullable=False, index=True
    )
    submitted_object_key: Mapped[str] = mapped_column(String(512), nullable=False)
    submitted_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    source: Mapped[SubmissionSource] = mapped_column(
        Enum(SubmissionSource), default=SubmissionSource.upload, nullable=False
    )
    field_values: Mapped[dict] = mapped_column(JSON, default=dict)
    review_status: Mapped[ReviewStatus] = mapped_column(
        Enum(ReviewStatus), default=ReviewStatus.pending, nullable=False, index=True
    )
    review_report: Mapped[dict] = mapped_column(JSON, default=dict)
    diff_summary: Mapped[dict] = mapped_column(JSON, default=dict)
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    session: Mapped["CandidateSession"] = relationship(back_populates="submissions")  # noqa: F821
