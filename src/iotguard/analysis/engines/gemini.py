"""Gemini-backed analysis engine with circuit breaker and Redis caching.

This engine sends a structured prompt to the Gemini API, parses the JSON
response, and maps it to an :class:`~iotguard.analysis.models.AnalysisResult`.
Repeated identical commands are served from a short-lived Redis cache.
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any

import google.generativeai as genai
import structlog

from iotguard.analysis.models import AnalysisResult, RiskLevel
from iotguard.core.circuit_breaker import CircuitBreaker
from iotguard.core.config import GeminiSettings, RedisSettings
from iotguard.core.exceptions import LLMError

logger = structlog.get_logger(__name__)

_ANALYSIS_PROMPT = """\
You are an IoT security expert. Analyse the following IoT device command for
security risks.  Consider the device context provided.

**Device context:**
{device_context}

**Command:**
{command}

Respond ONLY with valid JSON (no markdown fences) containing exactly these keys:
{{
  "risk_level": "NONE" | "LOW" | "MEDIUM" | "HIGH" | "CRITICAL",
  "explanation": "<brief security assessment>",
  "suggestions": ["<suggestion 1>", "..."],
  "safe_alternatives": ["<safer command variant>", "..."]
}}
"""

_CACHE_TTL_SECONDS = 300  # 5 minutes


class GeminiAnalysisEngine:
    """LLM-based command analysis using the Google Gemini API."""

    def __init__(
        self,
        gemini_settings: GeminiSettings,
        redis_settings: RedisSettings | None = None,
        *,
        redis_client: Any | None = None,
    ) -> None:
        self._settings = gemini_settings
        self._redis = redis_client
        self._redis_prefix = (
            redis_settings.key_prefix if redis_settings else "iotguard:"
        )
        self._breaker = CircuitBreaker(
            name="gemini",
            failure_threshold=3,
            cooldown=30.0,
        )

        api_key = gemini_settings.api_key.get_secret_value()
        if api_key:
            genai.configure(api_key=api_key)

    # -- AnalysisEngine protocol --------------------------------------------

    async def analyze(
        self,
        command: str,
        device_context: dict[str, Any],
    ) -> AnalysisResult:
        """Run Gemini analysis with caching and circuit breaker."""
        # 1. Check cache
        cache_key = self._cache_key(command, device_context)
        cached = await self._get_cached(cache_key)
        if cached is not None:
            logger.debug("gemini_cache_hit", command=command[:80])
            return cached

        # 2. Call Gemini behind the circuit breaker
        api_key = self._settings.api_key.get_secret_value()
        if not api_key:
            raise LLMError("Gemini API key is not configured")

        try:
            async with self._breaker:
                result = await self._call_gemini(command, device_context)
        except LLMError:
            raise
        except Exception as exc:
            raise LLMError(f"Gemini call failed: {exc}") from exc

        # 3. Store in cache
        await self._set_cached(cache_key, result)
        return result

    # -- internals ----------------------------------------------------------

    async def _call_gemini(
        self,
        command: str,
        device_context: dict[str, Any],
    ) -> AnalysisResult:
        prompt = _ANALYSIS_PROMPT.format(
            command=command,
            device_context=json.dumps(device_context, default=str),
        )

        model = genai.GenerativeModel(
            self._settings.model_name,
            generation_config=genai.GenerationConfig(
                temperature=self._settings.temperature,
                max_output_tokens=self._settings.max_tokens,
            ),
        )

        response = model.generate_content(prompt)

        if not response or not response.text:
            raise LLMError("Empty response from Gemini API")

        return self._parse_response(response.text)

    @staticmethod
    def _parse_response(raw_text: str) -> AnalysisResult:
        """Parse the JSON response from Gemini into an AnalysisResult."""
        text = raw_text.strip()
        # Strip markdown code fences if present
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\s*", "", text)
            text = re.sub(r"\s*```$", "", text)

        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise LLMError(f"Failed to parse Gemini response as JSON: {exc}") from exc

        try:
            risk_level = RiskLevel(data.get("risk_level", "MEDIUM").upper())
        except ValueError:
            risk_level = RiskLevel.MEDIUM

        return AnalysisResult(
            risk_level=risk_level,
            explanation=data.get("explanation", ""),
            suggestions=data.get("suggestions", []),
            safe_alternatives=data.get("safe_alternatives", []),
            rule_violations=[],
            was_blocked=False,
        )

    # -- caching helpers ----------------------------------------------------

    def _cache_key(self, command: str, device_context: dict[str, Any]) -> str:
        raw = f"{command}::{json.dumps(device_context, sort_keys=True, default=str)}"
        digest = hashlib.sha256(raw.encode()).hexdigest()[:24]
        return f"{self._redis_prefix}analysis_cache:{digest}"

    async def _get_cached(self, key: str) -> AnalysisResult | None:
        if self._redis is None:
            return None
        try:
            raw = await self._redis.get(key)
            if raw is None:
                return None
            data = json.loads(raw)
            return AnalysisResult(
                risk_level=RiskLevel(data["risk_level"]),
                explanation=data["explanation"],
                suggestions=data.get("suggestions", []),
                safe_alternatives=data.get("safe_alternatives", []),
                rule_violations=data.get("rule_violations", []),
                was_blocked=data.get("was_blocked", False),
            )
        except Exception:
            logger.debug("cache_read_error", key=key)
            return None

    async def _set_cached(self, key: str, result: AnalysisResult) -> None:
        if self._redis is None:
            return
        try:
            payload = json.dumps(
                {
                    "risk_level": result.risk_level.value,
                    "explanation": result.explanation,
                    "suggestions": result.suggestions,
                    "safe_alternatives": result.safe_alternatives,
                    "rule_violations": result.rule_violations,
                    "was_blocked": result.was_blocked,
                }
            )
            await self._redis.set(key, payload, ex=_CACHE_TTL_SECONDS)
        except Exception:
            logger.debug("cache_write_error", key=key)
