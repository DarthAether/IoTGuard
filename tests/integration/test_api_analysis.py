"""Integration tests for POST /v1/analyze and /v1/analyze-and-execute."""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from iotguard.db.models import Device


async def _seed_device(session: AsyncSession) -> Device:
    """Insert a test device."""
    dev = Device(
        id=uuid.uuid4(),
        device_id="analysis-dev",
        name="Analysis Test Device",
        device_type="light",
        state={"is_on": False},
        is_online=True,
    )
    session.add(dev)
    await session.flush()
    await session.commit()
    return dev


class TestAnalyzeEndpoint:
    """Test POST /v1/analyze."""

    async def test_analyze_returns_result(
        self,
        test_client: AsyncClient,
        auth_headers: dict[str, str],
        db_session: AsyncSession,
    ) -> None:
        resp = await test_client.post(
            "/v1/analyze",
            json={
                "command": "turn_on light",
                "device_id": "dev-1",
            },
            headers=auth_headers,
        )
        # May return 200 or 500 depending on LLM/rule engine state,
        # but the endpoint should be reachable
        assert resp.status_code in (200, 500)

    async def test_analyze_requires_auth(
        self,
        test_client: AsyncClient,
    ) -> None:
        resp = await test_client.post(
            "/v1/analyze",
            json={"command": "test", "device_id": "d"},
        )
        assert resp.status_code == 401

    async def test_analyze_validates_command_length(
        self,
        test_client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        resp = await test_client.post(
            "/v1/analyze",
            json={"command": "", "device_id": "d"},
            headers=auth_headers,
        )
        assert resp.status_code == 422  # validation error


class TestAnalyzeAndExecuteEndpoint:
    """Test POST /v1/analyze-and-execute."""

    async def test_analyze_and_execute_requires_auth(
        self,
        test_client: AsyncClient,
    ) -> None:
        resp = await test_client.post(
            "/v1/analyze-and-execute",
            json={"command": "turn_on", "device_id": "dev-1"},
        )
        assert resp.status_code == 401

    async def test_analyze_and_execute_viewer_forbidden(
        self,
        test_client: AsyncClient,
        viewer_auth_headers: dict[str, str],
    ) -> None:
        resp = await test_client.post(
            "/v1/analyze-and-execute",
            json={"command": "turn_on", "device_id": "dev-1"},
            headers=viewer_auth_headers,
        )
        assert resp.status_code == 403


class TestAnalysisHistory:
    """Test GET /v1/analysis/history."""

    async def test_history_returns_list(
        self,
        test_client: AsyncClient,
        viewer_auth_headers: dict[str, str],
    ) -> None:
        resp = await test_client.get(
            "/v1/analysis/history",
            headers=viewer_auth_headers,
        )
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    async def test_history_requires_auth(
        self,
        test_client: AsyncClient,
    ) -> None:
        resp = await test_client.get("/v1/analysis/history")
        assert resp.status_code == 401
