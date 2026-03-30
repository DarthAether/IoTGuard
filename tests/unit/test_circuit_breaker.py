"""Unit tests for the CircuitBreaker -- all state transitions."""

from __future__ import annotations

import time
from unittest.mock import patch

import pytest

from iotguard.core.circuit_breaker import CircuitBreaker, CircuitOpenError, CircuitState


class TestCircuitBreakerClosed:
    """Breaker starts CLOSED and stays closed on success."""

    async def test_initial_state_is_closed(self) -> None:
        cb = CircuitBreaker(name="test", failure_threshold=3, cooldown=1.0)
        assert cb.state == CircuitState.CLOSED
        assert cb.failure_count == 0

    async def test_success_keeps_closed(self) -> None:
        cb = CircuitBreaker(name="test", failure_threshold=3, cooldown=1.0)
        async with cb:
            pass  # success
        assert cb.state == CircuitState.CLOSED
        assert cb.failure_count == 0

    async def test_failure_below_threshold_stays_closed(self) -> None:
        cb = CircuitBreaker(name="test", failure_threshold=3, cooldown=1.0)
        for _ in range(2):
            with pytest.raises(RuntimeError):
                async with cb:
                    raise RuntimeError("transient")
        assert cb.state == CircuitState.CLOSED
        assert cb.failure_count == 2


class TestCircuitBreakerOpen:
    """Breaker opens after reaching the failure threshold."""

    async def test_opens_at_threshold(self) -> None:
        cb = CircuitBreaker(name="test", failure_threshold=3, cooldown=60.0)
        for _ in range(3):
            with pytest.raises(RuntimeError):
                async with cb:
                    raise RuntimeError("fail")
        assert cb.state == CircuitState.OPEN
        assert cb.failure_count == 3

    async def test_open_breaker_raises_circuit_open_error(self) -> None:
        cb = CircuitBreaker(name="test", failure_threshold=1, cooldown=60.0)
        with pytest.raises(RuntimeError):
            async with cb:
                raise RuntimeError("fail")
        assert cb.state == CircuitState.OPEN

        with pytest.raises(CircuitOpenError) as exc_info:
            async with cb:
                pass
        assert exc_info.value.name == "test"
        assert exc_info.value.retry_after >= 0

    async def test_circuit_open_error_has_retry_after(self) -> None:
        cb = CircuitBreaker(name="test", failure_threshold=1, cooldown=30.0)
        with pytest.raises(RuntimeError):
            async with cb:
                raise RuntimeError("fail")

        with pytest.raises(CircuitOpenError) as exc_info:
            async with cb:
                pass
        assert exc_info.value.retry_after > 0


class TestCircuitBreakerHalfOpen:
    """After cooldown, breaker enters HALF_OPEN and probes."""

    async def test_transitions_to_half_open_after_cooldown(self) -> None:
        cb = CircuitBreaker(name="test", failure_threshold=1, cooldown=0.01)
        with pytest.raises(RuntimeError):
            async with cb:
                raise RuntimeError("fail")

        assert cb.state == CircuitState.OPEN

        # Wait for cooldown
        import asyncio
        await asyncio.sleep(0.05)

        # Should now be HALF_OPEN
        assert cb.state == CircuitState.HALF_OPEN

    async def test_half_open_success_closes_breaker(self) -> None:
        cb = CircuitBreaker(name="test", failure_threshold=1, cooldown=0.01)
        with pytest.raises(RuntimeError):
            async with cb:
                raise RuntimeError("fail")

        import asyncio
        await asyncio.sleep(0.05)

        # Successful probe should close the breaker
        async with cb:
            pass

        assert cb.state == CircuitState.CLOSED
        assert cb.failure_count == 0

    async def test_half_open_failure_reopens_breaker(self) -> None:
        cb = CircuitBreaker(name="test", failure_threshold=1, cooldown=0.01)
        with pytest.raises(RuntimeError):
            async with cb:
                raise RuntimeError("fail1")

        import asyncio
        await asyncio.sleep(0.05)

        # Failed probe should reopen
        with pytest.raises(RuntimeError):
            async with cb:
                raise RuntimeError("fail2")

        assert cb.state == CircuitState.OPEN


class TestCircuitBreakerManualReset:
    """Manual reset returns the breaker to CLOSED."""

    async def test_manual_reset(self) -> None:
        cb = CircuitBreaker(name="test", failure_threshold=1, cooldown=60.0)
        with pytest.raises(RuntimeError):
            async with cb:
                raise RuntimeError("fail")
        assert cb.state == CircuitState.OPEN

        await cb.reset()

        assert cb.state == CircuitState.CLOSED
        assert cb.failure_count == 0

    async def test_reset_from_closed_is_noop(self) -> None:
        cb = CircuitBreaker(name="test", failure_threshold=3, cooldown=1.0)
        await cb.reset()
        assert cb.state == CircuitState.CLOSED
        assert cb.failure_count == 0


class TestCircuitBreakerExceptionPropagation:
    """The breaker never suppresses exceptions."""

    async def test_exception_propagates_through(self) -> None:
        cb = CircuitBreaker(name="test", failure_threshold=5, cooldown=1.0)
        with pytest.raises(ValueError, match="specific error"):
            async with cb:
                raise ValueError("specific error")

    async def test_success_resets_after_failures(self) -> None:
        cb = CircuitBreaker(name="test", failure_threshold=5, cooldown=1.0)
        # 2 failures
        for _ in range(2):
            with pytest.raises(RuntimeError):
                async with cb:
                    raise RuntimeError("x")
        assert cb.failure_count == 2

        # 1 success should reset
        async with cb:
            pass
        assert cb.failure_count == 0
