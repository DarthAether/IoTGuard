"""Command analysis service -- orchestrates rule-based and LLM analysis.

The service checks security rules first; if the command is not blocked it
delegates to the Gemini LLM engine for deeper analysis.  Results from both
sources are merged, persisted to the command log, and published via the
event bus.
"""

from __future__ import annotations

import time
import uuid
from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from iotguard.analysis.engines.gemini import GeminiAnalysisEngine
from iotguard.analysis.engines.rule_based import RuleBasedEngine
from iotguard.analysis.models import AnalysisRequest, AnalysisResult, RiskLevel
from iotguard.core.config import GeminiSettings, RedisSettings
from iotguard.core.events import (
    AlertEvent,
    CommandAnalyzedEvent,
    EventBus,
    RuleViolationEvent,
)
from iotguard.core.exceptions import AnalysisError
from iotguard.db.models import CommandLog
from iotguard.db.repositories import CommandLogRepository

logger = structlog.get_logger(__name__)


class AnalysisService:
    """Orchestrate rule-based + LLM analysis for IoT commands."""

    def __init__(
        self,
        session: AsyncSession,
        gemini_settings: GeminiSettings,
        event_bus: EventBus,
        *,
        redis_settings: RedisSettings | None = None,
        redis_client: Any | None = None,
    ) -> None:
        self._session = session
        self._event_bus = event_bus
        self._log_repo = CommandLogRepository(session)

        # Engines
        self._rule_engine = RuleBasedEngine(session)
        self._llm_engine = GeminiAnalysisEngine(
            gemini_settings,
            redis_settings,
            redis_client=redis_client,
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def analyze(
        self,
        request: AnalysisRequest,
        *,
        user_id: uuid.UUID | None = None,
    ) -> AnalysisResult:
        """Run the full analysis pipeline and return a merged result."""
        start = time.monotonic()
        device_context: dict[str, Any] = {
            "device_id": request.device_id,
            **request.user_context,
        }

        # 1. Rule-based evaluation (always runs)
        rule_result = await self._rule_engine.analyze(
            request.command, device_context
        )

        # If rules already blocked the command, skip the LLM call
        if rule_result.was_blocked:
            merged = rule_result
        else:
            # 2. LLM analysis
            try:
                llm_result = await self._llm_engine.analyze(
                    request.command, device_context
                )
                merged = self._merge_results(rule_result, llm_result)
            except Exception as exc:
                logger.error("llm_analysis_failed", error=str(exc))
                # Fall back to rule-only result rather than failing entirely
                if rule_result.rule_violations:
                    merged = rule_result
                else:
                    raise AnalysisError(str(exc)) from exc

        # 3. Persist to command log
        log_entry = CommandLog(
            user_id=user_id,
            device_id=self._try_parse_uuid(request.device_id),
            command=request.command,
            risk_level=merged.risk_level.value,
            risk_explanation=merged.explanation,
            was_blocked=merged.was_blocked,
        )
        await self._log_repo.create(log_entry)

        elapsed = time.monotonic() - start
        logger.info(
            "command_analyzed",
            device_id=request.device_id,
            risk_level=merged.risk_level.value,
            blocked=merged.was_blocked,
            elapsed_s=round(elapsed, 3),
        )

        # 4. Publish domain events
        self._event_bus.publish_nowait(
            CommandAnalyzedEvent(
                device_id=request.device_id,
                command=request.command,
                risk_level=merged.risk_level.value,
                blocked=merged.was_blocked,
            )
        )

        if merged.rule_violations:
            for violation in merged.rule_violations:
                self._event_bus.publish_nowait(
                    RuleViolationEvent(
                        rule_name=violation,
                        command=request.command,
                        device_id=request.device_id,
                    )
                )

        if merged.risk_level in (RiskLevel.HIGH, RiskLevel.CRITICAL):
            self._event_bus.publish_nowait(
                AlertEvent(
                    severity=merged.risk_level.value,
                    message=f"High-risk command detected: {request.command[:120]}",
                    source="analysis_service",
                )
            )

        return merged

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _merge_results(
        rule_result: AnalysisResult,
        llm_result: AnalysisResult,
    ) -> AnalysisResult:
        """Combine rule-engine and LLM results, taking the higher risk."""
        risk_order = list(RiskLevel)
        rule_idx = risk_order.index(rule_result.risk_level)
        llm_idx = risk_order.index(llm_result.risk_level)
        higher = rule_result.risk_level if rule_idx >= llm_idx else llm_result.risk_level

        explanations: list[str] = []
        if rule_result.explanation:
            explanations.append(rule_result.explanation)
        if llm_result.explanation:
            explanations.append(llm_result.explanation)

        return AnalysisResult(
            risk_level=higher,
            explanation=" | ".join(explanations),
            suggestions=llm_result.suggestions + rule_result.suggestions,
            safe_alternatives=llm_result.safe_alternatives,
            rule_violations=rule_result.rule_violations,
            was_blocked=rule_result.was_blocked or llm_result.was_blocked,
        )

    @staticmethod
    def _try_parse_uuid(value: str) -> uuid.UUID | None:
        try:
            return uuid.UUID(value)
        except ValueError:
            return None
