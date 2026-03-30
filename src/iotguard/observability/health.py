"""Health / readiness / startup probes for Kubernetes-style orchestration.

Each sub-check runs independently so that a degraded component does not mask
healthier ones.  The aggregate status is ``"healthy"`` only when every check
passes.
"""

from __future__ import annotations

from typing import Any

import httpx
import structlog
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from iotguard.core.config import GeminiSettings, RedisSettings
from iotguard.mqtt.service import MqttService

logger = structlog.get_logger(__name__)


class HealthChecker:
    """Run health probes against all critical infrastructure components."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        redis_settings: RedisSettings,
        gemini_settings: GeminiSettings,
        mqtt_service: MqttService | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._redis_settings = redis_settings
        self._gemini_settings = gemini_settings
        self._mqtt = mqtt_service

    # ------------------------------------------------------------------
    # Individual probes
    # ------------------------------------------------------------------

    async def check_db(self) -> dict[str, Any]:
        try:
            async with self._session_factory() as session:
                await session.execute(text("SELECT 1"))
            return {"status": "healthy"}
        except Exception as exc:
            logger.warning("health_db_failed", error=str(exc))
            return {"status": "unhealthy", "error": str(exc)}

    async def check_redis(self) -> dict[str, Any]:
        try:
            client = Redis.from_url(self._redis_settings.url)
            try:
                pong = await client.ping()
                return {"status": "healthy" if pong else "unhealthy"}
            finally:
                await client.aclose()
        except Exception as exc:
            logger.warning("health_redis_failed", error=str(exc))
            return {"status": "unhealthy", "error": str(exc)}

    async def check_gemini(self) -> dict[str, Any]:
        api_key = self._gemini_settings.api_key.get_secret_value()
        if not api_key:
            return {"status": "skipped", "reason": "No API key configured"}
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    "https://generativelanguage.googleapis.com/v1beta/models",
                    params={"key": api_key},
                )
                if resp.status_code == 200:
                    return {"status": "healthy"}
                return {"status": "unhealthy", "http_status": resp.status_code}
        except Exception as exc:
            logger.warning("health_gemini_failed", error=str(exc))
            return {"status": "unhealthy", "error": str(exc)}

    async def check_mqtt(self) -> dict[str, Any]:
        if self._mqtt is None:
            return {"status": "skipped", "reason": "MQTT service not configured"}
        return {
            "status": "healthy" if self._mqtt.is_connected else "unhealthy",
            "connected": self._mqtt.is_connected,
        }

    # ------------------------------------------------------------------
    # Aggregate endpoints
    # ------------------------------------------------------------------

    async def liveness(self) -> dict[str, Any]:
        """Lightweight liveness probe -- always returns OK if the process is up."""
        return {"status": "healthy"}

    async def readiness(self) -> dict[str, Any]:
        """Full readiness check -- DB + Redis must both be healthy."""
        db = await self.check_db()
        redis = await self.check_redis()
        components = {"database": db, "redis": redis}
        overall = "healthy" if all(c["status"] == "healthy" for c in components.values()) else "degraded"
        return {"status": overall, "components": components}

    async def startup(self) -> dict[str, Any]:
        """Comprehensive startup check -- all four sub-systems."""
        db = await self.check_db()
        redis = await self.check_redis()
        gemini = await self.check_gemini()
        mqtt = await self.check_mqtt()
        components = {
            "database": db,
            "redis": redis,
            "gemini": gemini,
            "mqtt": mqtt,
        }
        healthy = all(c["status"] in ("healthy", "skipped") for c in components.values())
        return {"status": "healthy" if healthy else "degraded", "components": components}
