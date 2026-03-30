"""Shared test fixtures for the IoTGuard test suite.

Provides a fully isolated test environment using SQLite (async), disabled MQTT,
a fake Gemini engine, and a FastAPI TestClient wired to all fakes.
"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import AsyncIterator, Iterator
from typing import Any
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient
from pydantic import SecretStr
from sqlalchemy import event
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from iotguard.analysis.models import AnalysisResult, RiskLevel
from iotguard.core.config import (
    AlertSettings,
    ApiSettings,
    DatabaseSettings,
    DeviceSettings,
    GeminiSettings,
    JwtSettings,
    MqttSettings,
    ObservabilitySettings,
    RedisSettings,
    Settings,
)
from iotguard.core.events import EventBus
from iotguard.db.models import Base


# ---------------------------------------------------------------------------
# Settings fixture -- SQLite, disabled MQTT, temp dirs
# ---------------------------------------------------------------------------


@pytest.fixture()
def test_settings(tmp_path: Any) -> Settings:
    """Return a Settings object configured for testing."""
    return Settings(
        api=ApiSettings(host="127.0.0.1", port=8000, debug=True),
        jwt=JwtSettings(
            secret_key=SecretStr("test-secret-key-for-jwt-tokens"),
            algorithm="HS256",
            access_token_expire_minutes=30,
            refresh_token_expire_minutes=60,
        ),
        database=DatabaseSettings(
            host="localhost",
            port=5432,
            user="test",
            password=SecretStr("test"),
            name="test",
        ),
        redis=RedisSettings(host="localhost", port=6379, db=15),
        gemini=GeminiSettings(api_key=SecretStr("fake-key")),
        mqtt=MqttSettings(
            broker_host="localhost",
            broker_port=1883,
            client_id="test-client",
        ),
        devices=DeviceSettings(),
        alerts=AlertSettings(),
        observability=ObservabilitySettings(
            prometheus_enabled=False,
            audit_enabled=False,
            log_level="DEBUG",
            log_format="console",
        ),
    )


# ---------------------------------------------------------------------------
# Fake Gemini engine
# ---------------------------------------------------------------------------


class FakeGeminiEngine:
    """Returns a canned AnalysisResult without calling any external API."""

    def __init__(self, result: AnalysisResult | None = None) -> None:
        self._result = result or AnalysisResult(
            risk_level=RiskLevel.LOW,
            explanation="Fake analysis: command appears safe.",
            suggestions=["No action needed."],
            safe_alternatives=[],
            rule_violations=[],
            was_blocked=False,
        )

    async def analyze(
        self,
        command: str,
        device_context: dict[str, Any],
    ) -> AnalysisResult:
        return self._result


@pytest.fixture()
def fake_gemini_engine() -> FakeGeminiEngine:
    """Provide a FakeGeminiEngine that returns a canned LOW-risk result."""
    return FakeGeminiEngine()


# ---------------------------------------------------------------------------
# Event bus fixture
# ---------------------------------------------------------------------------


@pytest.fixture()
def event_bus() -> EventBus:
    """Return a fresh EventBus for each test."""
    return EventBus()


# ---------------------------------------------------------------------------
# Async SQLite database session
# ---------------------------------------------------------------------------


@pytest.fixture()
async def db_engine() -> AsyncIterator[AsyncEngine]:
    """Create an async SQLite engine and provision all tables."""
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        echo=False,
    )

    # SQLite does not support schemas, so we need to handle the JSONB columns.
    # We create tables using the metadata but with SQLite-compatible types.
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@pytest.fixture()
async def db_session(db_engine: AsyncEngine) -> AsyncIterator[AsyncSession]:
    """Yield an AsyncSession bound to the SQLite engine.

    Each test gets its own transaction that is rolled back at the end.
    """
    session_factory = async_sessionmaker(
        db_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    async with session_factory() as session:
        yield session


@pytest.fixture()
def db_session_factory(db_engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """Return a session factory bound to the test SQLite engine."""
    return async_sessionmaker(
        db_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )


# ---------------------------------------------------------------------------
# FastAPI test client with all fakes wired in
# ---------------------------------------------------------------------------


@pytest.fixture()
async def test_client(
    test_settings: Settings,
    db_engine: AsyncEngine,
    event_bus: EventBus,
    fake_gemini_engine: FakeGeminiEngine,
) -> AsyncIterator[AsyncClient]:
    """Provide an httpx.AsyncClient talking to the app with fakes injected."""
    from iotguard.api.dependencies import (
        get_app_settings,
        get_db_session,
        get_event_bus,
        get_mqtt_service,
    )
    from iotguard.api.app import create_app

    session_factory = async_sessionmaker(
        db_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    app = create_app(settings=test_settings)

    # Override dependencies
    app.dependency_overrides[get_app_settings] = lambda: test_settings

    async def _override_db_session() -> AsyncIterator[AsyncSession]:
        async with session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_db_session] = _override_db_session
    app.dependency_overrides[get_event_bus] = lambda: event_bus

    # Create a mock MQTT service
    mock_mqtt = AsyncMock()
    mock_mqtt.is_connected = False
    mock_mqtt.status.return_value = {"connected": False, "running": False}
    app.dependency_overrides[get_mqtt_service] = lambda: mock_mqtt

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Auth helper fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def auth_headers(test_settings: Settings) -> dict[str, str]:
    """Return Authorization headers with a valid admin JWT."""
    from iotguard.core.security import Role, create_token_pair

    user_id = str(uuid.uuid4())
    pair = create_token_pair(user_id, Role.ADMIN, test_settings.jwt)
    return {"Authorization": f"Bearer {pair.access_token}"}


@pytest.fixture()
def viewer_auth_headers(test_settings: Settings) -> dict[str, str]:
    """Return Authorization headers with a valid viewer JWT."""
    from iotguard.core.security import Role, create_token_pair

    user_id = str(uuid.uuid4())
    pair = create_token_pair(user_id, Role.VIEWER, test_settings.jwt)
    return {"Authorization": f"Bearer {pair.access_token}"}


@pytest.fixture()
def operator_auth_headers(test_settings: Settings) -> dict[str, str]:
    """Return Authorization headers with a valid operator JWT."""
    from iotguard.core.security import Role, create_token_pair

    user_id = str(uuid.uuid4())
    pair = create_token_pair(user_id, Role.OPERATOR, test_settings.jwt)
    return {"Authorization": f"Bearer {pair.access_token}"}
