"""In-process async event bus with typed domain events.

Subscribers are plain ``async def`` callables registered against a concrete
event type.  :meth:`EventBus.publish` fans out to every subscriber; errors
in one handler never block the others.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Callable, Coroutine

import structlog

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Domain events
# ---------------------------------------------------------------------------

Subscriber = Callable[..., Coroutine[Any, Any, None]]


@dataclass(frozen=True, slots=True)
class DomainEvent:
    """Base class that timestamps every event automatically."""

    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass(frozen=True, slots=True)
class CommandAnalyzedEvent(DomainEvent):
    """Emitted after the analysis pipeline finishes."""

    device_id: str = ""
    command: str = ""
    risk_level: str = ""
    blocked: bool = False
    user: str = ""


@dataclass(frozen=True, slots=True)
class CommandExecutedEvent(DomainEvent):
    """Emitted when a device command is successfully executed."""

    device_id: str = ""
    command: str = ""
    user: str = ""
    result: str = ""


@dataclass(frozen=True, slots=True)
class DeviceStatusEvent(DomainEvent):
    """Emitted on device online/offline transitions or state changes."""

    device_id: str = ""
    status: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class RuleViolationEvent(DomainEvent):
    """Emitted when a command matches a security rule."""

    rule_name: str = ""
    command: str = ""
    device_id: str = ""
    action: str = ""


@dataclass(frozen=True, slots=True)
class AlertEvent(DomainEvent):
    """Generic alert event (high-risk detection, anomalies, etc.)."""

    severity: str = ""
    message: str = ""
    source: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Event bus
# ---------------------------------------------------------------------------


class EventBus:
    """Simple in-process publish / subscribe bus for the current event loop."""

    def __init__(self) -> None:
        self._subscribers: dict[type[DomainEvent], list[Subscriber]] = {}

    # -- registration -------------------------------------------------------

    def subscribe(self, event_type: type[DomainEvent], handler: Subscriber) -> None:
        """Register *handler* to be called when *event_type* is published."""
        self._subscribers.setdefault(event_type, []).append(handler)

    def unsubscribe(self, event_type: type[DomainEvent], handler: Subscriber) -> None:
        """Remove a previously registered handler."""
        handlers = self._subscribers.get(event_type, [])
        if handler in handlers:
            handlers.remove(handler)

    # -- publication --------------------------------------------------------

    async def publish(self, event: DomainEvent) -> None:
        """Dispatch *event* to all registered subscribers sequentially.

        Errors in individual handlers are logged but never propagated so that
        one broken handler cannot take down the pipeline.
        """
        handlers = self._subscribers.get(type(event), [])
        for handler in handlers:
            try:
                await handler(event)
            except Exception:
                logger.exception(
                    "event_handler_error",
                    event=type(event).__name__,
                    handler=getattr(handler, "__qualname__", str(handler)),
                )

    def publish_nowait(self, event: DomainEvent) -> None:
        """Schedule publication without awaiting -- fire-and-forget."""
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self.publish(event))
        except RuntimeError:
            logger.warning("no_running_loop", event=type(event).__name__)
