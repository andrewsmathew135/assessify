"""Field specification schema.

This is the contract an admin defines per template: which cells (Excel) or
placeholders (Word) a candidate must fill, and what makes a value valid.
It is stored as JSON on the Template and drives both the in-browser editor and
the server-side review engine.
"""
from __future__ import annotations

import re
from enum import Enum

from pydantic import BaseModel, Field, field_validator, model_validator

# A1-style Excel cell reference, e.g. B2, AA10 (no absolute $ signs).
_CELL_RE = re.compile(r"^[A-Za-z]{1,3}[1-9][0-9]*$")


class FieldValueType(str, Enum):
    string = "string"
    number = "number"
    integer = "integer"
    boolean = "boolean"
    date = "date"


class FieldDefinition(BaseModel):
    """One thing the candidate must fill in."""

    id: str = Field(..., min_length=1, max_length=64, description="Stable identifier")
    label: str = Field(..., min_length=1, max_length=200)
    type: FieldValueType = FieldValueType.string
    required: bool = True
    help_text: str | None = Field(default=None, max_length=500)

    # --- Location (Excel) ---
    sheet: str | None = Field(default=None, max_length=100)
    cell: str | None = Field(default=None, description="A1-style reference, e.g. B2")

    # --- Location (Word) ---
    placeholder: str | None = Field(
        default=None, description="Named token in the document, e.g. {{full_name}}"
    )
    rich_text: bool = Field(default=False, description="Allow basic formatting (Word only)")

    # --- Value constraints ---
    min: float | None = None
    max: float | None = None
    min_length: int | None = Field(default=None, ge=0)
    max_length: int | None = Field(default=None, ge=0)
    pattern: str | None = Field(default=None, description="Regex the value must match")
    allowed_values: list[str] | None = None

    @field_validator("id")
    @classmethod
    def _valid_id(cls, v: str) -> str:
        if not re.match(r"^[A-Za-z0-9_.-]+$", v):
            raise ValueError("id may only contain letters, numbers, '_', '.', '-'")
        return v

    @field_validator("cell")
    @classmethod
    def _valid_cell(cls, v: str | None) -> str | None:
        if v is None:
            return v
        v = v.strip().upper()
        if not _CELL_RE.match(v):
            raise ValueError(f"'{v}' is not a valid A1-style cell reference")
        return v

    @field_validator("pattern")
    @classmethod
    def _valid_pattern(cls, v: str | None) -> str | None:
        if v is None:
            return v
        try:
            re.compile(v)
        except re.error as exc:
            raise ValueError(f"invalid regex pattern: {exc}") from exc
        return v

    @model_validator(mode="after")
    def _has_locator(self) -> "FieldDefinition":
        has_excel = bool(self.sheet and self.cell)
        has_word = bool(self.placeholder)
        if not has_excel and not has_word:
            raise ValueError(
                "field must define an Excel locator (sheet + cell) or a Word placeholder"
            )
        if self.min is not None and self.max is not None and self.min > self.max:
            raise ValueError("min cannot be greater than max")
        return self


class FieldSpec(BaseModel):
    """The full set of fields for a template."""

    fields: list[FieldDefinition] = Field(default_factory=list)

    @model_validator(mode="after")
    def _unique_ids(self) -> "FieldSpec":
        ids = [f.id for f in self.fields]
        dupes = {i for i in ids if ids.count(i) > 1}
        if dupes:
            raise ValueError(f"duplicate field ids: {', '.join(sorted(dupes))}")
        return self

    def for_excel(self) -> list[FieldDefinition]:
        return [f for f in self.fields if f.sheet and f.cell]

    def for_word(self) -> list[FieldDefinition]:
        return [f for f in self.fields if f.placeholder]
