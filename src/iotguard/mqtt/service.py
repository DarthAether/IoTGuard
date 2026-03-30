"""High-level MQTT service bridging the broker to the device layer.

:class:`MqttService` owns the :class:`MqttClient` lifecycle and translates
incoming MQTT messages into device-service calls (and vice-versa).
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from iotguard.core.config import MqttSettings
from iotguard.core.events import DeviceStatusEvent, EventBus
from iotguard.devices.service import DeviceService
from iotguard.mqtt.client import MqttClient

logger = structlog.get_logger(__name__)

# Topic conventions:
#   iotguard/devices/{device_id}/status   -- device publishes status
#   iotguard/commands/{device_id}         -- server publishes commands
#   iotguard/status/{device_id}           -- server publishes state changes


class MqttService:
    """Manage the MQTT lifecycle and bridge messages to/from the device layer."""

    def __init__(
        self,
        settings: MqttSettings,
        session_factory: async_sessionmaker[AsyncSession],
        event_bus: EventBus,
    ) -> None:
        self._settings = settings
        self._session_factory = session_factory
        self._event_bus = event_bus
        self._client = MqttClient(settings)
        self._running = False

    # -- properties ---------------------------------------------------------

    @property
    def is_connected(self) -> bool:
        return self._client.is_connected

    # -- lifecycle ----------------------------------------------------------

    async def start(self) -> None:
        """Connect the MQTT client and register the message router."""
        if self._running:
            return
        self._client.add_handler(self._route_message)
        await self._client.connect()
        self._running = True
        logger.info("mqtt_service_started")

    async def stop(self) -> None:
        """Disconnect the MQTT client."""
        if not self._running:
            return
        self._client.remove_handler(self._route_message)
        await self._client.disconnect()
        self._running = False
        logger.info("mqtt_service_stopped")

    # -- public helpers -----------------------------------------------------

    async def publish_command(
        self, device_id: str, command: str, **kwargs: Any
    ) -> None:
        """Publish a command to a device topic."""
        topic = f"iotguard/commands/{device_id}"
        payload = {"command": command, **kwargs}
        await self._client.publish(topic, payload)

    async def publish_device_status(
        self, device_id: str, status: dict[str, Any]
    ) -> None:
        """Publish a device status update."""
        topic = f"iotguard/status/{device_id}"
        await self._client.publish(topic, status, retain=True)

    def status(self) -> dict[str, Any]:
        """Return a health summary for the MQTT subsystem."""
        return {
            "connected": self._client.is_connected,
            "broker_host": self._settings.broker_host,
            "broker_port": self._settings.broker_port,
            "client_id": self._settings.client_id,
            "running": self._running,
        }

    # -- message routing (runs on paho's background thread) -----------------

    def _route_message(self, topic: str, payload: dict[str, Any]) -> None:
        """Dispatch an incoming MQTT message to the appropriate handler.

        Since paho callbacks are synchronous but our services are async, we
        schedule a coroutine on the running event loop.
        """
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            logger.warning("mqtt_no_event_loop", topic=topic)
            return

        if "/devices/" in topic and topic.endswith("/status"):
            loop.create_task(self._handle_device_status(topic, payload))
        elif "/commands/" in topic:
            loop.create_task(self._handle_command_response(topic, payload))
        else:
            logger.debug("mqtt_unrouted_message", topic=topic)

    async def _handle_device_status(
        self, topic: str, payload: dict[str, Any]
    ) -> None:
        """Process a status message from a device."""
        parts = topic.split("/")
        if len(parts) < 3:
            return
        device_id = parts[2]

        is_online = payload.get("online", True)
        logger.info(
            "mqtt_device_status",
            device_id=device_id,
            online=is_online,
        )

        try:
            async with self._session_factory() as session:
                svc = DeviceService(session, self._event_bus)
                device = await svc.get_device_by_device_id(device_id)
                await svc.set_online_status(device.id, is_online=is_online)
                if "state" in payload:
                    await svc.update_device_state(device.id, payload["state"])
                await session.commit()
        except Exception:
            logger.exception("mqtt_device_status_error", device_id=device_id)

        self._event_bus.publish_nowait(
            DeviceStatusEvent(
                device_id=device_id,
                status="online" if is_online else "offline",
                metadata=payload,
            )
        )

    async def _handle_command_response(
        self, topic: str, payload: dict[str, Any]
    ) -> None:
        """Process a command acknowledgement from a device."""
        parts = topic.split("/")
        if len(parts) < 3:
            return
        device_id = parts[2]
        logger.info(
            "mqtt_command_response",
            device_id=device_id,
            result=payload.get("result", "unknown"),
        )
