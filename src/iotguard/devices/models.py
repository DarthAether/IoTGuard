"""Pydantic models for the device layer."""

from __future__ import annotations

import enum
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class DeviceType(str, enum.Enum):
    """Supported IoT device types."""

    DOOR_LOCK = "door_lock"
    CAMERA = "camera"
    SPEAKER = "speaker"
    THERMOSTAT = "thermostat"
    LIGHT = "light"
    GENERIC = "generic"


class DeviceState(BaseModel):
    """Flexible device state snapshot.

    Common fields are declared explicitly; anything else is captured via
    the ``extra`` dict so that new device types can evolve without schema
    changes.
    """

    is_locked: bool | None = None
    is_on: bool | None = None
    temperature: float | None = None
    brightness: int | None = None
    volume: int | None = None
    recording: bool | None = None
    extra: dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# API-facing models
# ---------------------------------------------------------------------------


class DeviceInfo(BaseModel):
    """Read-only device representation returned by the API."""

    id: str
    device_id: str
    name: str
    device_type: DeviceType
    state: dict[str, Any] = Field(default_factory=dict)
    is_online: bool = True
    last_seen: datetime | None = None
    created_at: datetime | None = None


class DeviceCreateRequest(BaseModel):
    """Payload for registering a new device."""

    device_id: str = Field(..., min_length=1, max_length=128)
    name: str = Field(..., min_length=1, max_length=256)
    device_type: DeviceType = DeviceType.GENERIC
    state: dict[str, Any] = Field(default_factory=dict)


class DeviceCommandRequest(BaseModel):
    """Payload for sending a command to a device."""

    command: str = Field(..., min_length=1, max_length=4096)
    parameters: dict[str, Any] = Field(default_factory=dict)
