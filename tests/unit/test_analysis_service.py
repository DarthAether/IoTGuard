"""Unit tests for the AnalysisService -- rules-first-then-LLM orchestration."""

from __future__ import annotations

import uuid
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from iotguard.analysis.models import AnalysisRequest, AnalysisResult, RiskLevel
from iotguard.analysis.service import AnalysisService
from iotguard.core.events import EventBus


class FakeRuleEngine:
    """Configurable rule engine stub."""

    def __init__(self, result: AnalysisResult | None = None) -> None:
        self.result = result or AnalysisResult(
            risk_level=RiskLevel.NONE,
            explanation="No rules matched.",
            was_blocked=False,
        )
        self.call_count = 0

    async def analyze(self, command: str, device_context: dict[str, Any]) -> AnalysisResult:
        self.call_count += 1
        return self.result


class FakeLLMEngine:
    """Configurable LLM engine stub."""

    def __init__(
        self,
        result: AnalysisResult | None = None,
        *,
        should_fail: bool = False,
    ) -> None:
        self.result = result or AnalysisResult(
            risk_level=RiskLevel.LOW,
            explanation="LLM says safe.",
            suggestions=["All good."],
        )
        self.should_fail = should_fail
        self.call_count = 0

    async def analyze(self, command: str, device_context: dict[str, Any]) -> AnalysisResult:
        self.call_count += 1
        if self.should_fail:
            raise RuntimeError("LLM unavailable")
        return self.result


class TestRulesFirstThenLLM:
    """The service evaluates rules first, then calls the LLM if not blocked."""

    async def test_rule_engine_runs_first(
        self,
        db_session: Any,
        event_bus: EventBus,
    ) -> None:
        """Both engines are called when rules don't block."""
        rule_engine = FakeRuleEngine()
        llm_engine = FakeLLMEngine()

        svc = AnalysisService.__new__(AnalysisService)
        svc._session = db_session
        svc._event_bus = event_bus
        svc._rule_engine = rule_engine
        svc._llm_engine = llm_engine
        svc._log_repo = AsyncMock()
        svc._log_repo.create = AsyncMock()

        req = AnalysisRequest(command="turn_on light", device_id="dev-1")
        result = await svc.analyze(req)

        assert rule_engine.call_count == 1
        assert llm_engine.call_count == 1
        assert result.was_blocked is False

    async def test_llm_skipped_when_rules_block(
        self,
        db_session: Any,
        event_bus: EventBus,
    ) -> None:
        """When rules block, the LLM should not be called."""
        blocked_result = AnalysisResult(
            risk_level=RiskLevel.CRITICAL,
            explanation="Blocked by rule.",
            was_blocked=True,
            rule_violations=["[BLOCK] Rule 'no-rm': dangerous pattern"],
        )
        rule_engine = FakeRuleEngine(result=blocked_result)
        llm_engine = FakeLLMEngine()

        svc = AnalysisService.__new__(AnalysisService)
        svc._session = db_session
        svc._event_bus = event_bus
        svc._rule_engine = rule_engine
        svc._llm_engine = llm_engine
        svc._log_repo = AsyncMock()
        svc._log_repo.create = AsyncMock()

        req = AnalysisRequest(command="rm -rf /", device_id="dev-1")
        result = await svc.analyze(req)

        assert rule_engine.call_count == 1
        assert llm_engine.call_count == 0
        assert result.was_blocked is True
        assert result.risk_level == RiskLevel.CRITICAL


class TestRiskLevelMapping:
    """Merged results take the higher risk level."""

    async def test_higher_risk_from_llm_wins(
        self,
        db_session: Any,
        event_bus: EventBus,
    ) -> None:
        rule_engine = FakeRuleEngine(
            AnalysisResult(risk_level=RiskLevel.LOW, explanation="Rule says low.")
        )
        llm_engine = FakeLLMEngine(
            AnalysisResult(risk_level=RiskLevel.HIGH, explanation="LLM says high.")
        )

        svc = AnalysisService.__new__(AnalysisService)
        svc._session = db_session
        svc._event_bus = event_bus
        svc._rule_engine = rule_engine
        svc._llm_engine = llm_engine
        svc._log_repo = AsyncMock()
        svc._log_repo.create = AsyncMock()

        req = AnalysisRequest(command="set_temperature 999", device_id="dev-1")
        result = await svc.analyze(req)

        assert result.risk_level == RiskLevel.HIGH

    async def test_higher_risk_from_rules_wins(
        self,
        db_session: Any,
        event_bus: EventBus,
    ) -> None:
        rule_engine = FakeRuleEngine(
            AnalysisResult(
                risk_level=RiskLevel.HIGH,
                explanation="Rule warning.",
                rule_violations=["[WARN] high-temp"],
            )
        )
        llm_engine = FakeLLMEngine(
            AnalysisResult(risk_level=RiskLevel.LOW, explanation="LLM says low.")
        )

        svc = AnalysisService.__new__(AnalysisService)
        svc._session = db_session
        svc._event_bus = event_bus
        svc._rule_engine = rule_engine
        svc._llm_engine = llm_engine
        svc._log_repo = AsyncMock()
        svc._log_repo.create = AsyncMock()

        req = AnalysisRequest(command="x", device_id="dev-1")
        result = await svc.analyze(req)

        assert result.risk_level == RiskLevel.HIGH


class TestBlockingLogic:
    """Blocked commands produce the correct result shape."""

    async def test_blocked_result_shape(
        self,
        db_session: Any,
        event_bus: EventBus,
    ) -> None:
        blocked = AnalysisResult(
            risk_level=RiskLevel.CRITICAL,
            explanation="Blocked.",
            was_blocked=True,
            rule_violations=["[BLOCK] dangerous"],
        )
        rule_engine = FakeRuleEngine(result=blocked)
        llm_engine = FakeLLMEngine()

        svc = AnalysisService.__new__(AnalysisService)
        svc._session = db_session
        svc._event_bus = event_bus
        svc._rule_engine = rule_engine
        svc._llm_engine = llm_engine
        svc._log_repo = AsyncMock()
        svc._log_repo.create = AsyncMock()

        req = AnalysisRequest(command="rm -rf /", device_id="dev-1")
        result = await svc.analyze(req)

        assert result.was_blocked is True
        assert len(result.rule_violations) > 0
        assert result.risk_level == RiskLevel.CRITICAL


class TestLLMFallback:
    """When LLM fails, service falls back to rule-only result."""

    async def test_llm_failure_falls_back_to_rules(
        self,
        db_session: Any,
        event_bus: EventBus,
    ) -> None:
        rule_engine = FakeRuleEngine(
            AnalysisResult(
                risk_level=RiskLevel.MEDIUM,
                explanation="Rule matched.",
                rule_violations=["[WARN] suspicious"],
            )
        )
        llm_engine = FakeLLMEngine(should_fail=True)

        svc = AnalysisService.__new__(AnalysisService)
        svc._session = db_session
        svc._event_bus = event_bus
        svc._rule_engine = rule_engine
        svc._llm_engine = llm_engine
        svc._log_repo = AsyncMock()
        svc._log_repo.create = AsyncMock()

        req = AnalysisRequest(command="suspicious_cmd", device_id="dev-1")
        result = await svc.analyze(req)

        # Falls back to rule result since rules had violations
        assert result.risk_level == RiskLevel.MEDIUM


class TestMergeResults:
    """Test the static _merge_results helper."""

    def test_merge_combines_explanations(self) -> None:
        r1 = AnalysisResult(risk_level=RiskLevel.LOW, explanation="Rule ok")
        r2 = AnalysisResult(risk_level=RiskLevel.MEDIUM, explanation="LLM medium")
        merged = AnalysisService._merge_results(r1, r2)
        assert "Rule ok" in merged.explanation
        assert "LLM medium" in merged.explanation

    def test_merge_takes_higher_risk(self) -> None:
        r1 = AnalysisResult(risk_level=RiskLevel.LOW, explanation="")
        r2 = AnalysisResult(risk_level=RiskLevel.HIGH, explanation="")
        merged = AnalysisService._merge_results(r1, r2)
        assert merged.risk_level == RiskLevel.HIGH

    def test_merge_preserves_rule_violations(self) -> None:
        r1 = AnalysisResult(
            risk_level=RiskLevel.LOW,
            explanation="",
            rule_violations=["v1", "v2"],
        )
        r2 = AnalysisResult(risk_level=RiskLevel.LOW, explanation="")
        merged = AnalysisService._merge_results(r1, r2)
        assert merged.rule_violations == ["v1", "v2"]

    def test_merge_blocked_from_either_source(self) -> None:
        r1 = AnalysisResult(risk_level=RiskLevel.LOW, explanation="", was_blocked=True)
        r2 = AnalysisResult(risk_level=RiskLevel.LOW, explanation="", was_blocked=False)
        merged = AnalysisService._merge_results(r1, r2)
        assert merged.was_blocked is True
