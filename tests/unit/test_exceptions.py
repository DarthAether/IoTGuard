"""Unit tests for the exception hierarchy."""

from __future__ import annotations

import pytest

from iotguard.core.exceptions import (
    AnalysisError,
    AuthError,
    CommandBlockedError,
    ConfigError,
    DeviceError,
    DeviceNotFoundError,
    DeviceOfflineError,
    InsufficientPermissionsError,
    InvalidCredentialsError,
    IoTGuardError,
    LLMError,
    MqttConnectionError,
    MqttError,
    RuleViolationError,
    TokenExpiredError,
)


class TestExceptionHierarchy:
    """Verify all exceptions inherit from IoTGuardError."""

    @pytest.mark.parametrize(
        "exc_class",
        [
            ConfigError,
            AuthError,
            InvalidCredentialsError,
            InsufficientPermissionsError,
            TokenExpiredError,
            DeviceError,
            DeviceNotFoundError,
            DeviceOfflineError,
            CommandBlockedError,
            AnalysisError,
            LLMError,
            RuleViolationError,
            MqttError,
            MqttConnectionError,
        ],
    )
    def test_inherits_from_base(self, exc_class: type) -> None:
        assert issubclass(exc_class, IoTGuardError)

    def test_auth_errors_inherit_from_auth_error(self) -> None:
        assert issubclass(InvalidCredentialsError, AuthError)
        assert issubclass(InsufficientPermissionsError, AuthError)
        assert issubclass(TokenExpiredError, AuthError)

    def test_device_errors_inherit_from_device_error(self) -> None:
        assert issubclass(DeviceNotFoundError, DeviceError)
        assert issubclass(DeviceOfflineError, DeviceError)
        assert issubclass(CommandBlockedError, DeviceError)

    def test_analysis_errors_inherit_from_analysis_error(self) -> None:
        assert issubclass(LLMError, AnalysisError)
        assert issubclass(RuleViolationError, AnalysisError)

    def test_mqtt_errors_inherit_from_mqtt_error(self) -> None:
        assert issubclass(MqttConnectionError, MqttError)


class TestUniqueErrorCodes:
    """Every concrete exception should have a unique error code."""

    def test_all_codes_are_unique(self) -> None:
        codes = set()
        exceptions = [
            IoTGuardError(),
            ConfigError("x"),
            AuthError(),
            InvalidCredentialsError(),
            InsufficientPermissionsError(),
            TokenExpiredError(),
            DeviceError("x"),
            DeviceNotFoundError("dev1"),
            DeviceOfflineError("dev1"),
            CommandBlockedError("reason"),
            AnalysisError("x"),
            LLMError("x"),
            RuleViolationError("rule1", "detail"),
            MqttError("x"),
            MqttConnectionError("x"),
        ]
        for exc in exceptions:
            assert exc.code not in codes, f"Duplicate code: {exc.code}"
            codes.add(exc.code)


class TestStatusCodes:
    """Verify HTTP status codes are correctly assigned."""

    def test_base_error_is_500(self) -> None:
        assert IoTGuardError().status_code == 500

    def test_config_error_is_500(self) -> None:
        assert ConfigError("x").status_code == 500

    def test_auth_error_is_401(self) -> None:
        assert AuthError().status_code == 401

    def test_invalid_credentials_is_401(self) -> None:
        assert InvalidCredentialsError().status_code == 401

    def test_insufficient_permissions_is_403(self) -> None:
        assert InsufficientPermissionsError().status_code == 403

    def test_token_expired_is_401(self) -> None:
        assert TokenExpiredError().status_code == 401

    def test_device_not_found_is_404(self) -> None:
        assert DeviceNotFoundError("x").status_code == 404

    def test_device_offline_is_503(self) -> None:
        assert DeviceOfflineError("x").status_code == 503

    def test_command_blocked_is_403(self) -> None:
        assert CommandBlockedError("x").status_code == 403

    def test_rule_violation_is_403(self) -> None:
        assert RuleViolationError("rule", "detail").status_code == 403

    def test_mqtt_error_is_502(self) -> None:
        assert MqttError("x").status_code == 502

    def test_analysis_error_is_500(self) -> None:
        assert AnalysisError("x").status_code == 500


class TestExceptionMessages:
    """Ensure exception messages contain relevant information."""

    def test_device_not_found_includes_id(self) -> None:
        exc = DeviceNotFoundError("sensor_01")
        assert "sensor_01" in str(exc)

    def test_device_offline_includes_id(self) -> None:
        exc = DeviceOfflineError("cam_02")
        assert "cam_02" in str(exc)

    def test_command_blocked_includes_reason(self) -> None:
        exc = CommandBlockedError("dangerous pattern")
        assert "dangerous pattern" in str(exc)

    def test_rule_violation_includes_rule_name(self) -> None:
        exc = RuleViolationError("no_rm", "rm -rf detected")
        assert "no_rm" in str(exc)
        assert exc.rule_name == "no_rm"
