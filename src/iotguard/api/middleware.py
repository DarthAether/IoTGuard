"""HTTP middleware -- correlation ID injection, request logging, error handling."""

from __future__ import annotations

import time
import uuid

import structlog
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from iotguard.core.exceptions import IoTGuardError
from iotguard.core.logging import correlation_id_var
from iotguard.observability.metrics import http_request_duration_seconds, http_requests_total

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Correlation-ID middleware
# ---------------------------------------------------------------------------


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """Inject (or propagate) a correlation ID into every request."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        cid = request.headers.get("X-Correlation-ID") or uuid.uuid4().hex
        correlation_id_var.set(cid)

        response = await call_next(request)
        response.headers["X-Correlation-ID"] = cid
        return response


# ---------------------------------------------------------------------------
# Request-logging middleware
# ---------------------------------------------------------------------------


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Log every HTTP request with timing and record Prometheus metrics."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        start = time.monotonic()
        method = request.method
        path = request.url.path

        response = await call_next(request)

        elapsed = time.monotonic() - start
        status_code = response.status_code

        logger.info(
            "http_request",
            method=method,
            path=path,
            status=status_code,
            duration_s=round(elapsed, 4),
        )

        # Prometheus
        http_requests_total.labels(
            method=method,
            path=path,
            status_code=str(status_code),
        ).inc()
        http_request_duration_seconds.labels(method=method, path=path).observe(elapsed)

        return response


# ---------------------------------------------------------------------------
# Exception handlers
# ---------------------------------------------------------------------------


def register_exception_handlers(app: FastAPI) -> None:
    """Attach global exception handlers that turn domain errors into JSON."""

    @app.exception_handler(IoTGuardError)
    async def _domain_error_handler(request: Request, exc: IoTGuardError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": exc.code,
                "detail": exc.message,
                "correlation_id": correlation_id_var.get() or None,
            },
        )

    @app.exception_handler(Exception)
    async def _unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("unhandled_exception", path=request.url.path)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": "INTERNAL_ERROR",
                "detail": "An unexpected error occurred",
                "correlation_id": correlation_id_var.get() or None,
            },
        )
