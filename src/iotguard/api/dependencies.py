"""FastAPI dependency injection -- settings, DB sessions, auth, services."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from typing import Annotated

import structlog
from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from iotguard.analysis.service import AnalysisService
from iotguard.core.config import Settings, get_settings
from iotguard.core.events import EventBus
from iotguard.core.security import (
    Role,
    TokenPayload,
    check_permission,
    decode_token,
)
from iotguard.db.engine import get_session_factory
from iotguard.devices.service import DeviceService
from iotguard.mqtt.service import MqttService

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Singleton containers (set during app lifespan)
# ---------------------------------------------------------------------------

_settings: Settings | None = None
_event_bus: EventBus | None = None
_mqtt_service: MqttService | None = None


def set_singletons(
    settings: Settings,
    event_bus: EventBus,
    mqtt_service: MqttService,
) -> None:
    """Called once during ``lifespan`` to wire singletons into the DI graph."""
    global _settings, _event_bus, _mqtt_service  # noqa: PLW0603
    _settings = settings
    _event_bus = event_bus
    _mqtt_service = mqtt_service


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------


def get_app_settings() -> Settings:
    if _settings is None:
        return get_settings()
    return _settings


SettingsDep = Annotated[Settings, Depends(get_app_settings)]


# ---------------------------------------------------------------------------
# Database session
# ---------------------------------------------------------------------------


async def get_db_session(
    settings: SettingsDep,
) -> AsyncIterator[AsyncSession]:
    factory = get_session_factory(settings.database)
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


DbSession = Annotated[AsyncSession, Depends(get_db_session)]


# ---------------------------------------------------------------------------
# Authentication -- JWT bearer
# ---------------------------------------------------------------------------


async def get_current_user(
    settings: SettingsDep,
    authorization: str | None = Header(None),
) -> TokenPayload:
    if authorization is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )

    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication scheme",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        return decode_token(token, settings.jwt)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


CurrentUser = Annotated[TokenPayload, Depends(get_current_user)]


# ---------------------------------------------------------------------------
# Role-based access control
# ---------------------------------------------------------------------------


def require_role(*roles: Role):  # noqa: ANN201
    """Return a dependency that verifies the current user has one of *roles*."""

    async def _checker(user: CurrentUser) -> TokenPayload:
        if user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires one of: {', '.join(r.value for r in roles)}",
            )
        return user

    return Depends(_checker)


def require_permission(permission: str):  # noqa: ANN201
    """Return a dependency that checks the permission-matrix string."""

    async def _checker(user: CurrentUser) -> TokenPayload:
        try:
            check_permission(user.role, permission)
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=str(exc),
            ) from exc
        return user

    return Depends(_checker)


AdminUser = Annotated[TokenPayload, require_role(Role.ADMIN)]
OperatorUser = Annotated[TokenPayload, require_role(Role.ADMIN, Role.OPERATOR)]
ViewerUser = Annotated[TokenPayload, require_role(Role.ADMIN, Role.OPERATOR, Role.VIEWER)]


# ---------------------------------------------------------------------------
# Service factories
# ---------------------------------------------------------------------------


def get_event_bus() -> EventBus:
    if _event_bus is None:
        return EventBus()
    return _event_bus


EventBusDep = Annotated[EventBus, Depends(get_event_bus)]


async def get_analysis_service(
    session: DbSession,
    settings: SettingsDep,
    bus: EventBusDep,
) -> AnalysisService:
    return AnalysisService(
        session,
        settings.gemini,
        bus,
        redis_settings=settings.redis,
    )


AnalysisServiceDep = Annotated[AnalysisService, Depends(get_analysis_service)]


async def get_device_service(
    session: DbSession,
    bus: EventBusDep,
) -> DeviceService:
    return DeviceService(session, bus)


DeviceServiceDep = Annotated[DeviceService, Depends(get_device_service)]


def get_mqtt_service() -> MqttService:
    if _mqtt_service is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="MQTT service not initialised",
        )
    return _mqtt_service


MqttServiceDep = Annotated[MqttService, Depends(get_mqtt_service)]
