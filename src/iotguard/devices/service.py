"""Device management and command execution service.

Manages the device registry, executes commands (after analysis approval),
simulates device state changes, and publishes domain events.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from iotguard.core.events import CommandExecutedEvent, DeviceStatusEvent, EventBus
from iotguard.core.exceptions import (
    DeviceNotFoundError,
    DeviceOfflineError,
    InsufficientPermissionsError,
)
from iotguard.db.models import Device
from iotguard.db.repositories import DeviceRepository, PermissionRepository

logger = structlog.get_logger(__name__)

# Simple simulation rules: command keyword -> state mutation
_STATE_EFFECTS: dict[str, dict[str, Any]] = {
    "unlock": {"is_locked": False},
    "lock": {"is_locked": True},
    "turn_on": {"is_on": True},
    "turn_off": {"is_on": False},
    "open": {"is_locked": False},
    "close": {"is_locked": True},
    "start_recording": {"recording": True},
    "stop_recording": {"recording": False},
}


class DeviceService:
    """High-level device operations backed by the async repository."""

    def __init__(self, session: AsyncSession, event_bus: EventBus) -> None:
        self._session = session
        self._event_bus = event_bus
        self._repo = DeviceRepository(session)
        self._perm_repo = PermissionRepository(session)

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    async def list_devices(
        self, *, offset: int = 0, limit: int = 50
    ) -> list[Device]:
        return list(await self._repo.list_all(offset=offset, limit=limit))

    async def get_device(self, device_pk: uuid.UUID) -> Device:
        device = await self._repo.get_by_id(device_pk)
        if device is None:
            raise DeviceNotFoundError(str(device_pk))
        return device

    async def get_device_by_device_id(self, device_id: str) -> Device:
        device = await self._repo.get_by_device_id(device_id)
        if device is None:
            raise DeviceNotFoundError(device_id)
        return device

    async def register_device(
        self,
        *,
        device_id: str,
        name: str,
        device_type: str,
        state: dict[str, Any] | None = None,
    ) -> Device:
        device = Device(
            device_id=device_id,
            name=name,
            device_type=device_type,
            state=state or {},
            is_online=True,
            last_seen=datetime.now(UTC),
        )
        device = await self._repo.create(device)
        logger.info(
            "device_registered",
            device_pk=str(device.id),
            device_id=device_id,
            name=name,
        )
        return device

    async def update_device_state(
        self, device_pk: uuid.UUID, state: dict[str, Any]
    ) -> Device:
        device = await self.get_device(device_pk)
        merged = {**(device.state or {}), **state}
        await self._repo.update_state(device_pk, merged)
        await self._session.refresh(device)
        return device

    async def set_online_status(
        self, device_pk: uuid.UUID, *, is_online: bool
    ) -> None:
        await self._repo.update_online_status(
            device_pk,
            is_online=is_online,
            last_seen=datetime.now(UTC) if is_online else None,
        )
        device = await self.get_device(device_pk)
        status = "online" if is_online else "offline"
        self._event_bus.publish_nowait(
            DeviceStatusEvent(device_id=device.device_id, status=status)
        )
        logger.info(
            "device_status_changed",
            device_id=device.device_id,
            status=status,
        )

    async def delete_device(self, device_pk: uuid.UUID) -> None:
        await self.get_device(device_pk)  # ensure exists
        await self._repo.delete(device_pk)
        logger.info("device_deleted", device_pk=str(device_pk))

    # ------------------------------------------------------------------
    # Command execution (post-analysis)
    # ------------------------------------------------------------------

    async def execute_command(
        self,
        device_pk: uuid.UUID,
        command: str,
        *,
        user: str = "system",
        user_id: uuid.UUID | None = None,
        skip_permission_check: bool = False,
    ) -> dict[str, Any]:
        """Execute a pre-approved command on a device.

        In a real deployment this would dispatch via MQTT/gRPC; here we
        simulate the state change.
        """
        device = await self.get_device(device_pk)

        if not device.is_online:
            raise DeviceOfflineError(device.device_id)

        # Permission check
        if not skip_permission_check and user_id is not None:
            has_perm = await self._perm_repo.check_permission(
                user_id, device_pk, action="execute"
            )
            if not has_perm:
                raise InsufficientPermissionsError(
                    f"User lacks 'execute' permission on device '{device.device_id}'"
                )

        # Simulate state mutation
        new_state = self._simulate_state_change(command, device.state or {})
        if new_state != device.state:
            await self._repo.update_state(device_pk, new_state)

        result_text = (
            f"Command '{command}' executed successfully on {device.name}"
        )
        logger.info(
            "command_executed",
            device_id=device.device_id,
            command=command,
            user=user,
        )

        self._event_bus.publish_nowait(
            CommandExecutedEvent(
                device_id=device.device_id,
                command=command,
                user=user,
                result=result_text,
            )
        )
        self._event_bus.publish_nowait(
            DeviceStatusEvent(
                device_id=device.device_id,
                status="online",
                metadata={"last_command": command},
            )
        )

        return {
            "device_id": device.device_id,
            "command": command,
            "result": result_text,
            "state": new_state,
        }

    # ------------------------------------------------------------------
    # Simulation helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _simulate_state_change(
        command: str,
        current_state: dict[str, Any],
    ) -> dict[str, Any]:
        """Apply simple keyword-based state mutations."""
        new_state = dict(current_state)
        cmd_lower = command.lower().strip()

        for keyword, effect in _STATE_EFFECTS.items():
            if keyword in cmd_lower:
                new_state.update(effect)

        # Handle set_temperature / set_brightness patterns
        if "set_temperature" in cmd_lower:
            parts = cmd_lower.split()
            for i, p in enumerate(parts):
                if p == "set_temperature" and i + 1 < len(parts):
                    try:
                        new_state["temperature"] = float(parts[i + 1])
                    except ValueError:
                        pass

        if "set_brightness" in cmd_lower:
            parts = cmd_lower.split()
            for i, p in enumerate(parts):
                if p == "set_brightness" and i + 1 < len(parts):
                    try:
                        new_state["brightness"] = int(parts[i + 1])
                    except ValueError:
                        pass

        return new_state
