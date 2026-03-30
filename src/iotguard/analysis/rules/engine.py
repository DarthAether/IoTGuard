"""Security rule engine -- loads rules from the database and evaluates them.

Rules are ordered by priority (ascending -- lower number = higher priority)
and evaluated sequentially.  A ``BLOCK`` action on any rule causes the
entire command to be rejected.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Sequence

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from iotguard.db.models import SecurityRule
from iotguard.db.repositories import SecurityRuleRepository

logger = structlog.get_logger(__name__)


@dataclass(frozen=True, slots=True)
class RuleMatch:
    """Represents a single rule that matched a command."""

    rule_name: str
    pattern: str
    action: str  # BLOCK | WARN | LOG
    description: str
    priority: int


@dataclass(slots=True)
class RuleEvaluationResult:
    """Aggregated result of evaluating all rules against a command."""

    matches: list[RuleMatch] = field(default_factory=list)
    blocked: bool = False
    block_reason: str = ""

    @property
    def has_matches(self) -> bool:
        return len(self.matches) > 0

    @property
    def warnings(self) -> list[RuleMatch]:
        return [m for m in self.matches if m.action == "WARN"]

    @property
    def log_only(self) -> list[RuleMatch]:
        return [m for m in self.matches if m.action == "LOG"]


class SecurityRuleEngine:
    """Load rules from the DB and match them against commands."""

    def __init__(self, session: AsyncSession) -> None:
        self._repo = SecurityRuleRepository(session)
        self._cached_rules: list[SecurityRule] | None = None

    async def load_rules(self, *, force: bool = False) -> Sequence[SecurityRule]:
        """Fetch active rules from the database, caching them for the session.

        Pass ``force=True`` to bypass the cache and reload.
        """
        if self._cached_rules is None or force:
            self._cached_rules = list(await self._repo.list_active())
            logger.info("rules_loaded", count=len(self._cached_rules))
        return self._cached_rules

    async def evaluate(self, command: str) -> RuleEvaluationResult:
        """Match *command* against all active rules and return the result.

        Rules are evaluated in priority order.  If multiple rules match,
        all matches are recorded but the first ``BLOCK`` action encountered
        determines the overall blocked status.
        """
        rules = await self.load_rules()
        result = RuleEvaluationResult()

        for rule in rules:
            try:
                if not re.search(rule.pattern, command, re.IGNORECASE):
                    continue
            except re.error:
                logger.warning(
                    "invalid_rule_pattern",
                    rule=rule.name,
                    pattern=rule.pattern,
                )
                continue

            match = RuleMatch(
                rule_name=rule.name,
                pattern=rule.pattern,
                action=rule.action.upper(),
                description=rule.description or "",
                priority=rule.priority,
            )
            result.matches.append(match)

            if match.action == "BLOCK" and not result.blocked:
                result.blocked = True
                result.block_reason = (
                    f"Blocked by rule '{rule.name}' (priority {rule.priority}): "
                    f"{rule.description or rule.pattern}"
                )

            logger.info(
                "rule_matched",
                rule=rule.name,
                action=match.action,
                command=command[:100],
            )

        return result

    def invalidate_cache(self) -> None:
        """Clear the in-memory rule cache so the next evaluation reloads."""
        self._cached_rules = None
