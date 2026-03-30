"""Authentication endpoints -- token issuance and refresh."""

from __future__ import annotations

from pydantic import BaseModel
from fastapi import APIRouter, HTTPException, status

from iotguard.api.dependencies import DbSession, SettingsDep
from iotguard.core.security import (
    Role,
    TokenPayload,
    create_token_pair,
    decode_token,
    verify_password,
)
from iotguard.db.repositories import UserRepository

router = APIRouter(prefix="/auth", tags=["auth"])


# ---------------------------------------------------------------------------
# Request / response schemas
# ---------------------------------------------------------------------------


class TokenRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/token", response_model=TokenResponse)
async def login(
    body: TokenRequest,
    session: DbSession,
    settings: SettingsDep,
) -> TokenResponse:
    """Exchange credentials for an access + refresh token pair."""
    repo = UserRepository(session)
    user = await repo.get_by_username(body.username)
    if user is None or not verify_password(body.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account deactivated",
        )

    pair = create_token_pair(str(user.id), Role(user.role), settings.jwt)
    return TokenResponse(
        access_token=pair.access_token,
        refresh_token=pair.refresh_token,
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    body: RefreshRequest,
    session: DbSession,
    settings: SettingsDep,
) -> TokenResponse:
    """Exchange a valid refresh token for a new token pair."""
    try:
        payload: TokenPayload = decode_token(body.refresh_token, settings.jwt)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
        ) from exc

    if payload.token_type != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Expected a refresh token",
        )

    # Verify user still exists and is active
    repo = UserRepository(session)
    user = await repo.get_by_id(__import__("uuid").UUID(payload.sub))
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User no longer valid",
        )

    pair = create_token_pair(payload.sub, payload.role, settings.jwt)
    return TokenResponse(
        access_token=pair.access_token,
        refresh_token=pair.refresh_token,
    )
