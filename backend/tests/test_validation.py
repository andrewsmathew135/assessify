"""Tests for the upload validation gate (security-critical)."""
from __future__ import annotations

import io
import zipfile

import pytest

from app.core.errors import (
    CorruptFileError,
    FileTooLargeError,
    MacroDetectedError,
    UnsupportedFileTypeError,
)
from app.models.enums import FileType
from app.services import validation
from tests.conftest import build_docx, build_macro_docx, build_xlsx


def test_valid_docx_passes(sample_docx):
    assert validation.validate_upload("template.docx", sample_docx) is FileType.docx


def test_valid_xlsx_passes(sample_xlsx):
    assert validation.validate_upload("template.xlsx", sample_xlsx) is FileType.xlsx


def test_empty_file_rejected():
    with pytest.raises(CorruptFileError):
        validation.validate_upload("template.docx", b"")


def test_non_office_bytes_rejected():
    with pytest.raises(CorruptFileError):
        validation.validate_upload("template.docx", b"not an office file at all")


def test_macro_enabled_extension_rejected(sample_docx):
    with pytest.raises(MacroDetectedError):
        validation.validate_upload("template.docm", sample_docx)


def test_xlsm_extension_rejected(sample_xlsx):
    with pytest.raises(MacroDetectedError):
        validation.validate_upload("template.xlsm", sample_xlsx)


def test_embedded_macro_rejected_even_with_docx_extension():
    macro_docx = build_macro_docx()
    with pytest.raises(MacroDetectedError):
        validation.validate_upload("looks_clean.docx", macro_docx)


def test_unsupported_extension_rejected():
    with pytest.raises(UnsupportedFileTypeError):
        validation.validate_upload("resume.pdf", b"%PDF-1.7 ...")


def test_extension_content_mismatch_rejected(sample_xlsx):
    # An xlsx renamed to .docx must be rejected (anti-spoofing).
    with pytest.raises(UnsupportedFileTypeError):
        validation.validate_upload("sneaky.docx", sample_xlsx)


def test_oversized_file_rejected(monkeypatch, sample_docx):
    class _S:
        max_upload_bytes = 10

    monkeypatch.setattr(validation, "get_settings", lambda: _S())
    with pytest.raises(FileTooLargeError):
        validation.validate_upload("template.docx", sample_docx)


def test_zip_without_office_parts_rejected():
    bio = io.BytesIO()
    with zipfile.ZipFile(bio, "w") as zf:
        zf.writestr("random.txt", "hello")
    with pytest.raises(CorruptFileError):
        validation.validate_upload("template.docx", bio.getvalue())
