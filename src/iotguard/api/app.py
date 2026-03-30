"""FastAPI application factory with async lifespan management."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from iotguard.api.dependencies import set_singletons
from iotguard.api.middleware import (
    CorrelationIdMiddleware,
    RequestLoggingMiddleware,
    register_exception_handlers,
)
from iotguard.api.routers import admin, analysis, analytics, auth, devices, health, mqtt, rules
from iotguard.core.config import Settings, get_settings
from iotguard.core.events import EventBus
from iotguard.core.logging import setup_logging
from iotguard.db.engine import dispose_engine, get_session_factory
from iotguard.mqtt.service import MqttService
from iotguard.observability.audit import AuditLogger
from iotguard.observability.metrics import MetricsCollector, create_metrics_app

logger = structlog.get_logger(__name__)


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Startup / shutdown hook."""
    settings: Settings = app.state.settings

    # Logging
    setup_logging(
        json_output=(settings.observability.log_format == "json"),
        level=settings.observability.log_level,
    )
    logger.info("starting_up", version=settings.api.version)

    # Event bus
    event_bus = EventBus()

    # DB session factory (ensures engine is created)
    session_factory = get_session_factory(settings.database)

    # MQTT
    mqtt_service = MqttService(settings.mqtt, session_factory, event_bus)
    try:
        await mqtt_service.start()
    except Exception:
        logger.warning("mqtt_connect_failed_at_startup")

    # Wire singletons into the DI graph
    set_singletons(settings, event_bus, mqtt_service)

    # Observability
    if settings.observability.prometheus_enabled:
        collector = MetricsCollector()
        collector.register(event_bus)

    if settings.observability.audit_enabled:
        audit_logger = AuditLogger(session_factory)
        audit_logger.register(event_bus)

    yield

    # Shutdown
    logger.info("shutting_down")
    await mqtt_service.stop()
    await dispose_engine()


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build and return a fully configured FastAPI application."""
    if settings is None:
        settings = get_settings()

    app = FastAPI(
        title=settings.api.title,
        version=settings.api.version,
        debug=settings.api.debug,
        lifespan=_lifespan,
    )
    app.state.settings = settings

    # -- CORS ---------------------------------------------------------------
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.api.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # -- Custom middleware (outermost first) ---------------------------------
    app.add_middleware(RequestLoggingMiddleware)
    app.add_middleware(CorrelationIdMiddleware)

    # -- Exception handlers -------------------------------------------------
    register_exception_handlers(app)

    # -- Routers ------------------------------------------------------------
    app.include_router(health.router)
    app.include_router(auth.router)
    app.include_router(analysis.router)
    app.include_router(devices.router)
    app.include_router(rules.router)
    app.include_router(analytics.router)
    app.include_router(admin.router)
    app.include_router(mqtt.router)

    # -- Prometheus /metrics ------------------------------------------------
    if settings.observability.prometheus_enabled:
        metrics_app = create_metrics_app()
        app.mount("/metrics", metrics_app)

    return app
