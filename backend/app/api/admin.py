"""Admin endpoints: templates, field specs, candidate links, review dashboard.

All routes require a valid admin JWT (see :func:`get_current_admin`).
"""
from __future__ import annotations

import io
import os
import re

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_admin, get_db, get_storage_dep
from app.config import get_settings
from app.core.errors import NotFoundError, ValidationError
from app.models.candidate_session import CandidateSession
from app.models.enums import ReviewStatus, SessionStatus
from app.models.submission import Submission
from app.models.template import Template
from app.core.security import generate_link_token
from app.schemas.common import MessageResponse
from app.schemas.field_spec import FieldSpec
from app.schemas.session import (
    SessionCreateRequest,
    SessionLinkResponse,
    SessionResponse,
)
from app.schemas.submission import (
    DashboardRow,
    SubmissionDetail,
)
from app.schemas.template import TemplateListItem, TemplateResponse, TemplateUpdate
from app.services import submission_service
from app.services.storage import Storage, make_object_key
from app.services.validation import CONTENT_TYPE_BY_FILETYPE, validate_upload
from datetime import datetime, timedelta, timezone

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(get_current_admin)])


# --------------------------------------------------------------------------- #
# Templates
# --------------------------------------------------------------------------- #
@router.post("/templates", response_model=TemplateResponse, status_code=201)
async def create_template(
    name: str = Form(..., min_length=1, max_length=200),
    instructions: str = Form(""),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    storage: Storage = Depends(get_storage_dep),
) -> TemplateResponse:
    data = await file.read()
    file_type = validate_upload(file.filename or "", data)  # raises on any problem

    key = make_object_key("templates", file.filename or f"template.{file_type.value}")
    storage.put(key, data, CONTENT_TYPE_BY_FILETYPE.get(file_type))

    template = Template(
        name=name.strip(),
        instructions=instructions,
        file_type=file_type,
        original_object_key=key,
        original_filename=file.filename or f"template.{file_type.value}",
        field_spec={"fields": []},
    )
    db.add(template)
    db.commit()
    db.refresh(template)
    return TemplateResponse.model_validate(template)


@router.get("/templates", response_model=list[TemplateListItem])
def list_templates(db: Session = Depends(get_db)) -> list[TemplateListItem]:
    rows = db.scalars(select(Template).order_by(Template.created_at.desc())).all()
    return [TemplateListItem.model_validate(t) for t in rows]


@router.get("/templates/{template_id}", response_model=TemplateResponse)
def get_template(template_id: str, db: Session = Depends(get_db)) -> TemplateResponse:
    template = db.get(Template, template_id)
    if template is None:
        raise NotFoundError("Template not found.")
    return TemplateResponse.model_validate(template)


@router.patch("/templates/{template_id}", response_model=TemplateResponse)
def update_template(
    template_id: str, body: TemplateUpdate, db: Session = Depends(get_db)
) -> TemplateResponse:
    template = db.get(Template, template_id)
    if template is None:
        raise NotFoundError("Template not found.")
    if body.name is not None:
        template.name = body.name.strip()
    if body.instructions is not None:
        template.instructions = body.instructions
    if body.field_spec is not None:
        _validate_field_spec_targets(template, body.field_spec)
        template.field_spec = body.field_spec.model_dump()
    db.commit()
    db.refresh(template)
    return TemplateResponse.model_validate(template)


@router.delete("/templates/{template_id}", response_model=MessageResponse)
def delete_template(
    template_id: str,
    db: Session = Depends(get_db),
    storage: Storage = Depends(get_storage_dep),
) -> MessageResponse:
    template = db.get(Template, template_id)
    if template is None:
        raise NotFoundError("Template not found.")
    # Best-effort delete of stored files (template + submissions).
    for sess in template.sessions:
        for sub in sess.submissions:
            _safe_delete(storage, sub.submitted_object_key)
    _safe_delete(storage, template.original_object_key)
    db.delete(template)
    db.commit()
    return MessageResponse(message="Template deleted.")


@router.get("/templates/{template_id}/original")
def download_template(
    template_id: str,
    db: Session = Depends(get_db),
    storage: Storage = Depends(get_storage_dep),
) -> StreamingResponse:
    template = db.get(Template, template_id)
    if template is None:
        raise NotFoundError("Template not found.")
    data = storage.get(template.original_object_key)
    return _file_response(data, template.original_filename, template.file_type)


# --------------------------------------------------------------------------- #
# Candidate sessions (links)
# --------------------------------------------------------------------------- #
@router.post("/sessions", response_model=SessionLinkResponse, status_code=201)
def create_session(
    body: SessionCreateRequest, db: Session = Depends(get_db)
) -> SessionLinkResponse:
    template = db.get(Template, body.template_id)
    if template is None:
        raise NotFoundError("Template not found.")
    settings = get_settings()
    expires_at = None
    if settings.session_expiry_days > 0:
        expires_at = datetime.now(timezone.utc) + timedelta(days=settings.session_expiry_days)

    session = CandidateSession(
        template_id=template.id,
        token=generate_link_token(),
        candidate_name=body.candidate_name,
        candidate_email=body.candidate_email,
        status=SessionStatus.pending,
        expires_at=expires_at,
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return _session_link(session)


@router.get("/sessions", response_model=list[SessionResponse])
def list_sessions(
    template_id: str | None = Query(default=None), db: Session = Depends(get_db)
) -> list[SessionResponse]:
    stmt = select(CandidateSession).order_by(CandidateSession.created_at.desc())
    if template_id:
        stmt = stmt.where(CandidateSession.template_id == template_id)
    rows = db.scalars(stmt).all()
    return [SessionResponse.model_validate(s) for s in rows]


# --------------------------------------------------------------------------- #
# Review dashboard
# --------------------------------------------------------------------------- #
@router.get("/submissions", response_model=list[DashboardRow])
def list_submissions(
    status: ReviewStatus | None = Query(default=None),
    template_id: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> list[DashboardRow]:
    stmt = (
        select(Submission, CandidateSession, Template)
        .join(CandidateSession, Submission.session_id == CandidateSession.id)
        .join(Template, Submission.template_id == Template.id)
        .order_by(Submission.created_at.desc())
    )
    if status:
        stmt = stmt.where(Submission.review_status == status)
    if template_id:
        stmt = stmt.where(Submission.template_id == template_id)

    rows: list[DashboardRow] = []
    for sub, sess, tmpl in db.execute(stmt).all():
        rows.append(
            DashboardRow(
                submission_id=sub.id,
                session_id=sub.session_id,
                template_id=sub.template_id,
                template_name=tmpl.name,
                candidate_name=sess.candidate_name,
                candidate_email=sess.candidate_email,
                submitted_filename=sub.submitted_filename,
                source=sub.source,
                review_status=sub.review_status,
                score=sub.score,
                created_at=sub.created_at,
            )
        )
    return rows


@router.get("/submissions/{submission_id}", response_model=SubmissionDetail)
def get_submission(submission_id: str, db: Session = Depends(get_db)) -> SubmissionDetail:
    sub = db.get(Submission, submission_id)
    if sub is None:
        raise NotFoundError("Submission not found.")
    sess = db.get(CandidateSession, sub.session_id)
    tmpl = db.get(Template, sub.template_id)
    payload = {
        "id": sub.id,
        "session_id": sub.session_id,
        "template_id": sub.template_id,
        "submitted_filename": sub.submitted_filename,
        "source": sub.source,
        "field_values": sub.field_values,
        "review_status": sub.review_status,
        "review_report": sub.review_report or None,
        "diff_summary": sub.diff_summary or None,
        "score": sub.score,
        "created_at": sub.created_at,
        "reviewed_at": sub.reviewed_at,
        "candidate_name": sess.candidate_name if sess else None,
        "candidate_email": sess.candidate_email if sess else None,
        "template_name": tmpl.name if tmpl else "(deleted template)",
        "file_type": tmpl.file_type.value if tmpl else "docx",
    }
    return SubmissionDetail.model_validate(payload)


@router.post("/submissions/{submission_id}/review", response_model=SubmissionDetail)
def rerun_submission_review(
    submission_id: str,
    db: Session = Depends(get_db),
    storage: Storage = Depends(get_storage_dep),
) -> SubmissionDetail:
    sub = db.get(Submission, submission_id)
    if sub is None:
        raise NotFoundError("Submission not found.")
    submission_service.rerun_review(db, storage, sub)
    return get_submission(submission_id, db)


@router.get("/submissions/{submission_id}/file")
def download_submission(
    submission_id: str,
    which: str = Query(default="submitted", pattern="^(submitted|original)$"),
    db: Session = Depends(get_db),
    storage: Storage = Depends(get_storage_dep),
) -> StreamingResponse:
    sub = db.get(Submission, submission_id)
    if sub is None:
        raise NotFoundError("Submission not found.")
    tmpl = db.get(Template, sub.template_id)
    if tmpl is None:
        raise NotFoundError("Template not found.")
    if which == "original":
        data = storage.get(tmpl.original_object_key)
        return _file_response(data, tmpl.original_filename, tmpl.file_type)
    data = storage.get(sub.submitted_object_key)
    return _file_response(data, sub.submitted_filename, tmpl.file_type)


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _session_link(session: CandidateSession) -> SessionLinkResponse:
    settings = get_settings()
    base = settings.cors_origin_list[0] if settings.cors_origin_list else ""
    candidate_url = f"{base.rstrip('/')}/c/{session.token}" if base else f"/c/{session.token}"
    data = SessionResponse.model_validate(session).model_dump()
    return SessionLinkResponse(**data, candidate_url=candidate_url)


def _validate_field_spec_targets(template: Template, spec: FieldSpec) -> None:
    from app.models.enums import FileType

    if template.file_type is FileType.xlsx:
        bad = [f.id for f in spec.fields if not (f.sheet and f.cell)]
        if bad:
            raise ValidationError(
                f"Excel fields must specify sheet and cell: {', '.join(bad)}"
            )
    else:
        bad = [f.id for f in spec.fields if not f.placeholder]
        if bad:
            raise ValidationError(
                f"Word fields must specify a placeholder: {', '.join(bad)}"
            )


def _file_response(data: bytes, filename: str, file_type) -> StreamingResponse:
    media = CONTENT_TYPE_BY_FILETYPE.get(file_type, "application/octet-stream")
    # Sanitise the filename to prevent HTTP response header injection and to keep
    # the Content-Disposition value well-formed.
    safe = re.sub(r'[\r\n"]', "", os.path.basename(filename or "download")).strip() or "download"
    headers = {"Content-Disposition": f'attachment; filename="{safe}"'}
    return StreamingResponse(io.BytesIO(data), media_type=media, headers=headers)


def _safe_delete(storage: Storage, key: str) -> None:
    try:
        storage.delete(key)
    except Exception:  # noqa: BLE001 - deletion is best-effort
        pass
