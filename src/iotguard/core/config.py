"""Centralised, layered configuration powered by pydantic-settings.

Reads from environment variables (optionally loaded from a ``.env`` file).  Every
sub-settings class is embedded in the root :class:`Settings` object so that the
rest of the application receives a single, validated config tree at startup.
"""

from __future__ import annotations

from pathlib import Path
from typing import List

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_ENV_FILE: str = str(Path(__file__).resolve().parents[3] / ".env")


# ---------------------------------------------------------------------------
# Sub-settings
# ---------------------------------------------------------------------------


class ApiSettings(BaseSettings):
    """HTTP API configuration."""

    model_config = SettingsConfigDict(env_prefix="API_")

    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = False
    cors_origins: List[str] = ["http://localhost:3000"]
    title: str = "IoTGuard"
    version: str = "1.0.0"


class JwtSettings(BaseSettings):
    """JSON Web Token configuration."""

    model_config = SettingsConfigDict(env_prefix="JWT_")

    secret_key: SecretStr = SecretStr("CHANGE_ME")
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_minutes: int = 10080  # 7 days


class DatabaseSettings(BaseSettings):
    """PostgreSQL / async SQLAlchemy configuration."""

    model_config = SettingsConfigDict(env_prefix="DB_")

    host: str = "localhost"
    port: int = 5432
    user: str = "iotguard"
    password: SecretStr = SecretStr("iotguard")
    name: str = "iotguard"
    echo: bool = False
    pool_size: int = 10
    max_overflow: int = 20

    @property
    def async_url(self) -> str:
        """Return an ``asyncpg`` DSN."""
        pwd = self.password.get_secret_value()
        return (
            f"postgresql+asyncpg://{self.user}:{pwd}"
            f"@{self.host}:{self.port}/{self.name}"
        )

    @property
    def sync_url(self) -> str:
        """Return a synchronous ``psycopg2`` DSN (for Alembic migrations)."""
        pwd = self.password.get_secret_value()
        return (
            f"postgresql+psycopg2://{self.user}:{pwd}"
            f"@{self.host}:{self.port}/{self.name}"
        )


class RedisSettings(BaseSettings):
    """Redis connection configuration."""

    model_config = SettingsConfigDict(env_prefix="REDIS_")

    host: str = "localhost"
    port: int = 6379
    db: int = 0
    password: SecretStr | None = None
    key_prefix: str = "iotguard:"

    @property
    def url(self) -> str:
        auth = ""
        if self.password:
            auth = f":{self.password.get_secret_value()}@"
        return f"redis://{auth}{self.host}:{self.port}/{self.db}"


class GeminiSettings(BaseSettings):
    """Google Gemini (generative-AI) configuration."""

    model_config = SettingsConfigDict(env_prefix="GEMINI_")

    api_key: SecretStr = SecretStr("")
    model_name: str = "gemini-1.5-flash"
    temperature: float = 0.2
    max_tokens: int = 2048


class MqttSettings(BaseSettings):
    """MQTT broker configuration."""

    model_config = SettingsConfigDict(env_prefix="MQTT_")

    broker_host: str = "localhost"
    broker_port: int = 1883
    username: str = ""
    password: SecretStr = SecretStr("")
    client_id: str = "iotguard-server"
    topics: List[str] = [
        "iotguard/devices/#",
        "iotguard/commands/#",
        "iotguard/status/#",
    ]


class DeviceSettings(BaseSettings):
    """Default device seeding."""

    model_config = SettingsConfigDict(env_prefix="DEVICE_")

    default_devices: List[str] = [
        "door_lock_01",
        "camera_01",
        "speaker_01",
        "thermostat_01",
        "light_01",
    ]


class AlertSettings(BaseSettings):
    """Alert thresholds."""

    model_config = SettingsConfigDict(env_prefix="ALERT_")

    high_risk_threshold: str = "HIGH"
    block_on_critical: bool = True


class ObservabilitySettings(BaseSettings):
    """Prometheus, audit logging, and general log tuning."""

    model_config = SettingsConfigDict(env_prefix="OBSERVABILITY_")

    prometheus_enabled: bool = True
    audit_enabled: bool = True
    log_level: str = "INFO"
    log_format: str = "json"

    @field_validator("log_level")
    @classmethod
    def _upper_log_level(cls, v: str) -> str:
        return v.upper()


# ---------------------------------------------------------------------------
# Root settings -- single entry-point for the whole application
# ---------------------------------------------------------------------------


class Settings(BaseSettings):
    """Aggregate all sub-settings into one validated tree."""

    model_config = SettingsConfigDict(
        env_file=_ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    api: ApiSettings = ApiSettings()
    jwt: JwtSettings = JwtSettings()
    database: DatabaseSettings = DatabaseSettings()
    redis: RedisSettings = RedisSettings()
    gemini: GeminiSettings = GeminiSettings()
    mqtt: MqttSettings = MqttSettings()
    devices: DeviceSettings = DeviceSettings()
    alerts: AlertSettings = AlertSettings()
    observability: ObservabilitySettings = ObservabilitySettings()


def get_settings() -> Settings:
    """Factory that can be overridden during testing via dependency injection."""
    return Settings()
