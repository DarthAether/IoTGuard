"""Device management endpoints."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field
from fastapi import APIRouter

from iotguard.api.dependencies import (
    DeviceServiceDep,
    OperatorUser,
    ViewerUser,
)

router = APIRouter(prefix="/v1/devices", tags=["devices"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class DeviceOut(BaseModel):
    id: str
    device_id: str
    name: str
    device_type: str
    is_online: bool
    state: dict[str, Any]
    last_seen: datetime | None = None
    created_at: datetime

    class Config:
        from_attributes = True


class DeviceCreate(BaseModel):
    device_id: str = Field(..., min_length=1, max_length=128)
    name: str = Field(..., min_length=1, max_length=256)
    device_type: str = Field(..., min_length=1, max_length=64)
    state: dict[str, Any] = Field(default_factory=dict)


class DeviceUpdate(BaseModel):
    name: str | None = None
    device_type: str | None = None
    is_online: bool | None = None
    state: dict[str, Any] | None = None


class CommandRequest(BaseModel):
    command: str


class DeviceStatusOut(BaseModel):
    id: str
    device_id: str
    name: str
    device_type: str
    is_online: bool
    state: dict[str, Any]
    last_seen: str | None = None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("", response_model=list[DeviceOut])
async def list_devices(
    user: ViewerUser,
    device_svc: DeviceServiceDep,
    offset: int = 0,
    limit: int = 50,
) -> list[DeviceOut]:
    devices = await device_svc.list_devices(offset=offset, limit=limit)
    return [
        DeviceOut(
            id=str(d.id),
            device_id=d.device_id,
            name=d.name,
            device_type=d.device_type,
            is_online=d.is_online,
            state=d.state,
            last_seen=d.last_seen,
            created_at=d.created_at,
        )
        for d in devices
    ]


@router.post("", response_model=DeviceOut, status_code=201)
async def register_device(
    body: DeviceCreate,
    user: OperatorUser,
    device_svc: DeviceServiceDep,
) -> DeviceOut:
    device = await device_svc.register_device(
        device_id=body.device_id,
        name=body.name,
        device_type=body.device_type,
        state=body.state,
    )
    return DeviceOut(
        id=str(device.id),
        device_id=device.device_id,
        name=device.name,
        device_type=device.device_type,
        is_online=device.is_online,
        state=device.state,
        last_seen=device.last_seen,
        created_at=device.created_at,
    )


@router.get("/{device_id}", response_model=DeviceOut)
async def get_device(
    device_id: uuid.UUID,
    user: ViewerUser,
    device_svc: DeviceServiceDep,
) -> DeviceOut:
    d = await device_svc.get_device(device_id)
    return DeviceOut(
        id=str(d.id),
        device_id=d.device_id,
        name=d.name,
        device_type=d.device_type,
        is_online=d.is_online,
        state=d.state,
        last_seen=d.last_seen,
        created_at=d.created_at,
    )


@router.patch("/{device_id}", response_model=DeviceOut)
async def update_device(
    device_id: uuid.UUID,
    body: DeviceUpdate,
    user: OperatorUser,
    device_svc: DeviceServiceDep,
) -> DeviceOut:
    if body.state is not None:
        d = await device_svc.update_device_state(device_id, body.state)
    else:
        d = await device_svc.get_device(device_id)
    if body.is_online is not None:
        await device_svc.set_online_status(device_id, is_online=body.is_online)
        await device_svc._session.refresh(d)
    return DeviceOut(
        id=str(d.id),
        device_id=d.device_id,
        name=d.name,
        device_type=d.device_type,
        is_online=d.is_online,
        state=d.state,
        last_seen=d.last_seen,
        created_at=d.created_at,
    )


@router.delete("/{device_id}", status_code=204)
async def delete_device(
    device_id: uuid.UUID,
    user: OperatorUser,
    device_svc: DeviceServiceDep,
) -> None:
    await device_svc.delete_device(device_id)


@router.post("/{device_id}/command")
async def execute_command(
    device_id: uuid.UUID,
    body: CommandRequest,
    user: OperatorUser,
    device_svc: DeviceServiceDep,
) -> dict[str, Any]:
    return await device_svc.execute_command(
        device_id, body.command, user=user.sub, user_id=uuid.UUID(user.sub),
    )


@router.get("/{device_id}/status", response_model=DeviceStatusOut)
async def device_status(
    device_id: uuid.UUID,
    user: ViewerUser,
    device_svc: DeviceServiceDep,
) -> DeviceStatusOut:
    d = await device_svc.get_device(device_id)
    return DeviceStatusOut(
        id=str(d.id),
        device_id=d.device_id,
        name=d.name,
        device_type=d.device_type,
        is_online=d.is_online,
        state=d.state,
        last_seen=d.last_seen.isoformat() if d.last_seen else None,
    )
