"""Authentication helpers -- JWT creation / verification, password hashing, RBAC.

The permission matrix maps each :class:`Role` to a set of permission strings
using the ``resource:action`` convention.  API endpoints declare which
permission they require; :func:`check_permission` enforces it.
"""

from __future__ import annotations

import enum
from datetime import UTC, datetime, timedelta
from typing import Any

from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel

from iotguard.core.config import JwtSettings
from iotguard.core.exceptions import (
    InsufficientPermissionsError,
    InvalidCredentialsError,
    TokenExpiredError,
)

# ---------------------------------------------------------------------------
# Role enum
# ---------------------------------------------------------------------------


class Role(str, enum.Enum):
    ADMIN = "admin"
    OPERATOR = "operator"
    VIEWER = "viewer"


# ---------------------------------------------------------------------------
# Permission matrix
# ---------------------------------------------------------------------------

PERMISSION_MATRIX: dict[Role, frozenset[str]] = {
    Role.ADMIN: frozenset(
        {
            "devices:read",
            "devices:write",
            "analysis:read",
            "analysis:write",
            "rules:read",
            "rules:write",
            "users:read",
            "users:write",
            "users:delete",
            "mqtt:read",
            "mqtt:write",
            "audit:read",
        }
    ),
    Role.OPERATOR: frozenset(
        {
            "devices:read",
            "devices:write",
            "analysis:read",
            "analysis:write",
            "rules:read",
            "mqtt:read",
            "mqtt:write",
            "audit:read",
        }
    ),
    Role.VIEWER: frozenset(
        {
            "devices:read",
            "analysis:read",
            "rules:read",
            "audit:read",
        }
    ),
}

# ---------------------------------------------------------------------------
# Password hashing
# ---------------------------------------------------------------------------

_pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    """Return a bcrypt hash of *password*."""
    return _pwd_ctx.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    """Check *plain* against a bcrypt *hashed* value."""
    return _pwd_ctx.verify(plain, hashed)


# ---------------------------------------------------------------------------
# JWT helpers
# ---------------------------------------------------------------------------


class TokenPayload(BaseModel):
    """Decoded JWT claims."""

    sub: str
    role: Role
    exp: datetime
    token_type: str = "access"


class TokenPair(BaseModel):
    """An access + refresh token pair returned on login."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"


def _encode(payload: dict[str, Any], settings: JwtSettings) -> str:
    return jwt.encode(
        payload,
        settings.secret_key.get_secret_value(),
        algorithm=settings.algorithm,
    )


def create_token_pair(
    subject: str,
    role: Role,
    settings: JwtSettings,
    extra: dict[str, Any] | None = None,
) -> TokenPair:
    """Create both an access and a refresh token."""
    now = datetime.now(UTC)

    access_payload: dict[str, Any] = {
        "sub": subject,
        "role": role.value,
        "exp": now + timedelta(minutes=settings.access_token_expire_minutes),
        "iat": now,
        "token_type": "access",
    }
    if extra:
        access_payload.update(extra)

    refresh_payload: dict[str, Any] = {
        "sub": subject,
        "role": role.value,
        "exp": now + timedelta(minutes=settings.refresh_token_expire_minutes),
        "iat": now,
        "token_type": "refresh",
    }

    return TokenPair(
        access_token=_encode(access_payload, settings),
        refresh_token=_encode(refresh_payload, settings),
    )


def decode_token(token: str, settings: JwtSettings) -> TokenPayload:
    """Decode and validate a JWT, returning structured claims.

    Raises :class:`InvalidCredentialsError` on malformed tokens and
    :class:`TokenExpiredError` when the ``exp`` claim is in the past.
    """
    try:
        raw = jwt.decode(
            token,
            settings.secret_key.get_secret_value(),
            algorithms=[settings.algorithm],
        )
        return TokenPayload(
            sub=raw["sub"],
            role=Role(raw["role"]),
            exp=datetime.fromtimestamp(raw["exp"], tz=UTC),
            token_type=raw.get("token_type", "access"),
        )
    except JWTError as exc:
        msg = str(exc)
        if "expired" in msg.lower():
            raise TokenExpiredError() from exc
        raise InvalidCredentialsError(f"Token validation failed: {exc}") from exc


# ---------------------------------------------------------------------------
# Authorisation
# ---------------------------------------------------------------------------


def check_permission(role: Role, required_permission: str) -> None:
    """Raise :class:`InsufficientPermissionsError` when *role* lacks *required_permission*.

    Parameters
    ----------
    role:
        The authenticated user's role.
    required_permission:
        A ``resource:action`` string, e.g. ``"devices:write"``.
    """
    allowed = PERMISSION_MATRIX.get(role, frozenset())
    if required_permission not in allowed:
        raise InsufficientPermissionsError(
            f"Role '{role.value}' does not have '{required_permission}' permission"
        )
