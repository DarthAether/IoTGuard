"""Structured logging setup with correlation-ID propagation.

Call :func:`setup_logging` once at application startup.  Every log entry
produced via ``structlog`` will automatically carry a ``correlation_id``
(aliased ``threat_id`` for backward compatibility) that threads through
the entire request lifecycle.
"""

from __future__ import annotations

import logging
import sys
import uuid
from contextvars import ContextVar
from typing import Any

import structlog

_correlation_id_ctx: ContextVar[str] = ContextVar("correlation_id", default="")


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------


def get_correlation_id() -> str:
    """Return the current correlation ID (or generate one if unset)."""
    cid = _correlation_id_ctx.get()
    if not cid:
        cid = uuid.uuid4().hex[:16]
        _correlation_id_ctx.set(cid)
    return cid


def set_correlation_id(cid: str) -> None:
    """Explicitly set the correlation ID (e.g. from an incoming header)."""
    _correlation_id_ctx.set(cid)


def new_correlation_id() -> str:
    """Generate, store, and return a fresh correlation ID."""
    cid = uuid.uuid4().hex[:16]
    _correlation_id_ctx.set(cid)
    return cid


# ---------------------------------------------------------------------------
# structlog processors
# ---------------------------------------------------------------------------


def _add_correlation_id(
    _logger: Any,
    _method: str,
    event_dict: dict[str, Any],
) -> dict[str, Any]:
    """Inject the correlation / threat ID into every log record."""
    cid = get_correlation_id()
    event_dict["correlation_id"] = cid
    event_dict["threat_id"] = cid  # backward-compat alias
    return event_dict


def _add_service_context(
    _logger: Any,
    _method: str,
    event_dict: dict[str, Any],
) -> dict[str, Any]:
    """Tag every record with the service name."""
    event_dict.setdefault("service", "iotguard")
    return event_dict


# ---------------------------------------------------------------------------
# Bootstrap
# ---------------------------------------------------------------------------


def setup_logging(
    *,
    log_level: str = "INFO",
    log_format: str = "json",
) -> None:
    """Configure structlog and the stdlib root logger.

    Parameters
    ----------
    log_level:
        Python log-level name (``DEBUG``, ``INFO``, ...).
    log_format:
        ``"json"`` for machine-readable output, ``"console"`` for
        human-friendly coloured output during development.
    """
    level = getattr(logging, log_level.upper(), logging.INFO)

    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        _add_correlation_id,
        _add_service_context,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.UnicodeDecoder(),
    ]

    if log_format == "console":
        renderer: structlog.types.Processor = structlog.dev.ConsoleRenderer()
    else:
        renderer = structlog.processors.JSONRenderer()

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)

    # Silence chatty third-party loggers
    for name in ("uvicorn.access", "sqlalchemy.engine", "httpx", "paho"):
        logging.getLogger(name).setLevel(logging.WARNING)


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """Return a bound structlog logger."""
    return structlog.get_logger(name)  # type: ignore[return-value]
