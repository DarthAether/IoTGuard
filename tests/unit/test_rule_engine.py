"""Unit tests for the SecurityRuleEngine -- pattern matching, priority, actions."""

from __future__ import annotations

import uuid
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from iotguard.analysis.rules.engine import RuleEvaluationResult, RuleMatch, SecurityRuleEngine
from iotguard.db.models import SecurityRule


def _rule(
    name: str,
    pattern: str,
    action: str = "BLOCK",
    priority: int = 100,
    is_active: bool = True,
    description: str = "",
) -> SecurityRule:
    """Helper to build a SecurityRule without touching the DB."""
    r = SecurityRule.__new__(SecurityRule)
    r.id = uuid.uuid4()
    r.name = name
    r.pattern = pattern
    r.action = action
    r.priority = priority
    r.is_active = is_active
    r.description = description or name
    return r


class TestPatternMatching:
    """Rules match commands via regex patterns."""

    async def test_simple_pattern_match(self) -> None:
        mock_repo = AsyncMock()
        mock_repo.list_active = AsyncMock(return_value=[
            _rule("no-rm", r"rm\s+-rf", "BLOCK", 10),
        ])

        engine = SecurityRuleEngine.__new__(SecurityRuleEngine)
        engine._repo = mock_repo
        engine._cached_rules = None

        result = await engine.evaluate("rm -rf /tmp")
        assert result.has_matches
        assert result.blocked is True

    async def test_case_insensitive_matching(self) -> None:
        mock_repo = AsyncMock()
        mock_repo.list_active = AsyncMock(return_value=[
            _rule("no-format", r"FORMAT", "BLOCK", 10),
        ])

        engine = SecurityRuleEngine.__new__(SecurityRuleEngine)
        engine._repo = mock_repo
        engine._cached_rules = None

        result = await engine.evaluate("format disk_c")
        assert result.has_matches

    async def test_no_match_returns_empty(self) -> None:
        mock_repo = AsyncMock()
        mock_repo.list_active = AsyncMock(return_value=[
            _rule("no-rm", r"rm\s+-rf", "BLOCK", 10),
        ])

        engine = SecurityRuleEngine.__new__(SecurityRuleEngine)
        engine._repo = mock_repo
        engine._cached_rules = None

        result = await engine.evaluate("turn_on light")
        assert not result.has_matches
        assert result.blocked is False

    async def test_invalid_regex_pattern_skipped(self) -> None:
        mock_repo = AsyncMock()
        mock_repo.list_active = AsyncMock(return_value=[
            _rule("bad-regex", r"[invalid(", "BLOCK", 10),
            _rule("good-rule", r"unlock", "WARN", 20),
        ])

        engine = SecurityRuleEngine.__new__(SecurityRuleEngine)
        engine._repo = mock_repo
        engine._cached_rules = None

        result = await engine.evaluate("unlock door")
        # Bad regex skipped, good rule matches
        assert len(result.matches) == 1
        assert result.matches[0].rule_name == "good-rule"


class TestPriorityOrdering:
    """Rules are evaluated in priority order (lower number = higher priority)."""

    async def test_multiple_rules_match_in_priority_order(self) -> None:
        mock_repo = AsyncMock()
        mock_repo.list_active = AsyncMock(return_value=[
            _rule("low-priority", r"door", "WARN", 200),
            _rule("high-priority", r"door", "BLOCK", 10),
            _rule("mid-priority", r"door", "LOG", 100),
        ])

        engine = SecurityRuleEngine.__new__(SecurityRuleEngine)
        engine._repo = mock_repo
        engine._cached_rules = None

        result = await engine.evaluate("unlock door")
        assert len(result.matches) == 3
        # The repo returns them sorted by priority; the engine evaluates in that order
        # The first BLOCK encountered sets the block reason
        assert result.blocked is True


class TestActions:
    """BLOCK, WARN, and LOG actions produce correct results."""

    async def test_block_action_sets_blocked(self) -> None:
        mock_repo = AsyncMock()
        mock_repo.list_active = AsyncMock(return_value=[
            _rule("block-rule", r"dangerous", "BLOCK", 10),
        ])

        engine = SecurityRuleEngine.__new__(SecurityRuleEngine)
        engine._repo = mock_repo
        engine._cached_rules = None

        result = await engine.evaluate("dangerous command")
        assert result.blocked is True
        assert "block-rule" in result.block_reason

    async def test_warn_action_does_not_block(self) -> None:
        mock_repo = AsyncMock()
        mock_repo.list_active = AsyncMock(return_value=[
            _rule("warn-rule", r"suspicious", "WARN", 10),
        ])

        engine = SecurityRuleEngine.__new__(SecurityRuleEngine)
        engine._repo = mock_repo
        engine._cached_rules = None

        result = await engine.evaluate("suspicious activity")
        assert not result.blocked
        assert len(result.warnings) == 1

    async def test_log_action_does_not_block(self) -> None:
        mock_repo = AsyncMock()
        mock_repo.list_active = AsyncMock(return_value=[
            _rule("log-rule", r"monitor", "LOG", 10),
        ])

        engine = SecurityRuleEngine.__new__(SecurityRuleEngine)
        engine._repo = mock_repo
        engine._cached_rules = None

        result = await engine.evaluate("monitor this")
        assert not result.blocked
        assert len(result.log_only) == 1

    async def test_mixed_actions(self) -> None:
        mock_repo = AsyncMock()
        mock_repo.list_active = AsyncMock(return_value=[
            _rule("log-it", r"cmd", "LOG", 30),
            _rule("warn-it", r"cmd", "WARN", 20),
            _rule("block-it", r"cmd", "BLOCK", 10),
        ])

        engine = SecurityRuleEngine.__new__(SecurityRuleEngine)
        engine._repo = mock_repo
        engine._cached_rules = None

        result = await engine.evaluate("cmd execute")
        assert result.blocked is True
        assert len(result.matches) == 3
        assert len(result.warnings) == 1
        assert len(result.log_only) == 1


class TestRuleCaching:
    """The engine caches rules and can invalidate the cache."""

    async def test_load_rules_caches(self) -> None:
        mock_repo = AsyncMock()
        mock_repo.list_active = AsyncMock(return_value=[
            _rule("r1", r"x", "BLOCK", 10),
        ])

        engine = SecurityRuleEngine.__new__(SecurityRuleEngine)
        engine._repo = mock_repo
        engine._cached_rules = None

        rules1 = await engine.load_rules()
        rules2 = await engine.load_rules()
        assert rules1 == rules2
        assert mock_repo.list_active.call_count == 1  # only loaded once

    async def test_force_reload(self) -> None:
        mock_repo = AsyncMock()
        mock_repo.list_active = AsyncMock(return_value=[])

        engine = SecurityRuleEngine.__new__(SecurityRuleEngine)
        engine._repo = mock_repo
        engine._cached_rules = None

        await engine.load_rules()
        await engine.load_rules(force=True)
        assert mock_repo.list_active.call_count == 2

    def test_invalidate_cache(self) -> None:
        engine = SecurityRuleEngine.__new__(SecurityRuleEngine)
        engine._cached_rules = [_rule("r", "x")]
        engine.invalidate_cache()
        assert engine._cached_rules is None
