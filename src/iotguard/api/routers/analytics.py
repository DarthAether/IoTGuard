"""Analytics and dashboard endpoints."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel
from fastapi import APIRouter, Query

from iotguard.api.dependencies import DbSession, ViewerUser
from iotguard.db.repositories import AuditRepository, CommandLogRepository, DeviceRepository

router = APIRouter(prefix="/v1/analytics", tags=["analytics"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class DashboardResponse(BaseModel):
    total_commands: int
    blocked_commands: int
    risk_distribution: dict[str, int]
    active_devices: int
    total_devices: int


class AuditLogItem(BaseModel):
    id: int
    event_type: str
    user_id: str | None
    payload: dict[str, Any]
    correlation_id: str | None
    timestamp: datetime

    class Config:
        from_attributes = True


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/dashboard", response_model=DashboardResponse)
async def dashboard(
    user: ViewerUser,
    session: DbSession,
) -> DashboardResponse:
    """Summary stats for the dashboard -- commands today, blocked, risk distribution."""
    cmd_repo = CommandLogRepository(session)
    dev_repo = DeviceRepository(session)

    today = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    stats = await cmd_repo.get_stats(since=today)

    total_devices = await dev_repo.count()

    return DashboardResponse(
        total_commands=stats["total"],
        blocked_commands=stats["blocked"],
        risk_distribution=stats.get("by_risk_level", {}),
        active_devices=total_devices,  # approximate; count online if repo supports it
        total_devices=total_devices,
    )


@router.get("/commands")
async def command_stats(
    user: ViewerUser,
    session: DbSession,
    since: datetime | None = Query(None),
    until: datetime | None = Query(None),
) -> dict[str, Any]:
    """Command statistics grouped by device and risk level for a time window."""
    repo = CommandLogRepository(session)
    stats = await repo.get_stats(since=since, until=until)
    return stats


@router.get("/audit", response_model=list[AuditLogItem])
async def audit_logs(
    user: ViewerUser,
    session: DbSession,
    event_type: str | None = Query(None),
    user_id: uuid.UUID | None = Query(None),
    since: datetime | None = Query(None),
    until: datetime | None = Query(None),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=250),
) -> list[AuditLogItem]:
    """Query the audit log with optional filters."""
    repo = AuditRepository(session)
    entries = await repo.query(
        offset=offset,
        limit=limit,
        event_type=event_type,
        user_id=user_id,
        since=since,
        until=until,
    )
    return [
        AuditLogItem(
            id=e.id,
            event_type=e.event_type,
            user_id=str(e.user_id) if e.user_id else None,
            payload=e.payload,
            correlation_id=e.correlation_id,
            timestamp=e.timestamp,
        )
        for e in entries
    ]
