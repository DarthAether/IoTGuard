"""Unit tests for the EventBus pub/sub system."""

from __future__ import annotations

import asyncio

import pytest

from iotguard.core.events import (
    AlertEvent,
    CommandAnalyzedEvent,
    CommandExecutedEvent,
    DeviceStatusEvent,
    DomainEvent,
    EventBus,
    RuleViolationEvent,
)


class TestEventBusPubSub:
    """Core pub/sub functionality."""

    async def test_subscribe_and_publish(self, event_bus: EventBus) -> None:
        received: list[DomainEvent] = []

        async def handler(event: CommandAnalyzedEvent) -> None:
            received.append(event)

        event_bus.subscribe(CommandAnalyzedEvent, handler)
        event = CommandAnalyzedEvent(device_id="d1", command="unlock", risk_level="LOW")
        await event_bus.publish(event)

        assert len(received) == 1
        assert received[0].device_id == "d1"

    async def test_multiple_subscribers(self, event_bus: EventBus) -> None:
        count = {"a": 0, "b": 0}

        async def handler_a(event: DomainEvent) -> None:
            count["a"] += 1

        async def handler_b(event: DomainEvent) -> None:
            count["b"] += 1

        event_bus.subscribe(DeviceStatusEvent, handler_a)
        event_bus.subscribe(DeviceStatusEvent, handler_b)

        await event_bus.publish(DeviceStatusEvent(device_id="x", status="online"))

        assert count["a"] == 1
        assert count["b"] == 1

    async def test_unsubscribe(self, event_bus: EventBus) -> None:
        received: list[DomainEvent] = []

        async def handler(event: DomainEvent) -> None:
            received.append(event)

        event_bus.subscribe(CommandExecutedEvent, handler)
        event_bus.unsubscribe(CommandExecutedEvent, handler)

        await event_bus.publish(CommandExecutedEvent(device_id="d", command="lock"))

        assert len(received) == 0

    async def test_no_subscribers_does_not_raise(self, event_bus: EventBus) -> None:
        # Should not raise even if nobody is listening
        await event_bus.publish(AlertEvent(severity="HIGH", message="test"))

    async def test_event_type_isolation(self, event_bus: EventBus) -> None:
        """Subscribers for one event type don't receive other types."""
        received: list[DomainEvent] = []

        async def handler(event: DomainEvent) -> None:
            received.append(event)

        event_bus.subscribe(CommandAnalyzedEvent, handler)

        # Publish a different event type
        await event_bus.publish(DeviceStatusEvent(device_id="x", status="offline"))

        assert len(received) == 0

    async def test_event_timestamp_auto_set(self) -> None:
        event = CommandAnalyzedEvent(device_id="d", command="c", risk_level="LOW")
        assert event.timestamp is not None


class TestEventBusErrorIsolation:
    """One failing handler must not break others."""

    async def test_error_in_handler_does_not_propagate(
        self, event_bus: EventBus,
    ) -> None:
        results: list[str] = []

        async def failing_handler(event: DomainEvent) -> None:
            raise RuntimeError("Handler exploded")

        async def good_handler(event: DomainEvent) -> None:
            results.append("ok")

        event_bus.subscribe(RuleViolationEvent, failing_handler)
        event_bus.subscribe(RuleViolationEvent, good_handler)

        # Should not raise
        await event_bus.publish(
            RuleViolationEvent(rule_name="r", command="c", device_id="d", action="BLOCK")
        )

        # The good handler should still have run
        assert results == ["ok"]

    async def test_multiple_failing_handlers(self, event_bus: EventBus) -> None:
        results: list[str] = []

        async def fail1(event: DomainEvent) -> None:
            raise ValueError("fail1")

        async def fail2(event: DomainEvent) -> None:
            raise TypeError("fail2")

        async def success(event: DomainEvent) -> None:
            results.append("success")

        event_bus.subscribe(AlertEvent, fail1)
        event_bus.subscribe(AlertEvent, fail2)
        event_bus.subscribe(AlertEvent, success)

        await event_bus.publish(AlertEvent(severity="CRITICAL", message="x"))

        assert results == ["success"]
