"""Tests for the Excel (.xlsx) service."""
from __future__ import annotations

from app.schemas.field_spec import FieldDefinition, FieldValueType
from app.services import xlsx_service
from tests.conftest import build_xlsx


def _cell_field(fid: str, cell: str, ftype: FieldValueType = FieldValueType.string) -> FieldDefinition:
    return FieldDefinition(id=fid, label=fid.title(), sheet="Sheet1", cell=cell, type=ftype)


def test_extract_cell_values():
    data = build_xlsx({"B1": "Ada", "B2": 87})
    fields = [
        _cell_field("name", "B1"),
        _cell_field("score", "B2", FieldValueType.number),
    ]
    values = xlsx_service.extract_field_values(data, fields)
    assert values == {"name": "Ada", "score": 87}


def test_write_cell_values_roundtrip():
    data = build_xlsx({"B1": "", "B2": 0})
    fields = [
        _cell_field("name", "B1"),
        _cell_field("score", "B2", FieldValueType.number),
    ]
    out = xlsx_service.write_field_values(data, fields, {"name": "Ada", "score": "91"})
    values = xlsx_service.extract_field_values(out, fields)
    assert values["name"] == "Ada"
    assert values["score"] == 91.0


def test_integer_coercion():
    data = build_xlsx({"B2": 0})
    fields = [_cell_field("score", "B2", FieldValueType.integer)]
    out = xlsx_service.write_field_values(data, fields, {"score": "42"})
    assert xlsx_service.extract_field_values(out, fields)["score"] == 42


def test_build_workbook_view_marks_editable_cells():
    data = build_xlsx({"A1": "Name", "B1": "", "A2": "Score", "B2": 0})
    fields = [_cell_field("name", "B1"), _cell_field("score", "B2")]
    view = xlsx_service.build_workbook_view(data, fields)
    assert len(view.sheets) == 1
    sheet = view.sheets[0]
    editable = {c.address for row in sheet.rows for c in row if c.editable}
    assert editable == {"B1", "B2"}


def test_non_numeric_in_number_field_kept_as_string_for_review():
    data = build_xlsx({"B2": 0})
    fields = [_cell_field("score", "B2", FieldValueType.number)]
    out = xlsx_service.write_field_values(data, fields, {"score": "not-a-number"})
    # Value is preserved as a string so the review engine can flag it.
    assert xlsx_service.extract_field_values(out, fields)["score"] == "not-a-number"


def test_write_cells_free_edit_grid():
    data = build_xlsx({"A1": "x"})
    out = xlsx_service.write_cells(data, {"Sheet1": {"A1": "Name", "B2": "42"}})
    fields = [
        _cell_field("name", "A1"),
        _cell_field("score", "B2", FieldValueType.number),
    ]
    vals = xlsx_service.extract_field_values(out, fields)
    assert vals["name"] == "Name"
    assert vals["score"] == 42
