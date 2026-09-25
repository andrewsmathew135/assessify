"""Excel (.xlsx) handling: extract cell values, write values back into the
original workbook (preserving other cells/formatting), build a grid view for the
in-browser spreadsheet editor, and diff against the template.

openpyxl does not evaluate formulas, so for cells containing a formula we fall
back to the value Excel cached the last time the file was saved (``data_only``).
Authoritative range/type validation always happens server-side on submit.
"""
from __future__ import annotations

import io
from dataclasses import dataclass, field
from datetime import date, datetime

from openpyxl import load_workbook
from openpyxl.utils import get_column_letter
from openpyxl.utils.cell import coordinate_to_tuple

from app.core.errors import CorruptFileError
from app.schemas.field_spec import FieldDefinition, FieldValueType

# Safety caps so an oversized sheet cannot blow up the grid view payload.
_MAX_VIEW_ROWS = 200
_MAX_VIEW_COLS = 40


@dataclass
class CellView:
    address: str
    value: object = None
    formula: str | None = None
    editable: bool = False


@dataclass
class SheetView:
    name: str
    rows: list[list[CellView]] = field(default_factory=list)
    n_rows: int = 0
    n_cols: int = 0


@dataclass
class WorkbookView:
    sheets: list[SheetView] = field(default_factory=list)


def _open(data: bytes, data_only: bool):
    try:
        return load_workbook(io.BytesIO(data), data_only=data_only, keep_vba=False)
    except Exception as exc:  # openpyxl raises assorted errors on bad input
        raise CorruptFileError("The Excel file could not be opened or is corrupt.") from exc


def _effective_value(wb_formula, wb_data, sheet: str, cell: str):
    """Return the literal value, or the cached computed value for a formula."""
    if sheet not in wb_formula.sheetnames:
        return None
    raw = wb_formula[sheet][cell].value
    if isinstance(raw, str) and raw.startswith("="):
        try:
            return wb_data[sheet][cell].value
        except Exception:  # noqa: BLE001
            return None
    return raw


def extract_field_values(data: bytes, fields: list[FieldDefinition]) -> dict[str, object]:
    """Read the value of each field's target cell."""
    wb_f = _open(data, data_only=False)
    wb_d = _open(data, data_only=True)
    try:
        values: dict[str, object] = {}
        for fd in fields:
            if not (fd.sheet and fd.cell):
                continue
            values[fd.id] = _effective_value(wb_f, wb_d, fd.sheet, fd.cell)
        return values
    finally:
        wb_f.close()
        wb_d.close()


def _coerce(fd: FieldDefinition, raw: object):
    """Best-effort convert a submitted value to the field's declared type."""
    if raw is None:
        return None
    if fd.type in (FieldValueType.number, FieldValueType.integer):
        try:
            num = float(str(raw).strip())
            return int(num) if fd.type is FieldValueType.integer and num.is_integer() else num
        except (TypeError, ValueError):
            return str(raw)  # keep as-is; review will flag the type mismatch
    if fd.type is FieldValueType.boolean:
        s = str(raw).strip().lower()
        if s in ("true", "1", "yes"):
            return True
        if s in ("false", "0", "no"):
            return False
        return str(raw)
    if fd.type is FieldValueType.date:
        try:
            return datetime.fromisoformat(str(raw)).date()
        except ValueError:
            return str(raw)
    return str(raw)


def write_field_values(
    data: bytes, fields: list[FieldDefinition], values: dict[str, object]
) -> bytes:
    """Write candidate ``values`` into the original workbook, returning new bytes."""
    wb = _open(data, data_only=False)
    try:
        for fd in fields:
            if not (fd.sheet and fd.cell) or fd.id not in values:
                continue
            if fd.sheet not in wb.sheetnames:
                continue
            wb[fd.sheet][fd.cell] = _coerce(fd, values[fd.id])
        out = io.BytesIO()
        wb.save(out)
        return out.getvalue()
    finally:
        wb.close()


def _coerce_cell(raw: object):
    """Coerce a raw grid string into a formula, number, or text for a free cell."""
    if raw is None:
        return None
    s = str(raw)
    if s == "":
        return None
    if s.startswith("="):
        return s  # openpyxl stores a leading-'=' string as a formula
    stripped = s.strip()
    try:
        if "." in stripped or "e" in stripped.lower():
            return float(stripped)
        return int(stripped)
    except ValueError:
        return s


def write_cells(data: bytes, edits: dict[str, dict[str, object]]) -> bytes:
    """Write arbitrary cell edits (Google Sheets-style free editing) back.

    ``edits`` maps sheet name -> {A1-address -> value}. Values are coerced to
    numbers/formulas where possible; empty strings clear the cell.
    """
    wb = _open(data, data_only=False)
    try:
        for sheet_name, cells in edits.items():
            if sheet_name not in wb.sheetnames:
                continue
            ws = wb[sheet_name]
            for addr, value in cells.items():
                ws[addr.upper()] = _coerce_cell(value)
        out = io.BytesIO()
        wb.save(out)
        return out.getvalue()
    finally:
        wb.close()


def _json_safe(value: object):
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return value


def build_workbook_view(data: bytes, fields: list[FieldDefinition]) -> WorkbookView:
    """Build a capped grid representation for the in-browser spreadsheet editor."""
    wb_f = _open(data, data_only=False)
    wb_d = _open(data, data_only=True)
    try:
        # Map editable cells per sheet from the field spec.
        editable: dict[str, set[str]] = {}
        for fd in fields:
            if fd.sheet and fd.cell:
                editable.setdefault(fd.sheet, set()).add(fd.cell.upper())

        view = WorkbookView()
        for name in wb_f.sheetnames:
            ws = wb_f[name]
            n_rows = min(ws.max_row or 1, _MAX_VIEW_ROWS)
            n_cols = min(ws.max_column or 1, _MAX_VIEW_COLS)
            sheet_view = SheetView(name=name, n_rows=n_rows, n_cols=n_cols)
            editable_cells = editable.get(name, set())
            for r in range(1, n_rows + 1):
                row_cells: list[CellView] = []
                for c in range(1, n_cols + 1):
                    addr = f"{get_column_letter(c)}{r}"
                    raw = ws.cell(row=r, column=c).value
                    formula = raw if isinstance(raw, str) and raw.startswith("=") else None
                    display = _effective_value(wb_f, wb_d, name, addr) if formula else raw
                    row_cells.append(
                        CellView(
                            address=addr,
                            value=_json_safe(display),
                            formula=formula,
                            editable=addr in editable_cells,
                        )
                    )
                sheet_view.rows.append(row_cells)
            view.sheets.append(sheet_view)
        return view
    finally:
        wb_f.close()
        wb_d.close()
