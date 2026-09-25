"""Shared FastAPI dependencies: DB session, storage, and admin authentication."""
from __future__ import annotations

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.errors import AuthError, ForbiddenError
from app.core.security import decode_access_token
from app.config import get_settings
from app.database import get_db
from app.schemas.auth import AdminInfo
from app.services.storage import Storage, get_storage

_bearer = HTTPBearer(auto_error=False)


def get_storage_dep() -> Storage:
    return get_storage()


def get_current_admin(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> AdminInfo:
    settings = get_settings()
    # Open mode: skip authentication entirely (local/demo use).
    if not settings.auth_enabled:
        return AdminInfo(email=settings.admin_email)
    if creds is None or not creds.credentials:
        raise AuthError("Authentication required. Please sign in.")
    payload = decode_access_token(creds.credentials)
    if payload.get("role") != "admin":
        raise ForbiddenError("You do not have access to this resource.")
    subject = payload.get("sub")
    if not subject:
        raise AuthError("Invalid session token.")
    return AdminInfo(email=subject)


__all__ = ["get_db", "get_current_admin", "get_storage_dep", "Session"]
