"""Domain exception hierarchy.

Every exception carries a machine-readable ``code`` and an HTTP-friendly
``status_code`` so that the API layer can translate domain errors directly
into proper HTTP responses.
"""

from __future__ import annotations


# ---------------------------------------------------------------------------
# Base
# ---------------------------------------------------------------------------


class IoTGuardError(Exception):
    """Base for all domain errors."""

    def __init__(
        self,
        message: str = "",
        *,
        code: str = "IOTGUARD_ERROR",
        status_code: int = 500,
    ) -> None:
        self.message = message
        self.code = code
        self.status_code = status_code
        super().__init__(message)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


class ConfigError(IoTGuardError):
    """Raised when required configuration is missing or invalid."""

    def __init__(self, detail: str) -> None:
        super().__init__(detail, code="CONFIG_ERROR", status_code=500)


# ---------------------------------------------------------------------------
# Authentication & authorisation
# ---------------------------------------------------------------------------


class AuthError(IoTGuardError):
    """Generic authentication / authorisation error."""

    def __init__(self, detail: str = "Authentication required") -> None:
        super().__init__(detail, code="AUTH_ERROR", status_code=401)


class InvalidCredentialsError(AuthError):
    """Username or password is wrong."""

    def __init__(self, detail: str = "Invalid credentials") -> None:
        super().__init__(detail)
        self.code = "INVALID_CREDENTIALS"


class InsufficientPermissionsError(AuthError):
    """User lacks the required role / permission."""

    def __init__(self, detail: str = "Insufficient permissions") -> None:
        super().__init__(detail)
        self.code = "INSUFFICIENT_PERMISSIONS"
        self.status_code = 403


class TokenExpiredError(AuthError):
    """The JWT has expired."""

    def __init__(self) -> None:
        super().__init__("Token has expired")
        self.code = "TOKEN_EXPIRED"


# ---------------------------------------------------------------------------
# Device errors
# ---------------------------------------------------------------------------


class DeviceError(IoTGuardError):
    """Generic device-layer error."""

    def __init__(self, detail: str, *, device_id: str = "") -> None:
        super().__init__(detail, code="DEVICE_ERROR", status_code=400)
        self.device_id = device_id


class DeviceNotFoundError(DeviceError):
    """The requested device does not exist."""

    def __init__(self, device_id: str) -> None:
        super().__init__(f"Device '{device_id}' not found", device_id=device_id)
        self.code = "DEVICE_NOT_FOUND"
        self.status_code = 404


class DeviceOfflineError(DeviceError):
    """The device exists but is currently offline."""

    def __init__(self, device_id: str) -> None:
        super().__init__(f"Device '{device_id}' is offline", device_id=device_id)
        self.code = "DEVICE_OFFLINE"
        self.status_code = 503


class CommandBlockedError(DeviceError):
    """A command was blocked by security rules or analysis."""

    def __init__(self, reason: str, *, rule_name: str = "") -> None:
        super().__init__(f"Command blocked: {reason}")
        self.code = "COMMAND_BLOCKED"
        self.status_code = 403
        self.reason = reason
        self.rule_name = rule_name


# ---------------------------------------------------------------------------
# Analysis / LLM errors
# ---------------------------------------------------------------------------


class AnalysisError(IoTGuardError):
    """Generic analysis-layer error."""

    def __init__(self, detail: str) -> None:
        super().__init__(f"Analysis failed: {detail}", code="ANALYSIS_ERROR", status_code=500)


class LLMError(AnalysisError):
    """The LLM backend returned an error or timed out."""

    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.code = "LLM_ERROR"


class RuleViolationError(AnalysisError):
    """A security rule was violated."""

    def __init__(self, rule_name: str, detail: str) -> None:
        super().__init__(f"Rule '{rule_name}' violated: {detail}")
        self.code = "RULE_VIOLATION"
        self.status_code = 403
        self.rule_name = rule_name


# ---------------------------------------------------------------------------
# MQTT / infrastructure
# ---------------------------------------------------------------------------


class MqttError(IoTGuardError):
    """Generic MQTT transport error."""

    def __init__(self, detail: str) -> None:
        super().__init__(f"MQTT error: {detail}", code="MQTT_ERROR", status_code=502)


class MqttConnectionError(MqttError):
    """Cannot connect to the MQTT broker."""

    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.code = "MQTT_CONNECTION_ERROR"
