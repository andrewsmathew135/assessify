"""Server-side upload validation.

Security-critical: this is the gate every uploaded file passes through before we
ever parse or store it. It enforces:

* a maximum size,
* that the bytes are a real OOXML (ZIP) package, not just a trusted extension,
* that the *actual* content matches the declared extension (blocks a renamed
  ``.xlsm`` masquerading as ``.docx``),
* that the file contains **no macros** (``.docm``/``.xlsm`` and any embedded
  ``vbaProject.bin`` or macro-enabled content types are rejected),
* that the file is not corrupt (the ZIP central directory is readable and the
  expected primary part exists).
"""
from __future__ import annotations

import io
import zipfile

from app.config import get_settings
from app.core.errors import (
    CorruptFileError,
    FileTooLargeError,
    MacroDetectedError,
    UnsupportedFileTypeError,
)
from app.models.enums import FileType

# OOXML packages are ZIP archives; ZIP local-file / empty-archive signatures.
_ZIP_SIGNATURES = (b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08")

# Extensions that are macro-enabled or otherwise disallowed outright.
_BLOCKED_EXTENSIONS = {".docm", ".xlsm", ".xlsb", ".dotm", ".xltm", ".xlam", ".doc", ".xls"}

_ALLOWED_EXTENSIONS = {".docx": FileType.docx, ".xlsx": FileType.xlsx}

_MACRO_CONTENT_TYPE_MARKERS = (
    b"macroEnabled",
    b"application/vnd.ms-office.vbaProject",
)

CONTENT_TYPE_BY_FILETYPE = {
    FileType.docx: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    FileType.xlsx: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}


def _extension(filename: str) -> str:
    name = (filename or "").lower().strip()
    dot = name.rfind(".")
    return name[dot:] if dot != -1 else ""


def _detect_kind_from_zip(zf: zipfile.ZipFile) -> FileType | None:
    names = set(zf.namelist())
    if "word/document.xml" in names:
        return FileType.docx
    if "xl/workbook.xml" in names:
        return FileType.xlsx
    return None


def _has_macros(zf: zipfile.ZipFile) -> bool:
    for name in zf.namelist():
        base = name.rsplit("/", 1)[-1].lower()
        if base == "vbaproject.bin":
            return True
    # Also inspect the content-types manifest for macro-enabled declarations.
    try:
        manifest = zf.read("[Content_Types].xml")
    except KeyError:
        return False
    return any(marker in manifest for marker in _MACRO_CONTENT_TYPE_MARKERS)


def validate_upload(filename: str, data: bytes) -> FileType:
    """Validate raw uploaded bytes and return the confirmed :class:`FileType`.

    Raises a specific :class:`FileValidationError` subclass on any problem so the
    caller can surface a precise, human-readable message.
    """
    settings = get_settings()

    # 1) Size.
    if len(data) == 0:
        raise CorruptFileError("The uploaded file is empty.")
    if len(data) > settings.max_upload_bytes:
        limit_mb = settings.max_upload_bytes / (1024 * 1024)
        raise FileTooLargeError(f"File exceeds the {limit_mb:.0f} MB size limit.")

    # 2) Extension policy (fast reject before touching the bytes as a zip).
    ext = _extension(filename)
    if ext in _BLOCKED_EXTENSIONS:
        raise MacroDetectedError(
            "Macro-enabled or legacy Office files are not allowed. "
            "Please upload a macro-free .docx or .xlsx file."
        )
    if ext not in _ALLOWED_EXTENSIONS:
        raise UnsupportedFileTypeError(
            "Unsupported file type. Only .docx and .xlsx files are accepted."
        )

    # 3) Magic bytes: must actually be a ZIP/OOXML package.
    if not any(data.startswith(sig) for sig in _ZIP_SIGNATURES):
        raise CorruptFileError("The file is not a valid Office document (bad signature).")

    # 4) Open as zip and inspect structure.
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            bad = zf.testzip()
            if bad is not None:
                raise CorruptFileError(f"The file is corrupt (bad entry: {bad}).")

            if _has_macros(zf):
                raise MacroDetectedError(
                    "This file contains macros, which are not allowed. "
                    "Please remove macros and re-upload."
                )

            actual = _detect_kind_from_zip(zf)
    except zipfile.BadZipFile as exc:
        raise CorruptFileError("The file is corrupt or not a valid Office document.") from exc

    if actual is None:
        raise CorruptFileError("The file is missing its main document part.")

    # 5) Declared extension must match actual content (anti-spoofing).
    declared = _ALLOWED_EXTENSIONS[ext]
    if declared != actual:
        raise UnsupportedFileTypeError(
            f"File contents ({actual.value}) do not match the .{declared.value} extension."
        )

    return actual
