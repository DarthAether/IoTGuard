"""Integration tests for /health and /ready endpoints."""

from __future__ import annotations

import pytest
from httpx import AsyncClient


class TestHealthEndpoint:
    """Test the /health liveness probe."""

    async def test_health_returns_200(self, test_client: AsyncClient) -> None:
        resp = await test_client.get("/health")
        assert resp.status_code == 200

    async def test_health_returns_healthy_status(self, test_client: AsyncClient) -> None:
        resp = await test_client.get("/health")
        data = resp.json()
        assert data["status"] == "healthy"


class TestReadyEndpoint:
    """Test the /ready readiness probe."""

    async def test_ready_returns_200(self, test_client: AsyncClient) -> None:
        resp = await test_client.get("/ready")
        # May return 200 with degraded status since we're using SQLite/no Redis
        assert resp.status_code == 200

    async def test_ready_has_components(self, test_client: AsyncClient) -> None:
        resp = await test_client.get("/ready")
        data = resp.json()
        assert "status" in data


class TestStartupEndpoint:
    """Test the /startup comprehensive probe."""

    async def test_startup_returns_200(self, test_client: AsyncClient) -> None:
        resp = await test_client.get("/startup")
        assert resp.status_code == 200

    async def test_startup_has_status(self, test_client: AsyncClient) -> None:
        resp = await test_client.get("/startup")
        data = resp.json()
        assert "status" in data
