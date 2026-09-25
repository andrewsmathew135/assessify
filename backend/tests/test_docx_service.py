"""Tests for the Word (.docx) service."""
from __future__ import annotations

from app.schemas.field_spec import FieldDefinition
from app.services import docx_service
from tests.conftest import build_docx, build_docx_with_content_control


def _word_field(fid: str, placeholder: str, rich: bool = False) -> FieldDefinition:
    return FieldDefinition(id=fid, label=fid.title(), placeholder=placeholder, rich_text=rich)


def test_find_placeholder_tokens(sample_docx):
    doc = docx_service.load_document(sample_docx)
    tokens = docx_service.find_placeholder_tokens(doc)
    assert tokens == {"full_name", "motivation"}


def test_write_and_readback_placeholder_value(sample_docx):
    fields = [_word_field("full_name", "{{full_name}}")]
    out = docx_service.write_field_values(sample_docx, fields, {"full_name": "Ada Lovelace"})

    doc = docx_service.load_document(out)
    text = docx_service.get_full_text(doc)
    assert "Ada Lovelace" in text
    # The placeholder token is consumed after writing.
    assert "{{full_name}}" not in text


def test_unfilled_placeholder_reports_none(sample_docx):
    fields = [_word_field("full_name", "{{full_name}}"), _word_field("motivation", "{{motivation}}")]
    result = docx_service.extract_field_values(sample_docx, fields)
    assert result.values == {"full_name": None, "motivation": None}


def test_content_control_extraction():
    data = build_docx_with_content_control("full_name", "Grace Hopper")
    fields = [_word_field("full_name", "{{full_name}}")]
    result = docx_service.extract_field_values(data, fields)
    assert result.values["full_name"] == "Grace Hopper"
    assert "full_name" not in result.uncaptured


def test_edited_placeholder_marked_uncaptured():
    # Candidate replaced the placeholder with free text; no content control.
    data = build_docx(["Dear Alan Turing,"])
    fields = [_word_field("full_name", "{{full_name}}")]
    result = docx_service.extract_field_values(data, fields)
    assert result.values["full_name"] is None
    assert "full_name" in result.uncaptured


def test_rich_text_writeback_applies_bold(sample_docx):
    fields = [_word_field("motivation", "{{motivation}}", rich=True)]
    out = docx_service.write_field_values(
        sample_docx, fields, {"motivation": "<p>I am <strong>very</strong> keen</p>"}
    )
    doc = docx_service.load_document(out)
    text = docx_service.get_full_text(doc)
    assert "very" in text and "keen" in text
    # At least one run in the document is bold.
    assert any(run.bold for p in doc.paragraphs for run in p.runs)


def test_build_document_view_splits_runs(sample_docx):
    fields = [_word_field("full_name", "{{full_name}}"), _word_field("motivation", "{{motivation}}")]
    blocks = docx_service.build_document_view(sample_docx, fields)
    field_runs = [r for b in blocks for r in b["runs"] if "field" in r]
    assert {r["field"] for r in field_runs} == {"full_name", "motivation"}


def test_document_to_html_renders_text(sample_docx):
    html = docx_service.document_to_html(sample_docx)
    assert "<p>" in html or "<h1>" in html


def test_html_to_docx_roundtrip_preserves_content_and_bold():
    out = docx_service.html_to_docx(
        "<h1>Title</h1><p>Alpha <strong>Beta</strong></p><ul><li>Gamma</li></ul>"
    )
    assert out[:2] == b"PK"
    doc = docx_service.load_document(out)
    text = docx_service.get_full_text(doc)
    assert "Alpha" in text and "Beta" in text and "Gamma" in text
    assert any(run.bold for p in doc.paragraphs for run in p.runs)
