"""Unit tests for the GeminiAnalysisEngine -- response parsing, circuit breaker, caching."""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import SecretStr

from iotguard.analysis.engines.gemini import GeminiAnalysisEngine
from iotguard.analysis.models import AnalysisResult, RiskLevel
from iotguard.core.circuit_breaker import CircuitOpenError
from iotguard.core.config import GeminiSettings, RedisSettings
from iotguard.core.exceptions import LLMError


_GEMINI_SETTINGS = GeminiSettings(
    api_key=SecretStr("test-key"),
    model_name="gemini-1.5-flash",
    temperature=0.2,
    max_tokens=2048,
)


class TestResponseParsing:
    """Test _parse_response with various LLM output formats."""

    def test_valid_json_response(self) -> None:
        raw = json.dumps({
            "risk_level": "HIGH",
            "explanation": "Dangerous command detected.",
            "suggestions": ["Use a safer alternative."],
            "safe_alternatives": ["turn_off_safely"],
        })
        result = GeminiAnalysisEngine._parse_response(raw)
        assert result.risk_level == RiskLevel.HIGH
        assert result.explanation == "Dangerous command detected."
        assert len(result.suggestions) == 1
        assert len(result.safe_alternatives) == 1

    def test_json_with_markdown_fences(self) -> None:
        raw = '```json\n{"risk_level": "LOW", "explanation": "safe"}\n```'
        result = GeminiAnalysisEngine._parse_response(raw)
        assert result.risk_level == RiskLevel.LOW

    def test_json_with_bare_fences(self) -> None:
        raw = '```\n{"risk_level": "MEDIUM", "explanation": "moderate"}\n```'
        result = GeminiAnalysisEngine._parse_response(raw)
        assert result.risk_level == RiskLevel.MEDIUM

    def test_invalid_json_raises_llm_error(self) -> None:
        with pytest.raises(LLMError, match="parse"):
            GeminiAnalysisEngine._parse_response("not json at all")

    def test_unknown_risk_level_defaults_to_medium(self) -> None:
        raw = json.dumps({
            "risk_level": "UNKNOWN_LEVEL",
            "explanation": "test",
        })
        result = GeminiAnalysisEngine._parse_response(raw)
        assert result.risk_level == RiskLevel.MEDIUM

    def test_missing_fields_use_defaults(self) -> None:
        raw = json.dumps({"risk_level": "NONE"})
        result = GeminiAnalysisEngine._parse_response(raw)
        assert result.explanation == ""
        assert result.suggestions == []
        assert result.safe_alternatives == []

    def test_lowercase_risk_level_handled(self) -> None:
        raw = json.dumps({"risk_level": "critical", "explanation": "bad"})
        result = GeminiAnalysisEngine._parse_response(raw)
        assert result.risk_level == RiskLevel.CRITICAL

    def test_was_blocked_is_always_false(self) -> None:
        """The LLM engine never sets was_blocked -- that's the rule engine's job."""
        raw = json.dumps({"risk_level": "HIGH", "explanation": "x"})
        result = GeminiAnalysisEngine._parse_response(raw)
        assert result.was_blocked is False

    def test_rule_violations_empty_from_llm(self) -> None:
        raw = json.dumps({"risk_level": "LOW", "explanation": "ok"})
        result = GeminiAnalysisEngine._parse_response(raw)
        assert result.rule_violations == []


class TestCircuitBreakerIntegration:
    """The engine uses a circuit breaker for Gemini calls."""

    async def test_no_api_key_raises_llm_error(self) -> None:
        settings = GeminiSettings(api_key=SecretStr(""))
        engine = GeminiAnalysisEngine(settings)
        with pytest.raises(LLMError, match="API key"):
            await engine.analyze("test", {"device_id": "d1"})

    async def test_circuit_breaker_exists(self) -> None:
        engine = GeminiAnalysisEngine(_GEMINI_SETTINGS)
        assert engine._breaker is not None
        assert engine._breaker.name == "gemini"


class TestCaching:
    """The engine caches results in Redis when available."""

    def test_cache_key_deterministic(self) -> None:
        engine = GeminiAnalysisEngine(_GEMINI_SETTINGS)
        k1 = engine._cache_key("cmd1", {"device_id": "d1"})
        k2 = engine._cache_key("cmd1", {"device_id": "d1"})
        assert k1 == k2

    def test_cache_key_varies_by_command(self) -> None:
        engine = GeminiAnalysisEngine(_GEMINI_SETTINGS)
        k1 = engine._cache_key("cmd1", {"device_id": "d1"})
        k2 = engine._cache_key("cmd2", {"device_id": "d1"})
        assert k1 != k2

    def test_cache_key_varies_by_context(self) -> None:
        engine = GeminiAnalysisEngine(_GEMINI_SETTINGS)
        k1 = engine._cache_key("cmd", {"device_id": "d1"})
        k2 = engine._cache_key("cmd", {"device_id": "d2"})
        assert k1 != k2

    async def test_cache_miss_returns_none(self) -> None:
        engine = GeminiAnalysisEngine(_GEMINI_SETTINGS)
        result = await engine._get_cached("nonexistent")
        assert result is None

    async def test_set_and_get_cached_with_mock_redis(self) -> None:
        mock_redis = AsyncMock()
        cache_data: dict[str, str] = {}

        async def mock_set(key: str, value: str, ex: int = 0) -> None:
            cache_data[key] = value

        async def mock_get(key: str) -> str | None:
            return cache_data.get(key)

        mock_redis.set = mock_set
        mock_redis.get = mock_get

        engine = GeminiAnalysisEngine(_GEMINI_SETTINGS, redis_client=mock_redis)
        test_result = AnalysisResult(
            risk_level=RiskLevel.LOW,
            explanation="cached result",
        )

        key = "test:cache:key"
        await engine._set_cached(key, test_result)
        retrieved = await engine._get_cached(key)

        assert retrieved is not None
        assert retrieved.risk_level == RiskLevel.LOW
        assert retrieved.explanation == "cached result"

    async def test_cache_error_does_not_raise(self) -> None:
        """Cache errors should be silently caught."""
        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(side_effect=ConnectionError("redis down"))

        engine = GeminiAnalysisEngine(_GEMINI_SETTINGS, redis_client=mock_redis)
        result = await engine._get_cached("some-key")
        assert result is None
