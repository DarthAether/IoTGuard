"""Integration tests for Device CRUD endpoints."""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from iotguard.db.models import Device


class TestDeviceList:
    """Test GET /v1/devices."""

    async def test_list_empty(
        self,
        test_client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        resp = await test_client.get("/v1/devices", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_list_with_devices(
        self,
        test_client: AsyncClient,
        auth_headers: dict[str, str],
        db_session: AsyncSession,
    ) -> None:
        dev = Device(
            id=uuid.uuid4(),
            device_id="list-dev-1",
            name="List Dev",
            device_type="light",
            state={},
            is_online=True,
        )
        db_session.add(dev)
        await db_session.commit()

        resp = await test_client.get("/v1/devices", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 1


class TestDeviceCreate:
    """Test POST /v1/devices."""

    async def test_create_device(
        self,
        test_client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        resp = await test_client.post(
            "/v1/devices",
            json={
                "device_id": "new-device-001",
                "name": "New Smart Light",
                "device_type": "light",
                "state": {"is_on": False},
            },
            headers=auth_headers,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["device_id"] == "new-device-001"
        assert data["name"] == "New Smart Light"
        assert data["is_online"] is True

    async def test_create_device_minimal(
        self,
        test_client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        resp = await test_client.post(
            "/v1/devices",
            json={
                "device_id": "minimal-dev",
                "name": "Minimal",
                "device_type": "generic",
            },
            headers=auth_headers,
        )
        assert resp.status_code == 201

    async def test_create_device_validation_error(
        self,
        test_client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        resp = await test_client.post(
            "/v1/devices",
            json={"device_id": "", "name": "", "device_type": ""},
            headers=auth_headers,
        )
        assert resp.status_code == 422


class TestDeviceGet:
    """Test GET /v1/devices/{id}."""

    async def test_get_device(
        self,
        test_client: AsyncClient,
        auth_headers: dict[str, str],
        db_session: AsyncSession,
    ) -> None:
        dev = Device(
            id=uuid.uuid4(),
            device_id="get-dev",
            name="Get Test",
            device_type="camera",
            state={},
            is_online=True,
        )
        db_session.add(dev)
        await db_session.commit()

        resp = await test_client.get(
            f"/v1/devices/{dev.id}",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["device_id"] == "get-dev"

    async def test_get_nonexistent_device(
        self,
        test_client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        fake_id = uuid.uuid4()
        resp = await test_client.get(
            f"/v1/devices/{fake_id}",
            headers=auth_headers,
        )
        assert resp.status_code in (404, 500)


class TestDeviceDelete:
    """Test DELETE /v1/devices/{id}."""

    async def test_delete_device(
        self,
        test_client: AsyncClient,
        auth_headers: dict[str, str],
        db_session: AsyncSession,
    ) -> None:
        dev = Device(
            id=uuid.uuid4(),
            device_id="delete-dev",
            name="Delete Test",
            device_type="generic",
            state={},
            is_online=True,
        )
        db_session.add(dev)
        await db_session.commit()

        resp = await test_client.delete(
            f"/v1/devices/{dev.id}",
            headers=auth_headers,
        )
        assert resp.status_code == 204

    async def test_delete_nonexistent_device(
        self,
        test_client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        fake_id = uuid.uuid4()
        resp = await test_client.delete(
            f"/v1/devices/{fake_id}",
            headers=auth_headers,
        )
        assert resp.status_code in (404, 500)
