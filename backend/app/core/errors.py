"""Domain-specific exceptions.

These carry a machine-readable ``code`` and a human-readable ``message`` so the
global exception handlers can always return clean JSON, never a raw stack trace.
"""
from __future__ import annotations


class AppError(Exception):
    """Base class for all handled application errors."""

    status_code: int = 400
    code: str = "app_error"

    def __init__(self, message: str, *, code: str | None = None, details: dict | None = None):
        super().__init__(message)
        self.message = message
        if code:
            self.code = code
        self.details = details or {}


class ValidationError(AppError):
    status_code = 422
    code = "validation_error"


class FileValidationError(AppError):
    """Raised when an uploaded file fails safety/format validation."""

    status_code = 422
    code = "file_validation_error"


class FileTooLargeError(FileValidationError):
    status_code = 413
    code = "file_too_large"


class UnsupportedFileTypeError(FileValidationError):
    code = "unsupported_file_type"


class MacroDetectedError(FileValidationError):
    code = "macro_detected"


class CorruptFileError(FileValidationError):
    code = "corrupt_file"


class NotFoundError(AppError):
    status_code = 404
    code = "not_found"


class AuthError(AppError):
    status_code = 401
    code = "unauthorized"


class ForbiddenError(AppError):
    status_code = 403
    code = "forbidden"


class ConflictError(AppError):
    status_code = 409
    code = "conflict"


class StorageError(AppError):
    status_code = 502
    code = "storage_error"
