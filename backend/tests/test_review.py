"""Tests for the automated review engine."""
from __future__ import annotations

from app.models.enums import FileType, ReviewStatus
from app.schemas.field_spec import FieldDefinition, FieldSpec, FieldValueType
from app.services import docx_service, review
from tests.conftest import build_docx, build_xlsx


def _spec_xlsx() -> FieldSpec:
    return FieldSpec(
        fields=[
            FieldDefinition(id="name", label="Name", sheet="Sheet1", cell="B1", required=True),
            FieldDefinition(
                id="score",
                label="Score",
                sheet="Sheet1",
                cell="B2",
                type=FieldValueType.number,
                required=True,
                min=0,
                max=100,
            ),
        ]
    )


def test_all_valid_passes():
    original = build_xlsx({"B1": "", "B2": 0})
    submitted = build_xlsx({"B1": "Ada", "B2": 88})
    outcome = review.review_submission(FileType.xlsx, _spec_xlsx(), submitted, original)
    assert outcome.report.status is ReviewStatus.passed
    assert outcome.score == 100.0


def test_missing_required_fails():
    original = build_xlsx({"B1": "", "B2": 0})
    submitted = build_xlsx({"B1": "", "B2": 50})  # name left blank
    outcome = review.review_submission(FileType.xlsx, _spec_xlsx(), submitted, original)
    assert outcome.report.status is ReviewStatus.failed
    assert any("required" in c.id for c in outcome.report.checks if not c.passed)


def test_out_of_range_fails():
    original = build_xlsx({"B1": "", "B2": 0})
    submitted = build_xlsx({"B1": "Ada", "B2": 150})  # above max 100
    outcome = review.review_submission(FileType.xlsx, _spec_xlsx(), submitted, original)
    assert outcome.report.status is ReviewStatus.failed
    assert any(c.id.endswith(":max") for c in outcome.report.checks if not c.passed)


def test_non_numeric_score_fails():
    original = build_xlsx({"B1": "", "B2": 0})
    submitted = build_xlsx({"B1": "Ada", "B2": "high"})
    outcome = review.review_submission(FileType.xlsx, _spec_xlsx(), submitted, original)
    assert outcome.report.status is ReviewStatus.failed


def test_unexpected_change_needs_review():
    original = build_xlsx({"A1": "Name", "B1": "", "A2": "Score", "B2": 0})
    # Candidate changed A1 (a label cell that is NOT editable) as well.
    submitted = build_xlsx({"A1": "CHANGED", "B1": "Ada", "A2": "Score", "B2": 80})
    outcome = review.review_submission(FileType.xlsx, _spec_xlsx(), submitted, original)
    assert outcome.report.status is ReviewStatus.needs_review
    assert any(c.id == "file:unexpected_changes" for c in outcome.report.checks)


def test_diff_summary_tracks_changes():
    original = build_xlsx({"B1": "", "B2": 0})
    submitted = build_xlsx({"B1": "Ada", "B2": 88})
    outcome = review.review_submission(FileType.xlsx, _spec_xlsx(), submitted, original)
    changed = {d.field_id for d in outcome.diff.fields if d.changed}
    assert changed == {"name", "score"}


def test_docx_in_browser_uses_provided_values():
    # For in-browser Word edits the provided values are authoritative; extracting
    # from the generated file would lose them (placeholders are replaced).
    original = build_docx(["Dear {{name}},", "Motivation: {{motivation}}"])
    spec = FieldSpec(
        fields=[
            FieldDefinition(id="name", label="Name", placeholder="{{name}}", required=True),
            FieldDefinition(
                id="motivation",
                label="Motivation",
                placeholder="{{motivation}}",
                required=True,
                min_length=5,
                rich_text=True,
            ),
        ]
    )
    provided = {"name": "Ada", "motivation": "<p>I love working with data</p>"}
    submitted = docx_service.write_field_values(original, spec.for_word(), provided)
    outcome = review.review_submission(
        FileType.docx, spec, submitted, original, provided_values=provided
    )
    assert outcome.report.status is ReviewStatus.passed
    assert outcome.values["name"] == "Ada"


def test_docx_in_browser_missing_required_fails():
    original = build_docx(["Dear {{name}},"])
    spec = FieldSpec(
        fields=[FieldDefinition(id="name", label="Name", placeholder="{{name}}", required=True)]
    )
    outcome = review.review_submission(
        FileType.docx, spec, original, original, provided_values={"name": ""}
    )
    assert outcome.report.status is ReviewStatus.failed
