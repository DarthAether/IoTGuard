"""Unit tests for the MqttClient -- connect, disconnect, publish, subscribe, reconnection."""

from __future__ import annotations

import asyncio
import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import SecretStr

from iotguard.core.config import MqttSettings
from iotguard.core.exceptions import MqttConnectionError, MqttError
from iotguard.mqtt.client import MqttClient


def _mqtt_settings(**kwargs: Any) -> MqttSettings:
    defaults = {
        "broker_host": "localhost",
        "broker_port": 1883,
        "username": "",
        "password": SecretStr(""),
        "client_id": "test-client",
        "topics": ["iotguard/test/#"],
    }
    defaults.update(kwargs)
    return MqttSettings(**defaults)


class TestMqttClientProperties:
    """Test initial state and properties."""

    def test_initial_state_not_connected(self) -> None:
        client = MqttClient(_mqtt_settings())
        assert client.is_connected is False

    def test_settings_stored(self) -> None:
        settings = _mqtt_settings(broker_host="broker.example.com")
        client = MqttClient(settings)
        assert client._settings.broker_host == "broker.example.com"


class TestMqttConnect:
    """Test connection logic."""

    async def test_connect_creates_paho_client(self) -> None:
        client = MqttClient(_mqtt_settings())

        with patch("iotguard.mqtt.client.paho_mqtt.Client") as MockClient:
            mock_paho = MagicMock()
            MockClient.return_value = mock_paho

            # Simulate successful connection
            def fake_connect(host, port):
                # Trigger the on_connect callback
                client._on_connect(mock_paho, None, None, 0)

            mock_paho.connect = fake_connect
            mock_paho.loop_start = MagicMock()
            mock_paho.subscribe = MagicMock()

            await client.connect()

            assert client.is_connected is True

    async def test_connect_with_credentials(self) -> None:
        settings = _mqtt_settings(username="user", password=SecretStr("pass"))
        client = MqttClient(settings)

        with patch("iotguard.mqtt.client.paho_mqtt.Client") as MockClient:
            mock_paho = MagicMock()
            MockClient.return_value = mock_paho

            def fake_connect(host, port):
                client._on_connect(mock_paho, None, None, 0)

            mock_paho.connect = fake_connect
            mock_paho.loop_start = MagicMock()
            mock_paho.subscribe = MagicMock()

            await client.connect()

            mock_paho.username_pw_set.assert_called_once_with("user", "pass")

    async def test_connect_failure_raises(self) -> None:
        client = MqttClient(_mqtt_settings())

        with patch("iotguard.mqtt.client.paho_mqtt.Client") as MockClient:
            mock_paho = MagicMock()
            MockClient.return_value = mock_paho
            mock_paho.connect = MagicMock(side_effect=OSError("Connection refused"))
            mock_paho.loop_start = MagicMock()

            with pytest.raises(MqttConnectionError):
                await client.connect()


class TestMqttDisconnect:
    """Test disconnection."""

    async def test_disconnect_clears_state(self) -> None:
        client = MqttClient(_mqtt_settings())

        with patch("iotguard.mqtt.client.paho_mqtt.Client") as MockClient:
            mock_paho = MagicMock()
            MockClient.return_value = mock_paho

            def fake_connect(host, port):
                client._on_connect(mock_paho, None, None, 0)

            mock_paho.connect = fake_connect
            mock_paho.loop_start = MagicMock()
            mock_paho.loop_stop = MagicMock()
            mock_paho.disconnect = MagicMock()
            mock_paho.subscribe = MagicMock()

            await client.connect()
            assert client.is_connected is True

            await client.disconnect()
            assert client.is_connected is False


class TestMqttPublishSubscribe:
    """Test publish and subscribe operations."""

    async def test_publish_requires_connection(self) -> None:
        client = MqttClient(_mqtt_settings())
        with pytest.raises(MqttError, match="Not connected"):
            await client.publish("topic", {"key": "value"})

    async def test_subscribe_requires_connection(self) -> None:
        client = MqttClient(_mqtt_settings())
        with pytest.raises(MqttError, match="Not connected"):
            await client.subscribe("topic")


class TestMqttHandlers:
    """Test message handler registration and dispatch."""

    def test_add_handler(self) -> None:
        client = MqttClient(_mqtt_settings())

        def handler(topic: str, payload: dict) -> None:
            pass

        client.add_handler(handler)
        assert handler in client._handlers

    def test_remove_handler(self) -> None:
        client = MqttClient(_mqtt_settings())

        def handler(topic: str, payload: dict) -> None:
            pass

        client.add_handler(handler)
        client.remove_handler(handler)
        assert handler not in client._handlers

    def test_on_message_dispatches_to_handlers(self) -> None:
        client = MqttClient(_mqtt_settings())
        received: list[tuple[str, dict]] = []

        def handler(topic: str, payload: dict) -> None:
            received.append((topic, payload))

        client.add_handler(handler)

        # Simulate an incoming message
        mock_msg = MagicMock()
        mock_msg.topic = "iotguard/test/status"
        mock_msg.payload = json.dumps({"status": "online"}).encode()

        client._on_message(MagicMock(), None, mock_msg)

        assert len(received) == 1
        assert received[0][0] == "iotguard/test/status"
        assert received[0][1]["status"] == "online"

    def test_on_message_handles_invalid_json(self) -> None:
        client = MqttClient(_mqtt_settings())
        received: list[tuple[str, dict]] = []

        def handler(topic: str, payload: dict) -> None:
            received.append((topic, payload))

        client.add_handler(handler)

        mock_msg = MagicMock()
        mock_msg.topic = "test/topic"
        mock_msg.payload = b"not json"

        client._on_message(MagicMock(), None, mock_msg)

        assert len(received) == 1
        assert "raw" in received[0][1]

    def test_handler_error_does_not_crash(self) -> None:
        client = MqttClient(_mqtt_settings())

        def bad_handler(topic: str, payload: dict) -> None:
            raise RuntimeError("handler crash")

        client.add_handler(bad_handler)

        mock_msg = MagicMock()
        mock_msg.topic = "test"
        mock_msg.payload = b'{"x": 1}'

        # Should not raise
        client._on_message(MagicMock(), None, mock_msg)


class TestMqttReconnection:
    """Test reconnection behavior."""

    def test_on_disconnect_with_reconnect_flag(self) -> None:
        client = MqttClient(_mqtt_settings())
        client._connected.set()
        client._should_reconnect = True

        client._on_disconnect(MagicMock(), None, None, 1)
        assert not client.is_connected
        # _should_reconnect remains True -- paho handles the reconnect itself

    def test_on_disconnect_clean(self) -> None:
        client = MqttClient(_mqtt_settings())
        client._connected.set()
        client._should_reconnect = False

        client._on_disconnect(MagicMock(), None, None, 0)
        assert not client.is_connected

    def test_on_connect_subscribes_to_configured_topics(self) -> None:
        settings = _mqtt_settings(topics=["a/#", "b/#"])
        client = MqttClient(settings)
        mock_paho = MagicMock()

        client._on_connect(mock_paho, None, None, 0)

        assert mock_paho.subscribe.call_count == 2
        assert client.is_connected is True
