#!/usr/bin/env python3
"""Seed the database with an admin user, default devices, and sample security rules.

Usage:
    python scripts/seed_db.py

Requires a running PostgreSQL instance configured via environment variables
(or .env file).
"""

from __future__ import annotations

import asyncio
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path

# Ensure the project root is on sys.path so imports work when running as a script
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from sqlalchemy.ext.asyncio import AsyncSession

from iotguard.core.config import get_settings
from iotguard.core.security import hash_password
from iotguard.db.engine import dispose_engine, get_session_factory
from iotguard.db.models import Base, Device, SecurityRule, User


async def seed() -> None:
    settings = get_settings()
    factory = get_session_factory(settings.database)

    # Create tables if they don't exist
    from iotguard.db.engine import get_engine

    engine = get_engine(settings.database)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with factory() as session:
        await _seed_users(session)
        await _seed_devices(session)
        await _seed_security_rules(session)
        await session.commit()

    await dispose_engine()
    print("Database seeded successfully.")


async def _seed_users(session: AsyncSession) -> None:
    """Create the default admin user if it does not exist."""
    from iotguard.db.repositories import UserRepository

    repo = UserRepository(session)
    existing = await repo.get_by_username("admin")
    if existing is not None:
        print("  [skip] Admin user already exists.")
        return

    admin = User(
        id=uuid.uuid4(),
        username="admin",
        hashed_password=hash_password("admin"),
        role="admin",
        is_active=True,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    await repo.create(admin)
    print(f"  [created] Admin user (id={admin.id})")

    # Create an operator user
    operator = User(
        id=uuid.uuid4(),
        username="operator",
        hashed_password=hash_password("operator"),
        role="operator",
        is_active=True,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    await repo.create(operator)
    print(f"  [created] Operator user (id={operator.id})")

    # Create a viewer user
    viewer = User(
        id=uuid.uuid4(),
        username="viewer",
        hashed_password=hash_password("viewer"),
        role="viewer",
        is_active=True,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    await repo.create(viewer)
    print(f"  [created] Viewer user (id={viewer.id})")


async def _seed_devices(session: AsyncSession) -> None:
    """Create default IoT devices."""
    from iotguard.db.repositories import DeviceRepository

    repo = DeviceRepository(session)

    devices = [
        {
            "device_id": "door_lock_01",
            "name": "Front Door Lock",
            "device_type": "door_lock",
            "state": {"is_locked": True},
        },
        {
            "device_id": "camera_01",
            "name": "Security Camera (Living Room)",
            "device_type": "camera",
            "state": {"recording": False, "is_on": True},
        },
        {
            "device_id": "speaker_01",
            "name": "Smart Speaker (Kitchen)",
            "device_type": "speaker",
            "state": {"is_on": False, "volume": 50},
        },
        {
            "device_id": "thermostat_01",
            "name": "Main Thermostat",
            "device_type": "thermostat",
            "state": {"temperature": 22.0, "is_on": True},
        },
        {
            "device_id": "light_01",
            "name": "Living Room Light",
            "device_type": "light",
            "state": {"is_on": False, "brightness": 100},
        },
    ]

    for dev_data in devices:
        existing = await repo.get_by_device_id(dev_data["device_id"])
        if existing is not None:
            print(f"  [skip] Device '{dev_data['device_id']}' already exists.")
            continue

        device = Device(
            id=uuid.uuid4(),
            device_id=dev_data["device_id"],
            name=dev_data["name"],
            device_type=dev_data["device_type"],
            state=dev_data["state"],
            is_online=True,
            last_seen=datetime.now(UTC),
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        session.add(device)
        print(f"  [created] Device '{device.device_id}'")


async def _seed_security_rules(session: AsyncSession) -> None:
    """Create sample security rules."""
    from iotguard.db.repositories import SecurityRuleRepository

    repo = SecurityRuleRepository(session)
    existing = await repo.list_all()
    existing_names = {r.name for r in existing}

    rules = [
        {
            "name": "block-destructive-commands",
            "description": "Block commands that could cause data loss or system damage.",
            "pattern": r"(rm\s+-rf|format|fdisk|mkfs|dd\s+if=)",
            "action": "BLOCK",
            "priority": 1,
        },
        {
            "name": "block-firmware-flash",
            "description": "Block unauthorized firmware flashing attempts.",
            "pattern": r"(flash_firmware|update_firmware|ota_update)",
            "action": "BLOCK",
            "priority": 5,
        },
        {
            "name": "warn-unlock-commands",
            "description": "Warn on door unlock commands for audit trail.",
            "pattern": r"unlock",
            "action": "WARN",
            "priority": 10,
        },
        {
            "name": "warn-high-temperature",
            "description": "Warn when temperature is set above 35 degrees.",
            "pattern": r"set_temperature\s+(3[5-9]|[4-9]\d|\d{3,})",
            "action": "WARN",
            "priority": 20,
        },
        {
            "name": "log-recording-commands",
            "description": "Log all recording-related commands for audit.",
            "pattern": r"(start_recording|stop_recording|record)",
            "action": "LOG",
            "priority": 50,
        },
        {
            "name": "block-network-reconfig",
            "description": "Block attempts to reconfigure device network settings.",
            "pattern": r"(set_wifi|change_ssid|set_proxy|set_dns)",
            "action": "BLOCK",
            "priority": 3,
        },
    ]

    for rule_data in rules:
        if rule_data["name"] in existing_names:
            print(f"  [skip] Rule '{rule_data['name']}' already exists.")
            continue

        rule = SecurityRule(
            id=uuid.uuid4(),
            name=rule_data["name"],
            description=rule_data["description"],
            pattern=rule_data["pattern"],
            action=rule_data["action"],
            is_active=True,
            priority=rule_data["priority"],
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        session.add(rule)
        print(f"  [created] Rule '{rule.name}' ({rule.action}, priority={rule.priority})")


if __name__ == "__main__":
    print("Seeding IoTGuard database...")
    asyncio.run(seed())
