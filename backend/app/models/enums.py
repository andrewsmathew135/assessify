"""Shared enumerations for statuses and file types."""
from __future__ import annotations

from enum import Enum


class FileType(str, Enum):
    docx = "docx"
    xlsx = "xlsx"


class SessionStatus(str, Enum):
    pending = "pending"      # link created, candidate has not opened it
    opened = "opened"        # candidate viewed the assignment
    submitted = "submitted"  # candidate submitted a file
    expired = "expired"      # link passed its expiry date


class ReviewStatus(str, Enum):
    pending = "pending"            # awaiting/undergoing automated review
    passed = "passed"             # all hard checks passed
    failed = "failed"             # missing required / out-of-range / corrupt / macro
    needs_review = "needs_review"  # parses fine but has soft issues for a human


class SubmissionSource(str, Enum):
    upload = "upload"
    in_browser = "in_browser"
