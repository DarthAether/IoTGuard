"""MQTT management endpoints."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel
from fastapi import APIRouter

from iotguard.api.dependencies import MqttServiceDep, OperatorUser, ViewerUser

router = APIRouter(prefix="/v1/mqtt", tags=["mqtt"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class PublishRequest(BaseModel):
    topic: str
    payload: dict[str, Any]


class MqttStatusResponse(BaseModel):
    connected: bool
    broker_host: str
    broker_port: int
    client_id: str
    running: bool = False


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/status", response_model=MqttStatusResponse)
async def mqtt_status(
    user: ViewerUser,
    mqtt: MqttServiceDep,
) -> MqttStatusResponse:
    raw = mqtt.status()
    return MqttStatusResponse(**raw)


@router.post("/connect", status_code=204)
async def mqtt_connect(
    user: OperatorUser,
    mqtt: MqttServiceDep,
) -> None:
    await mqtt.start()


@router.post("/disconnect", status_code=204)
async def mqtt_disconnect(
    user: OperatorUser,
    mqtt: MqttServiceDep,
) -> None:
    await mqtt.stop()


@router.post("/publish", status_code=204)
async def mqtt_publish(
    body: PublishRequest,
    user: OperatorUser,
    mqtt: MqttServiceDep,
) -> None:
    await mqtt._client.publish(body.topic, body.payload)
