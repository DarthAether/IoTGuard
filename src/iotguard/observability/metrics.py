"""Prometheus metrics for IoTGuard.

Exposes counters, histograms and gauges covering commands, devices, MQTT,
HTTP traffic, and rule violations.  :func:`create_metrics_app` returns a
standalone ASGI app suitable for mounting at ``/metrics``.
"""

from __future__ import annotations

from prometheus_client import (
    REGISTRY,
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    make_asgi_app,
)
from starlette.types import ASGIApp

# ---------------------------------------------------------------------------
# Metric definitions (module-level singletons)
# ---------------------------------------------------------------------------

commands_analyzed_total = Counter(
    "iotguard_commands_analyzed_total",
    "Total commands that have been analysed",
    labelnames=["device_id", "risk_level"],
)

commands_blocked_total = Counter(
    "iotguard_commands_blocked_total",
    "Total commands blocked by security rules",
    labelnames=["device_id", "reason"],
)

commands_executed_total = Counter(
    "iotguard_commands_executed_total",
    "Total commands successfully executed on devices",
    labelnames=["device_id", "user"],
)

analysis_latency_seconds = Histogram(
    "iotguard_analysis_latency_seconds",
    "Time taken to complete command analysis",
    labelnames=["engine"],
    buckets=(0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)

active_devices = Gauge(
    "iotguard_active_devices",
    "Number of currently active (online) devices",
)

mqtt_messages_total = Counter(
    "iotguard_mqtt_messages_total",
    "Total MQTT messages sent / received",
    labelnames=["topic", "direction"],
)

http_requests_total = Counter(
    "iotguard_http_requests_total",
    "Total HTTP requests",
    labelnames=["method", "path", "status_code"],
)

http_request_duration_seconds = Histogram(
    "iotguard_http_request_duration_seconds",
    "HTTP request latency",
    labelnames=["method", "path"],
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0),
)

rule_violations_total = Counter(
    "iotguard_rule_violations_total",
    "Total security rule violations",
    labelnames=["rule_name", "action"],
)


# ---------------------------------------------------------------------------
# Collector that ties event-bus events to metric increments
# ---------------------------------------------------------------------------


class MetricsCollector:
    """Subscribe to the event bus and update Prometheus counters."""

    async def on_command_analyzed(self, event: object) -> None:
        from iotguard.core.events import CommandAnalyzedEvent

        assert isinstance(event, CommandAnalyzedEvent)
        commands_analyzed_total.labels(
            device_id=event.device_id,
            risk_level=event.risk_level,
        ).inc()

    async def on_command_executed(self, event: object) -> None:
        from iotguard.core.events import CommandExecutedEvent

        assert isinstance(event, CommandExecutedEvent)
        commands_executed_total.labels(
            device_id=event.device_id,
            user=event.user,
        ).inc()

    async def on_rule_violation(self, event: object) -> None:
        from iotguard.core.events import RuleViolationEvent

        assert isinstance(event, RuleViolationEvent)
        rule_violations_total.labels(
            rule_name=event.rule_name,
            action=event.action,
        ).inc()

    def register(self, event_bus: object) -> None:
        """Wire all handlers to the given :class:`EventBus`."""
        from iotguard.core.events import (
            CommandAnalyzedEvent,
            CommandExecutedEvent,
            EventBus,
            RuleViolationEvent,
        )

        assert isinstance(event_bus, EventBus)
        event_bus.subscribe(CommandAnalyzedEvent, self.on_command_analyzed)
        event_bus.subscribe(CommandExecutedEvent, self.on_command_executed)
        event_bus.subscribe(RuleViolationEvent, self.on_rule_violation)


# ---------------------------------------------------------------------------
# ASGI app for /metrics
# ---------------------------------------------------------------------------


def create_metrics_app(registry: CollectorRegistry = REGISTRY) -> ASGIApp:
    """Return a Starlette-compatible ASGI app serving Prometheus metrics."""
    return make_asgi_app(registry)
