"""Async circuit breaker for external service calls (LLM, MQTT, etc.).

The breaker tracks consecutive failures.  When a configurable threshold is
exceeded it *opens*, short-circuiting all subsequent calls for a cooldown
period.  After the cooldown, a single *half-open* probe is allowed through;
if it succeeds the breaker resets, otherwise it re-opens.

Usage::

    breaker = CircuitBreaker(name="gemini", failure_threshold=3, cooldown=30.0)

    async with breaker:
        result = await call_external_api()
"""

from __future__ import annotations

import asyncio
import enum
import time
from types import TracebackType
from typing import Type

import structlog

logger = structlog.get_logger(__name__)


class CircuitState(str, enum.Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitOpenError(Exception):
    """Raised when a call is attempted while the breaker is open."""

    def __init__(self, name: str, retry_after: float) -> None:
        self.name = name
        self.retry_after = retry_after
        super().__init__(
            f"Circuit breaker '{name}' is open; retry after {retry_after:.1f}s"
        )


class CircuitBreaker:
    """Async-safe circuit breaker.

    Parameters
    ----------
    name:
        Human-readable label used in logs and error messages.
    failure_threshold:
        Number of consecutive failures before the breaker opens.
    cooldown:
        Seconds to wait in the *open* state before allowing a probe.
    """

    def __init__(
        self,
        *,
        name: str = "default",
        failure_threshold: int = 5,
        cooldown: float = 30.0,
    ) -> None:
        self.name = name
        self.failure_threshold = failure_threshold
        self.cooldown = cooldown

        self._state = CircuitState.CLOSED
        self._failure_count: int = 0
        self._last_failure_time: float = 0.0
        self._lock = asyncio.Lock()

    # -- public properties --------------------------------------------------

    @property
    def state(self) -> CircuitState:
        """Return the current breaker state (may transition from OPEN to HALF_OPEN)."""
        if self._state == CircuitState.OPEN:
            elapsed = time.monotonic() - self._last_failure_time
            if elapsed >= self.cooldown:
                self._state = CircuitState.HALF_OPEN
        return self._state

    @property
    def failure_count(self) -> int:
        return self._failure_count

    # -- context manager protocol -------------------------------------------

    async def __aenter__(self) -> CircuitBreaker:
        async with self._lock:
            current = self.state
            if current == CircuitState.OPEN:
                retry_after = self.cooldown - (
                    time.monotonic() - self._last_failure_time
                )
                raise CircuitOpenError(self.name, max(retry_after, 0.0))
            # CLOSED or HALF_OPEN -- allow the call through
        return self

    async def __aexit__(
        self,
        exc_type: Type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> bool:
        async with self._lock:
            if exc_type is None:
                # Success -- reset the breaker
                if self._state != CircuitState.CLOSED:
                    logger.info(
                        "circuit_breaker_closed",
                        name=self.name,
                        previous_failures=self._failure_count,
                    )
                self._failure_count = 0
                self._state = CircuitState.CLOSED
            else:
                # Failure
                self._failure_count += 1
                self._last_failure_time = time.monotonic()

                if self._failure_count >= self.failure_threshold:
                    self._state = CircuitState.OPEN
                    logger.warning(
                        "circuit_breaker_opened",
                        name=self.name,
                        failure_count=self._failure_count,
                        cooldown=self.cooldown,
                    )
                else:
                    logger.debug(
                        "circuit_breaker_failure",
                        name=self.name,
                        failure_count=self._failure_count,
                        threshold=self.failure_threshold,
                    )
        # Never suppress the exception -- let it propagate
        return False

    # -- manual controls ----------------------------------------------------

    async def reset(self) -> None:
        """Manually reset the breaker to a closed state."""
        async with self._lock:
            self._failure_count = 0
            self._state = CircuitState.CLOSED
            logger.info("circuit_breaker_manual_reset", name=self.name)
