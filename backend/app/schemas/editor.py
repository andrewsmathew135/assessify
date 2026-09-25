"""Schemas for the in-browser editor payloads (candidate side)."""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel

from app.schemas.field_spec import FieldDefinition


class CellSchema(BaseModel):
    address: str
    value: Any = None
    formula: str | None = None
    editable: bool = False


class SheetSchema(BaseModel):
    name: str
    rows: list[list[CellSchema]]
    n_rows: int
    n_cols: int


class WorkbookViewSchema(BaseModel):
    file_type: Literal["xlsx"] = "xlsx"
    sheets: list[SheetSchema]
    fields: list[FieldDefinition]


class DocumentBlockSchema(BaseModel):
    type: str = "paragraph"
    style: str | None = None
    runs: list[dict]


class DocumentViewSchema(BaseModel):
    file_type: Literal["docx"] = "docx"
    blocks: list[DocumentBlockSchema]
    fields: list[FieldDefinition]


class DocumentHtmlSchema(BaseModel):
    """Full document rendered as editable HTML (Google Docs-style editor)."""

    file_type: Literal["docx"] = "docx"
    html: str
    fields: list[FieldDefinition]
