"""Admin authentication endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import get_current_admin
from app.config import get_settings
from app.core.errors import AuthError
from app.core.security import create_access_token, verify_admin_credentials
from app.schemas.auth import AdminInfo, LoginRequest, TokenResponse

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest) -> TokenResponse:
    if not verify_admin_credentials(body.email, body.password):
        # Deliberately vague to avoid leaking which part was wrong.
        raise AuthError("Invalid email or password.")
    settings = get_settings()
    token = create_access_token(subject=body.email.lower())
    return TokenResponse(access_token=token, expires_in_minutes=settings.jwt_expires_minutes)


@router.get("/me", response_model=AdminInfo)
def me(admin: AdminInfo = Depends(get_current_admin)) -> AdminInfo:
    return admin
