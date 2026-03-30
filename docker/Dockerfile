# ------------------------------------------------------------------
# IoTGuard -- multi-stage production build
# ------------------------------------------------------------------

# ---- Stage 1: builder ----
FROM python:3.14-slim AS builder

WORKDIR /build

# Install build deps
RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc libpq-dev && \
    rm -rf /var/lib/apt/lists/*

# Copy project metadata first for layer caching
COPY pyproject.toml ./
COPY src/ ./src/

# Build the wheel
RUN pip install --no-cache-dir build && \
    python -m build --wheel --outdir /build/dist

# Install into a virtual environment
RUN python -m venv /opt/venv && \
    /opt/venv/bin/pip install --no-cache-dir /build/dist/*.whl


# ---- Stage 2: runtime ----
FROM python:3.14-slim AS runtime

# Security: run as non-root
RUN groupadd --gid 1001 iotguard && \
    useradd --uid 1001 --gid iotguard --shell /bin/false --create-home iotguard

# Runtime deps only
RUN apt-get update && \
    apt-get install -y --no-install-recommends libpq5 curl && \
    rm -rf /var/lib/apt/lists/*

# Copy virtualenv from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Copy application source (for alembic migrations etc.)
WORKDIR /app
COPY src/ ./src/
COPY alembic.ini ./

# Switch to non-root user
USER iotguard

EXPOSE 8000

# Healthcheck
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

ENTRYPOINT ["uvicorn", "iotguard.api.app:create_app", "--factory", \
            "--host", "0.0.0.0", "--port", "8000"]
CMD ["--workers", "2"]
