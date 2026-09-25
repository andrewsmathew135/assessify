"""Template schemas."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import FileType
from app.schemas.field_spec import FieldSpec


class TemplateUpdate(BaseModel):
    """Editable template metadata + field specification."""

    name: str | None = Field(default=None, min_length=1, max_length=200)
    instructions: str | None = None
    field_spec: FieldSpec | None = None


class TemplateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    instructions: str
    file_type: FileType
    original_filename: str
    field_spec: FieldSpec
    created_at: datetime


class TemplateListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    file_type: FileType
    original_filename: str
    created_at: datetime
