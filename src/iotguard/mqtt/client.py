"""Low-level async MQTT client wrapping paho-mqtt v2.

Handles connection / reconnection, topic subscriptions, publishing, and
message routing to registered handlers.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any, Callable

import paho.mqtt.client as paho_mqtt
import structlog

from iotguard.core.config import MqttSettings
from iotguard.core.exceptions import MqttConnectionError, MqttError

logger = structlog.get_logger(__name__)

MessageHandler = Callable[[str, dict[str, Any]], None]


class MqttClient:
    """Async-friendly wrapper around the paho-mqtt synchronous client.

    The paho network loop runs on a background thread; public methods use
    ``run_in_executor`` where blocking is unavoidable.
    """

    def __init__(self, settings: MqttSettings) -> None:
        self._settings = settings
        self._client: paho_mqtt.Client | None = None
        self._connected = asyncio.Event()
        self._handlers: list[MessageHandler] = []
        self._should_reconnect = True

    # -- properties ---------------------------------------------------------

    @property
    def is_connected(self) -> bool:
        return self._connected.is_set()

    # -- lifecycle ----------------------------------------------------------

    async def connect(self) -> None:
        """Connect to the MQTT broker and start the network loop."""
        if self.is_connected:
            return

        self._client = paho_mqtt.Client(
            callback_api_version=paho_mqtt.CallbackAPIVersion.VERSION2,
            client_id=self._settings.client_id,
        )

        if self._settings.username:
            self._client.username_pw_set(
                self._settings.username,
                self._settings.password.get_secret_value(),
            )

        self._client.on_connect = self._on_connect
        self._client.on_disconnect = self._on_disconnect
        self._client.on_message = self._on_message
        self._client.reconnect_delay_set(min_delay=1, max_delay=60)

        loop = asyncio.get_running_loop()
        try:
            await loop.run_in_executor(
                None,
                self._client.connect,
                self._settings.broker_host,
                self._settings.broker_port,
            )
            self._client.loop_start()
        except Exception as exc:
            raise MqttConnectionError(str(exc)) from exc

        # Wait up to 10 s for the on_connect callback
        try:
            await asyncio.wait_for(self._connected.wait(), timeout=10.0)
        except asyncio.TimeoutError:
            raise MqttConnectionError(
                f"Timeout connecting to {self._settings.broker_host}:{self._settings.broker_port}"
            )

    async def disconnect(self) -> None:
        """Stop the network loop and disconnect cleanly."""
        self._should_reconnect = False
        if self._client is not None:
            self._client.loop_stop()
            self._client.disconnect()
            self._connected.clear()
            logger.info("mqtt_disconnected")

    # -- pub / sub ----------------------------------------------------------

    async def subscribe(self, topic: str, *, qos: int = 1) -> None:
        """Subscribe to *topic*.  Raises if not connected."""
        self._assert_connected()
        assert self._client is not None
        self._client.subscribe(topic, qos=qos)
        logger.info("mqtt_subscribed", topic=topic, qos=qos)

    async def publish(
        self,
        topic: str,
        payload: dict[str, Any],
        *,
        qos: int = 1,
        retain: bool = False,
    ) -> None:
        """Publish a JSON-serialised *payload* to *topic*."""
        self._assert_connected()
        assert self._client is not None
        raw = json.dumps(payload, default=str)
        info = self._client.publish(topic, raw, qos=qos, retain=retain)
        info.wait_for_publish(timeout=5)
        logger.debug("mqtt_published", topic=topic)

    # -- handler registration -----------------------------------------------

    def add_handler(self, handler: MessageHandler) -> None:
        """Register a callback invoked for every incoming message."""
        self._handlers.append(handler)

    def remove_handler(self, handler: MessageHandler) -> None:
        if handler in self._handlers:
            self._handlers.remove(handler)

    # -- internal callbacks -------------------------------------------------

    def _on_connect(
        self,
        client: paho_mqtt.Client,
        userdata: Any,
        flags: Any,
        rc: Any,
        properties: Any = None,
    ) -> None:
        self._connected.set()
        logger.info("mqtt_connected", rc=str(rc))
        # Auto-subscribe to configured topics
        for topic in self._settings.topics:
            client.subscribe(topic, qos=1)
            logger.info("mqtt_auto_subscribed", topic=topic)

    def _on_disconnect(
        self,
        client: paho_mqtt.Client,
        userdata: Any,
        flags: Any,
        rc: Any,
        properties: Any = None,
    ) -> None:
        self._connected.clear()
        if self._should_reconnect:
            logger.warning("mqtt_disconnected_will_reconnect", rc=str(rc))
        else:
            logger.info("mqtt_disconnected_clean", rc=str(rc))

    def _on_message(
        self,
        client: paho_mqtt.Client,
        userdata: Any,
        msg: paho_mqtt.MQTTMessage,
    ) -> None:
        try:
            payload: dict[str, Any] = json.loads(msg.payload.decode())
        except (json.JSONDecodeError, UnicodeDecodeError):
            payload = {"raw": msg.payload.decode(errors="replace")}

        logger.debug("mqtt_message_received", topic=msg.topic)

        for handler in self._handlers:
            try:
                handler(msg.topic, payload)
            except Exception:
                logger.exception("mqtt_handler_error", topic=msg.topic)

    # -- helpers ------------------------------------------------------------

    def _assert_connected(self) -> None:
        if not self.is_connected or self._client is None:
            raise MqttError("Not connected to MQTT broker")
