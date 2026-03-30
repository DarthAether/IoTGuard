"""Rule-based analysis engine.

Evaluates security rules loaded from the database against an incoming
command.  Each matching rule contributes a violation entry and, depending
on its action (``BLOCK`` / ``WARN`` / ``LOG``), may mark the overall
result as blocked.
"""

from __future__ import annotations

import re
from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from iotguard.analysis.models import AnalysisResult, RiskLevel
from iotguard.db.repositories import SecurityRuleRepository

logger = structlog.get_logger(__name__)


class RuleBasedEngine:
    """Evaluate commands against :class:`SecurityRule` patterns from the DB."""

    def __init__(self, session: AsyncSession) -> None:
        self._rule_repo = SecurityRuleRepository(session)

    async def analyze(
        self,
        command: str,
        device_context: dict[str, Any],
    ) -> AnalysisResult:
        """Match *command* against all active rules and return a result.

        The returned :attr:`AnalysisResult.was_blocked` is ``True`` if any
        matching rule has ``action == 'BLOCK'``.
        """
        rules = await self._rule_repo.get_matching_rules(command)

        if not rules:
            return AnalysisResult(
                risk_level=RiskLevel.NONE,
                explanation="No security rules matched this command.",
                suggestions=[],
                safe_alternatives=[],
                rule_violations=[],
                was_blocked=False,
            )

        violations: list[str] = []
        was_blocked = False
        highest_risk = RiskLevel.LOW

        for rule in rules:
            action = rule.action.upper()
            violations.append(
                f"[{action}] Rule '{rule.name}': {rule.description or rule.pattern}"
            )
            if action == "BLOCK":
                was_blocked = True
                highest_risk = RiskLevel.CRITICAL
            elif action == "WARN" and highest_risk.value in ("NONE", "LOW"):
                highest_risk = RiskLevel.HIGH

        explanation = (
            f"Command matched {len(violations)} security rule(s). "
            + ("BLOCKED by policy." if was_blocked else "Warnings raised.")
        )

        return AnalysisResult(
            risk_level=highest_risk,
            explanation=explanation,
            suggestions=["Review the matched rules and adjust if needed."],
            safe_alternatives=[],
            rule_violations=violations,
            was_blocked=was_blocked,
        )
