"""Submission + review-report schemas."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import ReviewStatus, SubmissionSource

class CheckResult(BaseModel):
    """One automated check outcome."""

    id: str
    label: str
    passed: bool
    severity: Literal["error", "warning", "info"] = "error"
    message: str


class ReviewReport(BaseModel):
    status: ReviewStatus
    summary: str
    checks: list[CheckResult] = Field(default_factory=list)
    passed_count: int = 0
    failed_count: int = 0
    warning_count: int = 0


class FieldDiff(BaseModel):
    field_id: str
    label: str
    original: Any = None
    submitted: Any = None
    changed: bool = False


class DiffSummary(BaseModel):
    fields: list[FieldDiff] = Field(default_factory=list)
    changed_count: int = 0


class InBrowserSubmitRequest(BaseModel):
    """Candidate submits their work from the in-browser editor.

    Exactly one editing mode is used per submission:
    * ``field_values`` — legacy per-field editing (values keyed by field id).
    * ``cell_edits`` — Google Sheets-style free grid editing (sheet -> {cell -> value}).
    * ``document_html`` — Google Docs-style free document editing (edited HTML).
    """

    field_values: dict[str, Any] = Field(default_factory=dict)
    cell_edits: dict[str, dict[str, Any]] | None = None
    document_html: str | None = None


class SubmissionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    session_id: str
    template_id: str
    submitted_filename: str
    source: SubmissionSource
    field_values: dict[str, Any]
    review_status: ReviewStatus
    review_report: ReviewReport | None = None
    diff_summary: DiffSummary | None = None
    score: float | None = None
    created_at: datetime
    reviewed_at: datetime | None = None


class SubmissionListItem(BaseModel):
    """Row in the admin review dashboard."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    session_id: str
    template_id: str
    submitted_filename: str
    review_status: ReviewStatus
    score: float | None = None
    created_at: datetime


class SubmissionConfirmation(BaseModel):
    """Friendly candidate-facing confirmation after submit."""

    submission_id: str
    submitted_filename: str
    review_status: ReviewStatus
    summary: str
    fields_submitted: dict[str, Any]


class DashboardRow(BaseModel):
    """A single row in the admin review dashboard (joined view)."""

    submission_id: str
    session_id: str
    template_id: str
    template_name: str
    candidate_name: str | None = None
    candidate_email: str | None = None
    submitted_filename: str
    source: SubmissionSource
    review_status: ReviewStatus
    score: float | None = None
    created_at: datetime


class SubmissionDetail(SubmissionResponse):
    """Full submission plus candidate/template context for the detail view."""

    candidate_name: str | None = None
    candidate_email: str | None = None
    template_name: str
    file_type: str
