"""Template model: an uploaded Word/Excel assessment file + its field spec."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, Enum, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.enums import FileType


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Template(Base):
    __tablename__ = "templates"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    instructions: Mapped[str] = mapped_column(Text, default="")
    file_type: Mapped[FileType] = mapped_column(Enum(FileType), nullable=False)
    original_object_key: Mapped[str] = mapped_column(String(512), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    # The field definition (see schemas.field_spec.FieldSpec).
    field_spec: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    sessions: Mapped[list["CandidateSession"]] = relationship(  # noqa: F821
        back_populates="template", cascade="all, delete-orphan"
    )
