"""Security helpers: password hashing, JWT tokens, unguessable link tokens."""
from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.config import get_settings
from app.core.errors import AuthError

settings = get_settings()

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return _pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return _pwd_context.verify(plain, hashed)
    except ValueError:
        return False


def verify_admin_credentials(email: str, password: str) -> bool:
    """Constant-time comparison for the single configured admin account."""
    email_ok = secrets.compare_digest(email.strip().lower(), settings.admin_email.strip().lower())
    password_ok = secrets.compare_digest(password, settings.admin_password)
    # Evaluate both to avoid short-circuit timing leaks.
    return email_ok and password_ok


def create_access_token(subject: str, expires_minutes: int | None = None) -> str:
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=expires_minutes or settings.jwt_expires_minutes
    )
    payload = {"sub": subject, "exp": expire, "role": "admin"}
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except JWTError as exc:  # expired or tampered
        raise AuthError("Invalid or expired session token.") from exc


def generate_link_token(nbytes: int = 32) -> str:
    """URL-safe, unguessable token used in candidate links."""
    return secrets.token_urlsafe(nbytes)
