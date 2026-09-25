"""Orchestration for finalising a submission: store file, run review, persist.

Kept separate from the routers so the end-to-end flow can be unit-tested without
HTTP, and reused by both the candidate submit path and an admin re-review.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.candidate_session import CandidateSession
from app.models.enums import ReviewStatus, SessionStatus, SubmissionSource
from app.models.submission import Submission
from app.models.template import Template
from app.schemas.field_spec import FieldSpec
from app.services import review
from app.services.storage import Storage, make_object_key
from app.services.validation import CONTENT_TYPE_BY_FILETYPE


def finalize_submission(
    db: Session,
    storage: Storage,
    *,
    session: CandidateSession,
    template: Template,
    submitted_bytes: bytes,
    filename: str,
    source: SubmissionSource,
    provided_values: dict | None = None,
) -> Submission:
    field_spec = FieldSpec.model_validate(template.field_spec or {"fields": []})

    # Store the submitted file.
    key = make_object_key(f"submissions/{session.id}", filename)
    storage.put(key, submitted_bytes, CONTENT_TYPE_BY_FILETYPE.get(template.file_type))

    # Run the automated review against the original template.
    original_bytes = storage.get(template.original_object_key)
    outcome = review.review_submission(
        file_type=template.file_type,
        field_spec=field_spec,
        submitted_bytes=submitted_bytes,
        original_bytes=original_bytes,
        provided_values=provided_values,
    )

    submission = Submission(
        session_id=session.id,
        template_id=template.id,
        submitted_object_key=key,
        submitted_filename=filename,
        source=source,
        field_values=outcome.values,
        review_status=outcome.report.status,
        review_report=outcome.report.model_dump(),
        diff_summary=outcome.diff.model_dump(),
        score=outcome.score,
        reviewed_at=datetime.now(timezone.utc),
    )
    db.add(submission)

    session.status = SessionStatus.submitted
    if session.opened_at is None:
        session.opened_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(submission)
    return submission


def rerun_review(db: Session, storage: Storage, submission: Submission) -> Submission:
    template = db.get(Template, submission.template_id)
    if template is None:
        submission.review_status = ReviewStatus.needs_review
        db.commit()
        return submission
    field_spec = FieldSpec.model_validate(template.field_spec or {"fields": []})
    submitted_bytes = storage.get(submission.submitted_object_key)
    original_bytes = storage.get(template.original_object_key)
    # For in-browser edits, re-validate the stored authoritative values.
    provided = submission.field_values if submission.source is SubmissionSource.in_browser else None
    outcome = review.review_submission(
        file_type=template.file_type,
        field_spec=field_spec,
        submitted_bytes=submitted_bytes,
        original_bytes=original_bytes,
        provided_values=provided,
    )
    submission.field_values = outcome.values
    submission.review_status = outcome.report.status
    submission.review_report = outcome.report.model_dump()
    submission.diff_summary = outcome.diff.model_dump()
    submission.score = outcome.score
    submission.reviewed_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(submission)
    return submission
