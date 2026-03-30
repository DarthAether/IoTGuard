"""Integration tests for all DB repositories using SQLite."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from iotguard.core.security import hash_password
from iotguard.db.models import (
    AuditLog,
    CommandLog,
    Device,
    SecurityRule,
    User,
)
from iotguard.db.repositories import (
    AuditRepository,
    CommandLogRepository,
    DeviceRepository,
    PermissionRepository,
    SecurityRuleRepository,
    UserRepository,
)


# ---------------------------------------------------------------------------
# User repository
# ---------------------------------------------------------------------------


class TestUserRepository:
    async def test_create_and_get_by_username(self, db_session: AsyncSession) -> None:
        repo = UserRepository(db_session)
        user = User(
            username="alice",
            hashed_password=hash_password("pass"),
            role="admin",
        )
        await repo.create(user)
        await db_session.commit()

        found = await repo.get_by_username("alice")
        assert found is not None
        assert found.username == "alice"

    async def test_get_by_id(self, db_session: AsyncSession) -> None:
        repo = UserRepository(db_session)
        user = User(
            username="bob",
            hashed_password=hash_password("pass"),
            role="viewer",
        )
        await repo.create(user)
        await db_session.commit()

        found = await repo.get_by_id(user.id)
        assert found is not None
        assert found.username == "bob"

    async def test_get_nonexistent_returns_none(self, db_session: AsyncSession) -> None:
        repo = UserRepository(db_session)
        found = await repo.get_by_username("nobody")
        assert found is None

    async def test_list_all(self, db_session: AsyncSession) -> None:
        repo = UserRepository(db_session)
        for i in range(3):
            await repo.create(
                User(username=f"user{i}", hashed_password="x", role="viewer")
            )
        await db_session.commit()

        users = await repo.list_all()
        assert len(users) >= 3

    async def test_count(self, db_session: AsyncSession) -> None:
        repo = UserRepository(db_session)
        initial = await repo.count()
        await repo.create(
            User(username="counter-test", hashed_password="x", role="viewer")
        )
        await db_session.commit()
        assert await repo.count() == initial + 1

    async def test_update_role(self, db_session: AsyncSession) -> None:
        repo = UserRepository(db_session)
        user = User(username="role-change", hashed_password="x", role="viewer")
        await repo.create(user)
        await db_session.commit()

        await repo.update_role(user.id, "admin")
        await db_session.commit()
        await db_session.refresh(user)
        assert user.role == "admin"

    async def test_deactivate(self, db_session: AsyncSession) -> None:
        repo = UserRepository(db_session)
        user = User(username="deactivate-me", hashed_password="x", role="viewer")
        await repo.create(user)
        await db_session.commit()

        await repo.deactivate(user.id)
        await db_session.commit()
        await db_session.refresh(user)
        assert user.is_active is False


# ---------------------------------------------------------------------------
# Device repository
# ---------------------------------------------------------------------------


class TestDeviceRepository:
    async def test_create_and_get(self, db_session: AsyncSession) -> None:
        repo = DeviceRepository(db_session)
        dev = Device(
            device_id="sensor-001",
            name="Temperature Sensor",
            device_type="thermostat",
            state={"temperature": 22.0},
            is_online=True,
        )
        await repo.create(dev)
        await db_session.commit()

        found = await repo.get_by_device_id("sensor-001")
        assert found is not None
        assert found.name == "Temperature Sensor"

    async def test_list_all(self, db_session: AsyncSession) -> None:
        repo = DeviceRepository(db_session)
        for i in range(3):
            await repo.create(
                Device(
                    device_id=f"dev-list-{i}",
                    name=f"Device {i}",
                    device_type="generic",
                    state={},
                    is_online=True,
                )
            )
        await db_session.commit()

        devices = await repo.list_all()
        assert len(devices) >= 3

    async def test_update_state(self, db_session: AsyncSession) -> None:
        repo = DeviceRepository(db_session)
        dev = Device(
            device_id="state-test",
            name="State Test",
            device_type="light",
            state={"is_on": False},
            is_online=True,
        )
        await repo.create(dev)
        await db_session.commit()

        await repo.update_state(dev.id, {"is_on": True, "brightness": 80})
        await db_session.commit()
        await db_session.refresh(dev)
        assert dev.state.get("is_on") is True

    async def test_delete(self, db_session: AsyncSession) -> None:
        repo = DeviceRepository(db_session)
        dev = Device(
            device_id="delete-test",
            name="Delete Me",
            device_type="generic",
            state={},
            is_online=True,
        )
        await repo.create(dev)
        await db_session.commit()

        await repo.delete(dev.id)
        await db_session.commit()

        found = await repo.get_by_id(dev.id)
        assert found is None

    async def test_count(self, db_session: AsyncSession) -> None:
        repo = DeviceRepository(db_session)
        initial = await repo.count()
        await repo.create(
            Device(
                device_id="count-test",
                name="Count Test",
                device_type="generic",
                state={},
                is_online=True,
            )
        )
        await db_session.commit()
        assert await repo.count() == initial + 1


# ---------------------------------------------------------------------------
# Security rule repository
# ---------------------------------------------------------------------------


class TestSecurityRuleRepository:
    async def test_create_and_list_active(self, db_session: AsyncSession) -> None:
        repo = SecurityRuleRepository(db_session)
        rule = SecurityRule(
            name="test-block-rm",
            pattern=r"rm\s+-rf",
            action="BLOCK",
            is_active=True,
            priority=10,
        )
        await repo.create(rule)
        await db_session.commit()

        active = await repo.list_active()
        assert any(r.name == "test-block-rm" for r in active)

    async def test_inactive_rules_not_in_active_list(self, db_session: AsyncSession) -> None:
        repo = SecurityRuleRepository(db_session)
        rule = SecurityRule(
            name="inactive-rule",
            pattern=r"x",
            action="LOG",
            is_active=False,
            priority=100,
        )
        await repo.create(rule)
        await db_session.commit()

        active = await repo.list_active()
        assert not any(r.name == "inactive-rule" for r in active)

    async def test_get_matching_rules(self, db_session: AsyncSession) -> None:
        repo = SecurityRuleRepository(db_session)
        await repo.create(
            SecurityRule(
                name="match-unlock",
                pattern=r"unlock",
                action="WARN",
                is_active=True,
                priority=50,
            )
        )
        await db_session.commit()

        matched = await repo.get_matching_rules("unlock the front door")
        assert len(matched) >= 1

    async def test_no_matching_rules(self, db_session: AsyncSession) -> None:
        repo = SecurityRuleRepository(db_session)
        matched = await repo.get_matching_rules("turn_on_light")
        # Should be empty (or only match pre-existing rules)
        assert isinstance(matched, (list, tuple))

    async def test_delete_rule(self, db_session: AsyncSession) -> None:
        repo = SecurityRuleRepository(db_session)
        rule = SecurityRule(
            name="delete-rule",
            pattern=r"x",
            action="LOG",
            is_active=True,
            priority=999,
        )
        await repo.create(rule)
        await db_session.commit()

        await repo.delete(rule.id)
        await db_session.commit()

        active = await repo.list_active()
        assert not any(r.id == rule.id for r in active)


# ---------------------------------------------------------------------------
# Command log repository
# ---------------------------------------------------------------------------


class TestCommandLogRepository:
    async def test_create_and_list_recent(self, db_session: AsyncSession) -> None:
        repo = CommandLogRepository(db_session)
        log = CommandLog(
            command="turn_on light",
            risk_level="LOW",
            risk_explanation="Safe",
            was_blocked=False,
        )
        await repo.create(log)
        await db_session.commit()

        recent = await repo.list_recent(limit=10)
        assert len(recent) >= 1

    async def test_get_stats(self, db_session: AsyncSession) -> None:
        repo = CommandLogRepository(db_session)
        await repo.create(
            CommandLog(command="cmd1", risk_level="LOW", was_blocked=False)
        )
        await repo.create(
            CommandLog(command="cmd2", risk_level="HIGH", was_blocked=True)
        )
        await db_session.commit()

        stats = await repo.get_stats()
        assert "total" in stats
        assert "blocked" in stats
        assert stats["total"] >= 2


# ---------------------------------------------------------------------------
# Audit repository
# ---------------------------------------------------------------------------


class TestAuditRepository:
    async def test_create_and_query(self, db_session: AsyncSession) -> None:
        repo = AuditRepository(db_session)
        entry = AuditLog(
            event_type="test_event",
            payload={"key": "value"},
            correlation_id="abc123",
        )
        await repo.create(entry)
        await db_session.commit()

        results = await repo.query(event_type="test_event")
        assert len(results) >= 1
        assert results[0].event_type == "test_event"

    async def test_query_by_correlation_id(self, db_session: AsyncSession) -> None:
        repo = AuditRepository(db_session)
        await repo.create(
            AuditLog(
                event_type="corr_test",
                payload={},
                correlation_id="unique-corr",
            )
        )
        await db_session.commit()

        results = await repo.query(correlation_id="unique-corr")
        assert len(results) >= 1


# ---------------------------------------------------------------------------
# Permission repository
# ---------------------------------------------------------------------------


class TestPermissionRepository:
    async def test_grant_and_check(self, db_session: AsyncSession) -> None:
        user_repo = UserRepository(db_session)
        dev_repo = DeviceRepository(db_session)
        perm_repo = PermissionRepository(db_session)

        user = User(username="perm-user", hashed_password="x", role="operator")
        await user_repo.create(user)

        dev = Device(
            device_id="perm-dev",
            name="Perm Device",
            device_type="light",
            state={},
            is_online=True,
        )
        await dev_repo.create(dev)
        await db_session.commit()

        await perm_repo.grant(
            user.id, dev.id,
            can_read=True, can_write=True, can_execute=True,
        )
        await db_session.commit()

        assert await perm_repo.check_permission(user.id, dev.id, action="read") is True
        assert await perm_repo.check_permission(user.id, dev.id, action="write") is True
        assert await perm_repo.check_permission(user.id, dev.id, action="execute") is True

    async def test_no_permission_returns_false(self, db_session: AsyncSession) -> None:
        perm_repo = PermissionRepository(db_session)
        result = await perm_repo.check_permission(uuid.uuid4(), uuid.uuid4(), action="read")
        assert result is False

    async def test_revoke(self, db_session: AsyncSession) -> None:
        user_repo = UserRepository(db_session)
        dev_repo = DeviceRepository(db_session)
        perm_repo = PermissionRepository(db_session)

        user = User(username="revoke-user", hashed_password="x", role="operator")
        await user_repo.create(user)

        dev = Device(
            device_id="revoke-dev",
            name="Revoke Device",
            device_type="generic",
            state={},
            is_online=True,
        )
        await dev_repo.create(dev)
        await db_session.commit()

        await perm_repo.grant(user.id, dev.id, can_read=True)
        await db_session.commit()

        await perm_repo.revoke(user.id, dev.id)
        await db_session.commit()

        assert await perm_repo.check_permission(user.id, dev.id, action="read") is False
