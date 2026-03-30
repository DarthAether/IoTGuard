"""Async repository layer -- thin wrappers over SQLAlchemy queries.

Each repository receives an ``AsyncSession`` at construction time and exposes
domain-friendly CRUD operations.  Callers are responsible for committing the
session (typically via the ``get_session`` dependency which auto-commits on
success).
"""

from __future__ import annotations

import re
import uuid
from datetime import UTC, datetime
from typing import Any, Sequence

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from iotguard.db.models import (
    AuditLog,
    CommandLog,
    Device,
    DevicePermission,
    SecurityRule,
    User,
)


# ---------------------------------------------------------------------------
# User repository
# ---------------------------------------------------------------------------


class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def create(self, user: User) -> User:
        self._s.add(user)
        await self._s.flush()
        return user

    async def get_by_username(self, username: str) -> User | None:
        stmt = select(User).where(User.username == username)
        result = await self._s.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_id(self, user_id: uuid.UUID) -> User | None:
        return await self._s.get(User, user_id)

    async def list_all(self, *, offset: int = 0, limit: int = 50) -> Sequence[User]:
        stmt = (
            select(User)
            .order_by(User.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        result = await self._s.execute(stmt)
        return result.scalars().all()

    async def update_role(self, user_id: uuid.UUID, role: str) -> None:
        stmt = update(User).where(User.id == user_id).values(role=role)
        await self._s.execute(stmt)

    async def deactivate(self, user_id: uuid.UUID) -> None:
        stmt = update(User).where(User.id == user_id).values(is_active=False)
        await self._s.execute(stmt)

    async def count(self) -> int:
        stmt = select(func.count()).select_from(User)
        result = await self._s.execute(stmt)
        return result.scalar_one()


# ---------------------------------------------------------------------------
# Device repository
# ---------------------------------------------------------------------------


class DeviceRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def create(self, device: Device) -> Device:
        self._s.add(device)
        await self._s.flush()
        return device

    async def get_by_id(self, device_id: uuid.UUID) -> Device | None:
        return await self._s.get(Device, device_id)

    async def get_by_device_id(self, device_id: str) -> Device | None:
        stmt = select(Device).where(Device.device_id == device_id)
        result = await self._s.execute(stmt)
        return result.scalar_one_or_none()

    async def list_all(
        self, *, offset: int = 0, limit: int = 50
    ) -> Sequence[Device]:
        stmt = (
            select(Device)
            .order_by(Device.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        result = await self._s.execute(stmt)
        return result.scalars().all()

    async def update_state(
        self, device_pk: uuid.UUID, state: dict[str, Any]
    ) -> None:
        stmt = update(Device).where(Device.id == device_pk).values(state=state)
        await self._s.execute(stmt)

    async def update_online_status(
        self,
        device_pk: uuid.UUID,
        *,
        is_online: bool,
        last_seen: datetime | None = None,
    ) -> None:
        values: dict[str, Any] = {"is_online": is_online}
        if last_seen is not None:
            values["last_seen"] = last_seen
        stmt = update(Device).where(Device.id == device_pk).values(**values)
        await self._s.execute(stmt)

    async def delete(self, device_pk: uuid.UUID) -> None:
        stmt = delete(Device).where(Device.id == device_pk)
        await self._s.execute(stmt)

    async def count(self) -> int:
        stmt = select(func.count()).select_from(Device)
        result = await self._s.execute(stmt)
        return result.scalar_one()


# ---------------------------------------------------------------------------
# Security rule repository
# ---------------------------------------------------------------------------


class SecurityRuleRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def create(self, rule: SecurityRule) -> SecurityRule:
        self._s.add(rule)
        await self._s.flush()
        return rule

    async def list_active(self) -> Sequence[SecurityRule]:
        stmt = (
            select(SecurityRule)
            .where(SecurityRule.is_active.is_(True))
            .order_by(SecurityRule.priority.asc(), SecurityRule.name)
        )
        result = await self._s.execute(stmt)
        return result.scalars().all()

    async def list_all(
        self, *, offset: int = 0, limit: int = 50
    ) -> Sequence[SecurityRule]:
        stmt = (
            select(SecurityRule)
            .order_by(SecurityRule.priority.asc())
            .offset(offset)
            .limit(limit)
        )
        result = await self._s.execute(stmt)
        return result.scalars().all()

    async def update(
        self, rule_id: uuid.UUID, values: dict[str, Any]
    ) -> None:
        stmt = (
            update(SecurityRule).where(SecurityRule.id == rule_id).values(**values)
        )
        await self._s.execute(stmt)

    async def delete(self, rule_id: uuid.UUID) -> None:
        stmt = delete(SecurityRule).where(SecurityRule.id == rule_id)
        await self._s.execute(stmt)

    async def get_matching_rules(self, command: str) -> Sequence[SecurityRule]:
        """Return active rules whose regex pattern matches *command*.

        Rules are returned sorted by priority (lowest number = highest
        priority).  Invalid patterns are silently skipped.
        """
        all_active = await self.list_active()
        matched: list[SecurityRule] = []
        for rule in all_active:
            try:
                if re.search(rule.pattern, command, re.IGNORECASE):
                    matched.append(rule)
            except re.error:
                continue
        return matched


# ---------------------------------------------------------------------------
# Command log repository
# ---------------------------------------------------------------------------


class CommandLogRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def create(self, log: CommandLog) -> CommandLog:
        self._s.add(log)
        await self._s.flush()
        return log

    async def list_recent(
        self,
        *,
        offset: int = 0,
        limit: int = 50,
        device_id: uuid.UUID | None = None,
        risk_level: str | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
    ) -> Sequence[CommandLog]:
        stmt = select(CommandLog).order_by(CommandLog.timestamp.desc())
        if device_id is not None:
            stmt = stmt.where(CommandLog.device_id == device_id)
        if risk_level is not None:
            stmt = stmt.where(CommandLog.risk_level == risk_level)
        if since is not None:
            stmt = stmt.where(CommandLog.timestamp >= since)
        if until is not None:
            stmt = stmt.where(CommandLog.timestamp <= until)
        stmt = stmt.offset(offset).limit(limit)
        result = await self._s.execute(stmt)
        return result.scalars().all()

    async def get_stats(
        self,
        *,
        since: datetime | None = None,
        until: datetime | None = None,
    ) -> dict[str, Any]:
        """Return aggregate statistics over the given time window."""
        conditions: list[Any] = []
        if since is not None:
            conditions.append(CommandLog.timestamp >= since)
        if until is not None:
            conditions.append(CommandLog.timestamp <= until)

        # Total
        total_q = select(func.count()).select_from(CommandLog)
        blocked_q = (
            select(func.count())
            .select_from(CommandLog)
            .where(CommandLog.was_blocked.is_(True))
        )
        risk_q = (
            select(CommandLog.risk_level, func.count())
            .group_by(CommandLog.risk_level)
        )
        device_q = (
            select(CommandLog.device_id, func.count())
            .group_by(CommandLog.device_id)
        )

        for cond in conditions:
            total_q = total_q.where(cond)
            blocked_q = blocked_q.where(cond)
            risk_q = risk_q.where(cond)
            device_q = device_q.where(cond)

        total = (await self._s.execute(total_q)).scalar_one()
        blocked = (await self._s.execute(blocked_q)).scalar_one()
        risk_rows = (await self._s.execute(risk_q)).all()
        device_rows = (await self._s.execute(device_q)).all()

        return {
            "total": total,
            "blocked": blocked,
            "by_risk_level": {str(r): c for r, c in risk_rows},
            "by_device": {str(d): c for d, c in device_rows},
        }


# ---------------------------------------------------------------------------
# Audit log repository
# ---------------------------------------------------------------------------


class AuditRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def create(self, entry: AuditLog) -> AuditLog:
        self._s.add(entry)
        await self._s.flush()
        return entry

    async def query(
        self,
        *,
        offset: int = 0,
        limit: int = 50,
        event_type: str | None = None,
        user_id: uuid.UUID | None = None,
        correlation_id: str | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
    ) -> Sequence[AuditLog]:
        stmt = select(AuditLog).order_by(AuditLog.timestamp.desc())
        if event_type is not None:
            stmt = stmt.where(AuditLog.event_type == event_type)
        if user_id is not None:
            stmt = stmt.where(AuditLog.user_id == user_id)
        if correlation_id is not None:
            stmt = stmt.where(AuditLog.correlation_id == correlation_id)
        if since is not None:
            stmt = stmt.where(AuditLog.timestamp >= since)
        if until is not None:
            stmt = stmt.where(AuditLog.timestamp <= until)
        stmt = stmt.offset(offset).limit(limit)
        result = await self._s.execute(stmt)
        return result.scalars().all()


# ---------------------------------------------------------------------------
# Permission repository
# ---------------------------------------------------------------------------


class PermissionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def grant(
        self,
        user_id: uuid.UUID,
        device_id: uuid.UUID,
        *,
        can_read: bool = True,
        can_write: bool = False,
        can_execute: bool = False,
    ) -> DevicePermission:
        perm = DevicePermission(
            user_id=user_id,
            device_id=device_id,
            can_read=can_read,
            can_write=can_write,
            can_execute=can_execute,
        )
        self._s.add(perm)
        await self._s.flush()
        return perm

    async def revoke(self, user_id: uuid.UUID, device_id: uuid.UUID) -> None:
        stmt = delete(DevicePermission).where(
            DevicePermission.user_id == user_id,
            DevicePermission.device_id == device_id,
        )
        await self._s.execute(stmt)

    async def get_user_permissions(
        self, user_id: uuid.UUID
    ) -> Sequence[DevicePermission]:
        stmt = select(DevicePermission).where(
            DevicePermission.user_id == user_id
        )
        result = await self._s.execute(stmt)
        return result.scalars().all()

    async def check_permission(
        self,
        user_id: uuid.UUID,
        device_id: uuid.UUID,
        *,
        action: str = "read",
    ) -> bool:
        """Return ``True`` if *user_id* has the requested *action* on *device_id*.

        *action* must be one of ``"read"``, ``"write"``, ``"execute"``.
        """
        stmt = select(DevicePermission).where(
            DevicePermission.user_id == user_id,
            DevicePermission.device_id == device_id,
        )
        result = await self._s.execute(stmt)
        perm = result.scalar_one_or_none()
        if perm is None:
            return False

        if action == "read":
            return perm.can_read
        if action == "write":
            return perm.can_write
        if action == "execute":
            return perm.can_execute
        return False
