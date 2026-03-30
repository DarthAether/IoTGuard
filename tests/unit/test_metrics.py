"""Unit tests for Prometheus metrics -- counter increments, histogram observations."""

from __future__ import annotations

import pytest
from prometheus_client import CollectorRegistry

from iotguard.core.events import (
    CommandAnalyzedEvent,
    CommandExecutedEvent,
    EventBus,
    RuleViolationEvent,
)
from iotguard.observability.metrics import (
    MetricsCollector,
    analysis_latency_seconds,
    commands_analyzed_total,
    commands_blocked_total,
    commands_executed_total,
    http_requests_total,
    mqtt_messages_total,
    rule_violations_total,
)


class TestCounterIncrements:
    """Verify that event-driven counters increment correctly."""

    async def test_commands_analyzed_counter(self) -> None:
        collector = MetricsCollector()
        event = CommandAnalyzedEvent(
            device_id="dev-1",
            command="turn_on",
            risk_level="LOW",
            blocked=False,
        )
        # Get baseline
        before = commands_analyzed_total.labels(
            device_id="dev-1", risk_level="LOW",
        )._value.get()

        await collector.on_command_analyzed(event)

        after = commands_analyzed_total.labels(
            device_id="dev-1", risk_level="LOW",
        )._value.get()

        assert after == before + 1

    async def test_commands_executed_counter(self) -> None:
        collector = MetricsCollector()
        event = CommandExecutedEvent(
            device_id="dev-2",
            command="lock",
            user="admin",
            result="ok",
        )
        before = commands_executed_total.labels(
            device_id="dev-2", user="admin",
        )._value.get()

        await collector.on_command_executed(event)

        after = commands_executed_total.labels(
            device_id="dev-2", user="admin",
        )._value.get()
        assert after == before + 1

    async def test_rule_violations_counter(self) -> None:
        collector = MetricsCollector()
        event = RuleViolationEvent(
            rule_name="no-rm",
            command="rm -rf",
            device_id="dev-3",
            action="BLOCK",
        )
        before = rule_violations_total.labels(
            rule_name="no-rm", action="BLOCK",
        )._value.get()

        await collector.on_rule_violation(event)

        after = rule_violations_total.labels(
            rule_name="no-rm", action="BLOCK",
        )._value.get()
        assert after == before + 1


class TestHistogramObservations:
    """Verify histogram metrics can be observed."""

    def test_analysis_latency_histogram_observable(self) -> None:
        analysis_latency_seconds.labels(engine="gemini").observe(0.5)
        analysis_latency_seconds.labels(engine="rule_based").observe(0.01)
        # No assertion needed -- if observe raises, the test fails

    def test_http_request_histogram_observable(self) -> None:
        from iotguard.observability.metrics import http_request_duration_seconds

        http_request_duration_seconds.labels(method="GET", path="/health").observe(0.05)


class TestMetricsCollectorRegistration:
    """Verify the collector wires to the event bus."""

    def test_register_subscribes_handlers(self) -> None:
        bus = EventBus()
        collector = MetricsCollector()
        collector.register(bus)

        # Check that handlers were registered
        assert CommandAnalyzedEvent in bus._subscribers
        assert CommandExecutedEvent in bus._subscribers
        assert RuleViolationEvent in bus._subscribers

    async def test_full_integration_via_bus(self) -> None:
        bus = EventBus()
        collector = MetricsCollector()
        collector.register(bus)

        event = CommandAnalyzedEvent(
            device_id="int-dev",
            command="test",
            risk_level="MEDIUM",
        )

        before = commands_analyzed_total.labels(
            device_id="int-dev", risk_level="MEDIUM",
        )._value.get()

        await bus.publish(event)

        after = commands_analyzed_total.labels(
            device_id="int-dev", risk_level="MEDIUM",
        )._value.get()
        assert after == before + 1


class TestMetricDefinitions:
    """Verify metric objects exist and have correct labels."""

    def test_commands_analyzed_has_labels(self) -> None:
        # Should not raise
        commands_analyzed_total.labels(device_id="x", risk_level="LOW")

    def test_commands_blocked_has_labels(self) -> None:
        commands_blocked_total.labels(device_id="x", reason="rule")

    def test_mqtt_messages_has_labels(self) -> None:
        mqtt_messages_total.labels(topic="test", direction="inbound")

    def test_http_requests_has_labels(self) -> None:
        http_requests_total.labels(method="GET", path="/", status_code="200")
