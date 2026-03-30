"""Unit tests for password hashing, JWT tokens, and RBAC matrix."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from pydantic import SecretStr

from iotguard.core.config import JwtSettings
from iotguard.core.exceptions import (
    InsufficientPermissionsError,
    InvalidCredentialsError,
    TokenExpiredError,
)
from iotguard.core.security import (
    PERMISSION_MATRIX,
    Role,
    TokenPayload,
    check_permission,
    create_token_pair,
    decode_token,
    hash_password,
    verify_password,
)


# ---------------------------------------------------------------------------
# Password hashing
# ---------------------------------------------------------------------------


class TestPasswordHashing:
    def test_hash_and_verify(self) -> None:
        hashed = hash_password("secureP@ss123")
        assert verify_password("secureP@ss123", hashed) is True

    def test_wrong_password_fails(self) -> None:
        hashed = hash_password("correct")
        assert verify_password("wrong", hashed) is False

    def test_different_hashes_for_same_password(self) -> None:
        h1 = hash_password("same")
        h2 = hash_password("same")
        assert h1 != h2  # bcrypt uses random salt

    def test_hash_is_bcrypt(self) -> None:
        hashed = hash_password("test")
        assert hashed.startswith("$2b$")

    def test_empty_password_can_be_hashed(self) -> None:
        hashed = hash_password("")
        assert verify_password("", hashed) is True


# ---------------------------------------------------------------------------
# JWT tokens
# ---------------------------------------------------------------------------

_JWT_SETTINGS = JwtSettings(
    secret_key=SecretStr("test-jwt-secret"),
    algorithm="HS256",
    access_token_expire_minutes=15,
    refresh_token_expire_minutes=60,
)


class TestJwtTokenCreation:
    def test_create_token_pair_returns_both_tokens(self) -> None:
        pair = create_token_pair("user-123", Role.ADMIN, _JWT_SETTINGS)
        assert pair.access_token
        assert pair.refresh_token
        assert pair.token_type == "bearer"

    def test_access_token_decodable(self) -> None:
        pair = create_token_pair("user-456", Role.OPERATOR, _JWT_SETTINGS)
        payload = decode_token(pair.access_token, _JWT_SETTINGS)
        assert payload.sub == "user-456"
        assert payload.role == Role.OPERATOR
        assert payload.token_type == "access"

    def test_refresh_token_decodable(self) -> None:
        pair = create_token_pair("user-789", Role.VIEWER, _JWT_SETTINGS)
        payload = decode_token(pair.refresh_token, _JWT_SETTINGS)
        assert payload.sub == "user-789"
        assert payload.role == Role.VIEWER
        assert payload.token_type == "refresh"

    def test_token_has_expiration(self) -> None:
        pair = create_token_pair("u", Role.ADMIN, _JWT_SETTINGS)
        payload = decode_token(pair.access_token, _JWT_SETTINGS)
        assert payload.exp > datetime.now(UTC)


class TestJwtTokenDecoding:
    def test_invalid_token_raises(self) -> None:
        with pytest.raises(InvalidCredentialsError):
            decode_token("not.a.valid.token", _JWT_SETTINGS)

    def test_wrong_secret_raises(self) -> None:
        pair = create_token_pair("u", Role.ADMIN, _JWT_SETTINGS)
        wrong_settings = JwtSettings(secret_key=SecretStr("wrong-secret"))
        with pytest.raises(InvalidCredentialsError):
            decode_token(pair.access_token, wrong_settings)

    def test_expired_token_raises(self) -> None:
        expired_settings = JwtSettings(
            secret_key=_JWT_SETTINGS.secret_key,
            access_token_expire_minutes=0,
        )
        # Token with 0-minute expiry
        pair = create_token_pair("u", Role.ADMIN, expired_settings)
        # Immediately expired due to 0-minute TTL -- the jose library rounds,
        # so we create one with a negative offset manually.
        from jose import jwt as jose_jwt

        payload = {
            "sub": "u",
            "role": "admin",
            "exp": datetime.now(UTC) - timedelta(hours=1),
            "iat": datetime.now(UTC) - timedelta(hours=2),
            "token_type": "access",
        }
        token = jose_jwt.encode(
            payload,
            _JWT_SETTINGS.secret_key.get_secret_value(),
            algorithm="HS256",
        )
        with pytest.raises((TokenExpiredError, InvalidCredentialsError)):
            decode_token(token, _JWT_SETTINGS)


# ---------------------------------------------------------------------------
# RBAC matrix
# ---------------------------------------------------------------------------


class TestRBACMatrix:
    def test_admin_has_all_permissions(self) -> None:
        admin_perms = PERMISSION_MATRIX[Role.ADMIN]
        assert "devices:read" in admin_perms
        assert "devices:write" in admin_perms
        assert "users:write" in admin_perms
        assert "users:delete" in admin_perms
        assert "rules:write" in admin_perms

    def test_operator_has_device_and_analysis_write(self) -> None:
        ops = PERMISSION_MATRIX[Role.OPERATOR]
        assert "devices:write" in ops
        assert "analysis:write" in ops
        assert "users:write" not in ops
        assert "users:delete" not in ops

    def test_viewer_has_read_only(self) -> None:
        viewer = PERMISSION_MATRIX[Role.VIEWER]
        assert "devices:read" in viewer
        assert "analysis:read" in viewer
        assert "devices:write" not in viewer
        assert "analysis:write" not in viewer
        assert "rules:write" not in viewer

    def test_check_permission_passes_for_allowed(self) -> None:
        check_permission(Role.ADMIN, "devices:write")  # should not raise

    def test_check_permission_raises_for_denied(self) -> None:
        with pytest.raises(InsufficientPermissionsError):
            check_permission(Role.VIEWER, "devices:write")

    def test_check_permission_viewer_cannot_write_rules(self) -> None:
        with pytest.raises(InsufficientPermissionsError):
            check_permission(Role.VIEWER, "rules:write")

    def test_check_permission_operator_cannot_delete_users(self) -> None:
        with pytest.raises(InsufficientPermissionsError):
            check_permission(Role.OPERATOR, "users:delete")

    @pytest.mark.parametrize("role", list(Role))
    def test_all_roles_can_read_devices(self, role: Role) -> None:
        check_permission(role, "devices:read")  # should not raise

    @pytest.mark.parametrize("role", list(Role))
    def test_all_roles_can_read_audit(self, role: Role) -> None:
        check_permission(role, "audit:read")  # should not raise
