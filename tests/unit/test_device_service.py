"""Unit tests for the DeviceService -- CRUD, command execution, state simulation."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock

import pytest

from iotguard.core.events import EventBus
from iotguard.core.exceptions import (
    DeviceNotFoundError,
    DeviceOfflineError,
    InsufficientPermissionsError,
)
from iotguard.db.models import Device
from iotguard.devices.service import DeviceService


def _device(
    *,
    device_id: str = "test-dev",
    name: str = "Test Device",
    device_type: str = "generic",
    is_online: bool = True,
    state: dict[str, Any] | None = None,
) -> Device:
    d = Device.__new__(Device)
    d.id = uuid.uuid4()
    d.device_id = device_id
    d.name = name
    d.device_type = device_type
    d.is_online = is_online
    d.state = state or {}
    d.last_seen = datetime.now(UTC)
    d.created_at = datetime.now(UTC)
    d.updated_at = datetime.now(UTC)
    return d


class TestDeviceCRUD:
    """Test list, get, register, and delete operations."""

    async def test_list_devices(self, event_bus: EventBus) -> None:
        mock_session = AsyncMock()
        svc = DeviceService(mock_session, event_bus)
        svc._repo = AsyncMock()
        svc._repo.list_all = AsyncMock(return_value=[_device(), _device()])

        devices = await svc.list_devices()
        assert len(devices) == 2

    async def test_get_device_found(self, event_bus: EventBus) -> None:
        dev = _device()
        mock_session = AsyncMock()
        svc = DeviceService(mock_session, event_bus)
        svc._repo = AsyncMock()
        svc._repo.get_by_id = AsyncMock(return_value=dev)

        result = await svc.get_device(dev.id)
        assert result.device_id == dev.device_id

    async def test_get_device_not_found(self, event_bus: EventBus) -> None:
        mock_session = AsyncMock()
        svc = DeviceService(mock_session, event_bus)
        svc._repo = AsyncMock()
        svc._repo.get_by_id = AsyncMock(return_value=None)

        with pytest.raises(DeviceNotFoundError):
            await svc.get_device(uuid.uuid4())

    async def test_get_by_device_id_not_found(self, event_bus: EventBus) -> None:
        mock_session = AsyncMock()
        svc = DeviceService(mock_session, event_bus)
        svc._repo = AsyncMock()
        svc._repo.get_by_device_id = AsyncMock(return_value=None)

        with pytest.raises(DeviceNotFoundError):
            await svc.get_device_by_device_id("nonexistent")

    async def test_register_device(self, event_bus: EventBus) -> None:
        mock_session = AsyncMock()
        svc = DeviceService(mock_session, event_bus)
        svc._repo = AsyncMock()
        created = _device(device_id="new-dev", name="New Device")
        svc._repo.create = AsyncMock(return_value=created)

        result = await svc.register_device(
            device_id="new-dev",
            name="New Device",
            device_type="light",
        )
        assert result.device_id == "new-dev"

    async def test_delete_device(self, event_bus: EventBus) -> None:
        dev = _device()
        mock_session = AsyncMock()
        svc = DeviceService(mock_session, event_bus)
        svc._repo = AsyncMock()
        svc._repo.get_by_id = AsyncMock(return_value=dev)
        svc._repo.delete = AsyncMock()

        await svc.delete_device(dev.id)
        svc._repo.delete.assert_called_once_with(dev.id)


class TestCommandExecution:
    """Test command execution with state simulation."""

    async def test_execute_on_online_device(self, event_bus: EventBus) -> None:
        dev = _device(is_online=True, state={})
        mock_session = AsyncMock()
        svc = DeviceService(mock_session, event_bus)
        svc._repo = AsyncMock()
        svc._repo.get_by_id = AsyncMock(return_value=dev)
        svc._repo.update_state = AsyncMock()
        svc._perm_repo = AsyncMock()

        result = await svc.execute_command(
            dev.id, "turn_on", user="admin", skip_permission_check=True,
        )
        assert result["command"] == "turn_on"
        assert "executed successfully" in result["result"]

    async def test_execute_on_offline_device_raises(self, event_bus: EventBus) -> None:
        dev = _device(is_online=False)
        mock_session = AsyncMock()
        svc = DeviceService(mock_session, event_bus)
        svc._repo = AsyncMock()
        svc._repo.get_by_id = AsyncMock(return_value=dev)
        svc._perm_repo = AsyncMock()

        with pytest.raises(DeviceOfflineError):
            await svc.execute_command(
                dev.id, "turn_on", skip_permission_check=True,
            )


class TestStateSimulation:
    """Verify _simulate_state_change keyword-based mutations."""

    def test_unlock_sets_is_locked_false(self) -> None:
        new = DeviceService._simulate_state_change("unlock", {"is_locked": True})
        assert new["is_locked"] is False

    def test_lock_sets_is_locked_true(self) -> None:
        new = DeviceService._simulate_state_change("lock", {})
        assert new["is_locked"] is True

    def test_turn_on(self) -> None:
        new = DeviceService._simulate_state_change("turn_on", {"is_on": False})
        assert new["is_on"] is True

    def test_turn_off(self) -> None:
        new = DeviceService._simulate_state_change("turn_off", {"is_on": True})
        assert new["is_on"] is False

    def test_start_recording(self) -> None:
        new = DeviceService._simulate_state_change("start_recording", {})
        assert new["recording"] is True

    def test_stop_recording(self) -> None:
        new = DeviceService._simulate_state_change("stop_recording", {"recording": True})
        assert new["recording"] is False

    def test_set_temperature(self) -> None:
        new = DeviceService._simulate_state_change("set_temperature 22.5", {})
        assert new["temperature"] == 22.5

    def test_set_brightness(self) -> None:
        new = DeviceService._simulate_state_change("set_brightness 75", {})
        assert new["brightness"] == 75

    def test_unknown_command_preserves_state(self) -> None:
        original = {"is_on": True, "temperature": 20.0}
        new = DeviceService._simulate_state_change("do_nothing", original)
        assert new == original


class TestPermissionChecks:
    """Test execute_command permission enforcement."""

    async def test_no_permission_raises(self, event_bus: EventBus) -> None:
        dev = _device(is_online=True)
        user_id = uuid.uuid4()
        mock_session = AsyncMock()
        svc = DeviceService(mock_session, event_bus)
        svc._repo = AsyncMock()
        svc._repo.get_by_id = AsyncMock(return_value=dev)
        svc._perm_repo = AsyncMock()
        svc._perm_repo.check_permission = AsyncMock(return_value=False)

        with pytest.raises(InsufficientPermissionsError):
            await svc.execute_command(
                dev.id, "unlock", user="user", user_id=user_id,
            )

    async def test_skip_permission_check(self, event_bus: EventBus) -> None:
        dev = _device(is_online=True)
        mock_session = AsyncMock()
        svc = DeviceService(mock_session, event_bus)
        svc._repo = AsyncMock()
        svc._repo.get_by_id = AsyncMock(return_value=dev)
        svc._repo.update_state = AsyncMock()
        svc._perm_repo = AsyncMock()

        # Should not raise even without permissions
        result = await svc.execute_command(
            dev.id, "lock", user="system", skip_permission_check=True,
        )
        assert result["command"] == "lock"
