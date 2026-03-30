"""Unit tests for Settings construction, validation, and SecretStr safety."""

from __future__ import annotations

import pytest
from pydantic import SecretStr

from iotguard.core.config import (
    ApiSettings,
    DatabaseSettings,
    GeminiSettings,
    JwtSettings,
    MqttSettings,
    ObservabilitySettings,
    RedisSettings,
    Settings,
)


class TestSettingsConstruction:
    """Verify Settings and sub-settings can be built with defaults."""

    def test_default_settings_are_valid(self) -> None:
        settings = Settings()
        assert settings.api.port == 8000
        assert settings.jwt.algorithm == "HS256"
        assert settings.database.pool_size == 10

    def test_api_settings_defaults(self) -> None:
        api = ApiSettings()
        assert api.host == "0.0.0.0"
        assert api.debug is False
        assert api.version == "1.0.0"
        assert "localhost:3000" in api.cors_origins[0]

    def test_jwt_settings_defaults(self) -> None:
        jwt = JwtSettings()
        assert jwt.access_token_expire_minutes == 30
        assert jwt.refresh_token_expire_minutes == 10080

    def test_database_async_url_format(self) -> None:
        db = DatabaseSettings(user="u", password=SecretStr("p"), host="h", port=5432, name="n")
        assert db.async_url == "postgresql+asyncpg://u:p@h:5432/n"

    def test_database_sync_url_format(self) -> None:
        db = DatabaseSettings(user="u", password=SecretStr("p"), host="h", port=5432, name="n")
        assert db.sync_url == "postgresql+psycopg2://u:p@h:5432/n"

    def test_redis_url_without_password(self) -> None:
        r = RedisSettings(host="rh", port=6379, db=0, password=None)
        assert r.url == "redis://rh:6379/0"

    def test_redis_url_with_password(self) -> None:
        r = RedisSettings(host="rh", port=6379, db=2, password=SecretStr("secret"))
        assert r.url == "redis://:secret@rh:6379/2"

    def test_mqtt_default_topics(self) -> None:
        mqtt = MqttSettings()
        assert len(mqtt.topics) == 3
        assert any("devices" in t for t in mqtt.topics)


class TestSettingsValidation:
    """Test field validators and constraints."""

    def test_observability_log_level_uppercased(self) -> None:
        obs = ObservabilitySettings(log_level="debug")
        assert obs.log_level == "DEBUG"

    def test_observability_log_level_already_upper(self) -> None:
        obs = ObservabilitySettings(log_level="WARNING")
        assert obs.log_level == "WARNING"


class TestSecretStrSafety:
    """Ensure secrets are not leaked via str() or repr()."""

    def test_jwt_secret_not_in_str(self) -> None:
        jwt = JwtSettings(secret_key=SecretStr("super-secret-key"))
        assert "super-secret-key" not in str(jwt.secret_key)
        assert "super-secret-key" not in repr(jwt.secret_key)

    def test_database_password_not_in_str(self) -> None:
        db = DatabaseSettings(password=SecretStr("db-pass-123"))
        assert "db-pass-123" not in str(db.password)
        assert "db-pass-123" not in repr(db.password)

    def test_gemini_api_key_not_in_str(self) -> None:
        g = GeminiSettings(api_key=SecretStr("AIza-real-key"))
        assert "AIza-real-key" not in str(g.api_key)

    def test_secret_value_accessible_via_get(self) -> None:
        jwt = JwtSettings(secret_key=SecretStr("my-key"))
        assert jwt.secret_key.get_secret_value() == "my-key"

    def test_mqtt_password_not_in_str(self) -> None:
        mqtt = MqttSettings(password=SecretStr("mqtt-pass"))
        assert "mqtt-pass" not in str(mqtt.password)
