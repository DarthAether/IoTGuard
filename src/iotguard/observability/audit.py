"""Audit logger -- subscribes to domain events and persists audit entries.

Each audit record is written to the ``audit_logs`` table via the repository
layer.  The logger obtains its own short-lived DB session to avoid coupling
to the request lifecycle.
"""

from __future__ import annotations

import structlog
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from iotguard.core.events import (
    AlertEvent,
    CommandAnalyzedEvent,
    CommandExecutedEvent,
    DeviceStatusEvent,
    EventBus,
    RuleViolationEvent,
)
from iotguard.core.logging import correlation_id_var
from iotguard.db.models import AuditLog
from iotguard.db.repositories import AuditRepository

logger = structlog.get_logger(__name__)


class AuditLogger:
    """Persist domain events as audit log entries."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    async def on_command_analyzed(self, event: CommandAnalyzedEvent) -> None:
        await self._persist(
            event_type="command_analyzed",
            payload={
                "user": event.user,
                "device_id": event.device_id,
                "command": event.command,
                "risk_level": event.risk_level,
                "risk_score": event.risk_score,
            },
        )

    async def on_command_executed(self, event: CommandExecutedEvent) -> None:
        await self._persist(
            event_type="command_executed",
            payload={
                "user": event.user,
                "device_id": event.device_id,
                "command": event.command,
                "result": event.result,
            },
        )

    async def on_device_status(self, event: DeviceStatusEvent) -> None:
        await self._persist(
            event_type="device_status_changed",
            payload={
                "device_id": event.device_id,
                "status": event.status,
                **event.metadata,
            },
        )

    async def on_rule_violation(self, event: RuleViolationEvent) -> None:
        await self._persist(
            event_type="rule_violation",
            payload={
                "rule_name": event.rule_name,
                "device_id": event.device_id,
                "command": event.command,
                "action": event.action,
            },
        )

    async def on_alert(self, event: AlertEvent) -> None:
        await self._persist(
            event_type="alert",
            payload={
                "severity": event.severity,
                "message": event.message,
                "source": event.source,
                **event.metadata,
            },
        )

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register(self, event_bus: EventBus) -> None:
        """Wire all audit handlers to the given event bus."""
        event_bus.subscribe(CommandAnalyzedEvent, self.on_command_analyzed)
        event_bus.subscribe(CommandExecutedEvent, self.on_command_executed)
        event_bus.subscribe(DeviceStatusEvent, self.on_device_status)
        event_bus.subscribe(RuleViolationEvent, self.on_rule_violation)
        event_bus.subscribe(AlertEvent, self.on_alert)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    async def _persist(
        self,
        *,
        event_type: str,
        payload: dict | None = None,
    ) -> None:
        try:
            async with self._session_factory() as session, session.begin():
                repo = AuditRepository(session)
                entry = AuditLog(
                    event_type=event_type,
                    payload=payload or {},
                    correlation_id=correlation_id_var.get() or None,
                )
                await repo.create(entry)
        except Exception:
            logger.exception("audit_persist_failed", event_type=event_type)
