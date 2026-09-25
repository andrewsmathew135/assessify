"""Candidate endpoints: open a link, view/edit the assignment, and submit.

Access control is by the unguessable link token only (no login). The token is
looked up in constant paths and never enumerated.
"""
from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_storage_dep
from app.core.errors import ForbiddenError, NotFoundError, ValidationError
from app.models.candidate_session import CandidateSession
from app.models.enums import FileType, SessionStatus, SubmissionSource
from app.models.submission import Submission
from app.models.template import Template
from app.schemas.editor import DocumentHtmlSchema, DocumentViewSchema, WorkbookViewSchema
from app.schemas.field_spec import FieldSpec
from app.schemas.session import CandidateAssignmentResponse
from app.schemas.submission import InBrowserSubmitRequest, SubmissionConfirmation
from app.services import docx_service, submission_service, xlsx_service
from app.services.storage import Storage
from app.services.validation import validate_upload

router = APIRouter(prefix="/candidate", tags=["candidate"])


def _get_session(db: Session, token: str) -> CandidateSession:
    session = db.scalar(select(CandidateSession).where(CandidateSession.token == token))
    if session is None:
        raise NotFoundError("This assignment link is invalid.")
    return session


def _get_template(db: Session, session: CandidateSession) -> Template:
    template = db.get(Template, session.template_id)
    if template is None:
        raise NotFoundError("The assignment for this link no longer exists.")
    return template


def _refresh_expiry(db: Session, session: CandidateSession) -> None:
    if session.is_expired() and session.status != SessionStatus.expired:
        session.status = SessionStatus.expired
        db.commit()


def _has_submission(db: Session, session_id: str) -> bool:
    return db.scalar(select(Submission.id).where(Submission.session_id == session_id)) is not None


@router.get("/{token}", response_model=CandidateAssignmentResponse)
def open_assignment(token: str, db: Session = Depends(get_db)) -> CandidateAssignmentResponse:
    session = _get_session(db, token)
    template = _get_template(db, session)
    _refresh_expiry(db, session)

    # Mark as opened the first time (unless already submitted/expired).
    if session.status == SessionStatus.pending:
        session.status = SessionStatus.opened
        session.opened_at = datetime.now(timezone.utc)
        db.commit()

    spec = FieldSpec.model_validate(template.field_spec or {"fields": []})
    return CandidateAssignmentResponse(
        session_token=session.token,
        status=session.status,
        candidate_name=session.candidate_name,
        template_name=template.name,
        instructions=template.instructions,
        file_type=template.file_type,
        field_spec=spec,
        expires_at=session.expires_at,
        already_submitted=_has_submission(db, session.id),
    )


@router.get("/{token}/workbook", response_model=WorkbookViewSchema)
def get_workbook(
    token: str, db: Session = Depends(get_db), storage: Storage = Depends(get_storage_dep)
) -> WorkbookViewSchema:
    session = _get_session(db, token)
    template = _get_template(db, session)
    if template.file_type is not FileType.xlsx:
        raise ValidationError("This assignment is not a spreadsheet.")
    spec = FieldSpec.model_validate(template.field_spec or {"fields": []})
    data = storage.get(template.original_object_key)
    view = xlsx_service.build_workbook_view(data, spec.for_excel())
    return WorkbookViewSchema(
        sheets=[asdict(s) for s in view.sheets],
        fields=spec.for_excel(),
    )


@router.get("/{token}/document", response_model=DocumentViewSchema)
def get_document(
    token: str, db: Session = Depends(get_db), storage: Storage = Depends(get_storage_dep)
) -> DocumentViewSchema:
    session = _get_session(db, token)
    template = _get_template(db, session)
    if template.file_type is not FileType.docx:
        raise ValidationError("This assignment is not a Word document.")
    spec = FieldSpec.model_validate(template.field_spec or {"fields": []})
    data = storage.get(template.original_object_key)
    blocks = docx_service.build_document_view(data, spec.for_word())
    return DocumentViewSchema(blocks=blocks, fields=spec.for_word())


@router.get("/{token}/document-html", response_model=DocumentHtmlSchema)
def get_document_html(
    token: str, db: Session = Depends(get_db), storage: Storage = Depends(get_storage_dep)
) -> DocumentHtmlSchema:
    session = _get_session(db, token)
    template = _get_template(db, session)
    if template.file_type is not FileType.docx:
        raise ValidationError("This assignment is not a Word document.")
    spec = FieldSpec.model_validate(template.field_spec or {"fields": []})
    data = storage.get(template.original_object_key)
    html = docx_service.document_to_html(data)
    return DocumentHtmlSchema(html=html, fields=spec.for_word())


@router.post("/{token}/submit-upload", response_model=SubmissionConfirmation)
async def submit_upload(
    token: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    storage: Storage = Depends(get_storage_dep),
) -> SubmissionConfirmation:
    session = _get_session(db, token)
    template = _get_template(db, session)
    _guard_submittable(db, session)

    data = await file.read()
    file_type = validate_upload(file.filename or "", data)
    if file_type is not template.file_type:
        raise ValidationError(
            f"This assignment expects a .{template.file_type.value} file, "
            f"but you uploaded a .{file_type.value} file."
        )

    submission = submission_service.finalize_submission(
        db,
        storage,
        session=session,
        template=template,
        submitted_bytes=data,
        filename=file.filename or f"submission.{file_type.value}",
        source=SubmissionSource.upload,
    )
    return _confirmation(submission)


@router.post("/{token}/submit-edits", response_model=SubmissionConfirmation)
def submit_edits(
    token: str,
    body: InBrowserSubmitRequest,
    db: Session = Depends(get_db),
    storage: Storage = Depends(get_storage_dep),
) -> SubmissionConfirmation:
    session = _get_session(db, token)
    template = _get_template(db, session)
    _guard_submittable(db, session)

    spec = FieldSpec.model_validate(template.field_spec or {"fields": []})
    original = storage.get(template.original_object_key)

    provided_values: dict | None = None
    if template.file_type is FileType.docx:
        if body.document_html is not None:
            # Google Docs-style: rebuild the document from the edited HTML.
            submitted_bytes = docx_service.html_to_docx(body.document_html)
        else:
            submitted_bytes = docx_service.write_field_values(
                original, spec.for_word(), body.field_values
            )
            provided_values = body.field_values
    else:
        if body.cell_edits is not None:
            # Google Sheets-style: write all edited cells, then extract fields.
            submitted_bytes = xlsx_service.write_cells(original, body.cell_edits)
            provided_values = xlsx_service.extract_field_values(
                submitted_bytes, spec.for_excel()
            )
        else:
            submitted_bytes = xlsx_service.write_field_values(
                original, spec.for_excel(), body.field_values
            )
            provided_values = body.field_values

    base = template.original_filename.rsplit(".", 1)[0]
    filename = f"{base}_submission.{template.file_type.value}"
    submission = submission_service.finalize_submission(
        db,
        storage,
        session=session,
        template=template,
        submitted_bytes=submitted_bytes,
        filename=filename,
        source=SubmissionSource.in_browser,
        provided_values=provided_values,
    )
    return _confirmation(submission)


def _guard_submittable(db: Session, session: CandidateSession) -> None:
    _refresh_expiry(db, session)
    if session.status == SessionStatus.expired:
        raise ForbiddenError("This assignment link has expired.")


def _confirmation(submission: Submission) -> SubmissionConfirmation:
    report = submission.review_report or {}
    return SubmissionConfirmation(
        submission_id=submission.id,
        submitted_filename=submission.submitted_filename,
        review_status=submission.review_status,
        summary=report.get("summary", "Your submission was received."),
        fields_submitted=submission.field_values or {},
    )
