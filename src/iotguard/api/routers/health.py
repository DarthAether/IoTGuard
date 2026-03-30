"""Health, readiness, and startup probe endpoints."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends

from iotguard.api.dependencies import SettingsDep, get_app_settings
from iotguard.db.engine import get_session_factory
from iotguard.mqtt.service import MqttService
from iotguard.observability.health import HealthChecker

router = APIRouter(tags=["health"])


def _build_checker(settings: SettingsDep) -> HealthChecker:
    from iotguard.api.dependencies import _mqtt_service

    return HealthChecker(
        session_factory=get_session_factory(settings.database),
        redis_settings=settings.redis,
        gemini_settings=settings.gemini,
        mqtt_service=_mqtt_service,
    )


@router.get("/health")
async def health(settings: SettingsDep) -> dict[str, Any]:
    """Liveness probe -- always returns 200 if the process is running."""
    checker = _build_checker(settings)
    return await checker.liveness()


@router.get("/ready")
async def ready(settings: SettingsDep) -> dict[str, Any]:
    """Readiness probe -- checks DB and Redis."""
    checker = _build_checker(settings)
    return await checker.readiness()


@router.get("/startup")
async def startup(settings: SettingsDep) -> dict[str, Any]:
    """Startup probe -- full component check."""
    checker = _build_checker(settings)
    return await checker.startup()
