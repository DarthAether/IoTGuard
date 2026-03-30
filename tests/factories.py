"""Test object factories for IoTGuard domain models.

Each ``make_*`` function returns a fully populated object with sensible
defaults.  All values can be overridden via keyword arguments.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from iotguard.analysis.models import AnalysisResult, RiskLevel
from iotguard.db.models import CommandLog, Device, SecurityRule, User


def make_analysis_result(
    *,
    risk_level: RiskLevel = RiskLevel.LOW,
    explanation: str = "Test analysis result",
    suggestions: list[str] | None = None,
    safe_alternatives: list[str] | None = None,
    rule_violations: list[str] | None = None,
    was_blocked: bool = False,
) -> AnalysisResult:
    """Create an AnalysisResult with sensible defaults."""
    return AnalysisResult(
        risk_level=risk_level,
        explanation=explanation,
        suggestions=suggestions or [],
        safe_alternatives=safe_alternatives or [],
        rule_violations=rule_violations or [],
        was_blocked=was_blocked,
    )


def make_device(
    *,
    device_id: str | None = None,
    name: str = "Test Device",
    device_type: str = "generic",
    state: dict[str, Any] | None = None,
    is_online: bool = True,
    last_seen: datetime | None = None,
) -> Device:
    """Create a Device ORM instance with sensible defaults."""
    return Device(
        id=uuid.uuid4(),
        device_id=device_id or f"test-device-{uuid.uuid4().hex[:8]}",
        name=name,
        device_type=device_type,
        state=state or {},
        is_online=is_online,
        last_seen=last_seen or datetime.now(UTC),
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )


def make_user(
    *,
    username: str | None = None,
    hashed_password: str = "$2b$12$LJ3m4ys2Kq9qY9qY9qY9quH7xH7xH7xH7xH7xH7xH7xH7xH7xH7",
    role: str = "admin",
    is_active: bool = True,
) -> User:
    """Create a User ORM instance with sensible defaults."""
    return User(
        id=uuid.uuid4(),
        username=username or f"testuser-{uuid.uuid4().hex[:8]}",
        hashed_password=hashed_password,
        role=role,
        is_active=is_active,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )


def make_security_rule(
    *,
    name: str | None = None,
    description: str = "Test security rule",
    pattern: str = r"rm\s+-rf",
    action: str = "BLOCK",
    is_active: bool = True,
    priority: int = 100,
) -> SecurityRule:
    """Create a SecurityRule ORM instance with sensible defaults."""
    return SecurityRule(
        id=uuid.uuid4(),
        name=name or f"test-rule-{uuid.uuid4().hex[:8]}",
        description=description,
        pattern=pattern,
        action=action,
        is_active=is_active,
        priority=priority,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )


def make_command_log(
    *,
    command: str = "turn_on light",
    risk_level: str = "LOW",
    risk_explanation: str = "Safe command",
    was_blocked: bool = False,
    device_id: uuid.UUID | None = None,
    user_id: uuid.UUID | None = None,
) -> CommandLog:
    """Create a CommandLog ORM instance with sensible defaults."""
    return CommandLog(
        id=uuid.uuid4(),
        timestamp=datetime.now(UTC),
        user_id=user_id,
        device_id=device_id,
        command=command,
        risk_level=risk_level,
        risk_explanation=risk_explanation,
        was_blocked=was_blocked,
        was_modified=False,
        modified_command=None,
    )
