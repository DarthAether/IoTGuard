"""Integration tests for authentication -- token exchange, invalid creds, role enforcement."""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from iotguard.core.security import Role, create_token_pair, hash_password
from iotguard.db.models import User


async def _create_test_user(
    session: AsyncSession,
    *,
    username: str = "testuser",
    password: str = "testpass123",
    role: str = "admin",
) -> User:
    """Insert a user into the test DB and return it."""
    user = User(
        id=uuid.uuid4(),
        username=username,
        hashed_password=hash_password(password),
        role=role,
        is_active=True,
    )
    session.add(user)
    await session.flush()
    await session.commit()
    return user


class TestTokenExchange:
    """Test POST /auth/token."""

    async def test_valid_credentials_return_tokens(
        self,
        test_client: AsyncClient,
        db_session: AsyncSession,
    ) -> None:
        await _create_test_user(db_session, username="auth_user", password="secret123")

        resp = await test_client.post(
            "/auth/token",
            json={"username": "auth_user", "password": "secret123"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"

    async def test_invalid_password_returns_401(
        self,
        test_client: AsyncClient,
        db_session: AsyncSession,
    ) -> None:
        await _create_test_user(db_session, username="auth_user2", password="correct")

        resp = await test_client.post(
            "/auth/token",
            json={"username": "auth_user2", "password": "wrong"},
        )
        assert resp.status_code == 401

    async def test_nonexistent_user_returns_401(
        self,
        test_client: AsyncClient,
    ) -> None:
        resp = await test_client.post(
            "/auth/token",
            json={"username": "nobody", "password": "x"},
        )
        assert resp.status_code == 401


class TestInvalidCredentials:
    """Test various authentication failures."""

    async def test_missing_auth_header_returns_401(
        self,
        test_client: AsyncClient,
    ) -> None:
        resp = await test_client.get("/v1/devices")
        assert resp.status_code == 401

    async def test_invalid_scheme_returns_401(
        self,
        test_client: AsyncClient,
    ) -> None:
        resp = await test_client.get(
            "/v1/devices",
            headers={"Authorization": "Basic dXNlcjpwYXNz"},
        )
        assert resp.status_code == 401

    async def test_malformed_token_returns_401(
        self,
        test_client: AsyncClient,
    ) -> None:
        resp = await test_client.get(
            "/v1/devices",
            headers={"Authorization": "Bearer not.a.valid.jwt.token"},
        )
        assert resp.status_code == 401


class TestRoleEnforcement:
    """Test that endpoints enforce role requirements."""

    async def test_viewer_can_list_devices(
        self,
        test_client: AsyncClient,
        viewer_auth_headers: dict[str, str],
    ) -> None:
        resp = await test_client.get("/v1/devices", headers=viewer_auth_headers)
        assert resp.status_code == 200

    async def test_viewer_cannot_create_device(
        self,
        test_client: AsyncClient,
        viewer_auth_headers: dict[str, str],
    ) -> None:
        resp = await test_client.post(
            "/v1/devices",
            json={
                "device_id": "new-dev",
                "name": "New",
                "device_type": "generic",
            },
            headers=viewer_auth_headers,
        )
        assert resp.status_code == 403

    async def test_admin_can_create_device(
        self,
        test_client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        resp = await test_client.post(
            "/v1/devices",
            json={
                "device_id": "admin-dev",
                "name": "Admin Device",
                "device_type": "light",
            },
            headers=auth_headers,
        )
        assert resp.status_code == 201

    async def test_viewer_cannot_analyze_commands(
        self,
        test_client: AsyncClient,
        viewer_auth_headers: dict[str, str],
    ) -> None:
        resp = await test_client.post(
            "/v1/analyze",
            json={"command": "turn_on", "device_id": "dev-1"},
            headers=viewer_auth_headers,
        )
        assert resp.status_code == 403
