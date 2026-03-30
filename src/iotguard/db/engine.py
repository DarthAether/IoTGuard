"""Async SQLAlchemy engine, session factory, and ``get_session`` dependency.

The module maintains a single engine / session-factory pair that is lazily
created on first access and can be torn down via :func:`dispose_engine`.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from iotguard.core.config import DatabaseSettings

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def get_engine(settings: DatabaseSettings) -> AsyncEngine:
    """Return (and lazily create) the async engine singleton."""
    global _engine  # noqa: PLW0603
    if _engine is None:
        _engine = create_async_engine(
            settings.async_url,
            echo=settings.echo,
            pool_size=settings.pool_size,
            max_overflow=settings.max_overflow,
        )
    return _engine


def get_session_factory(settings: DatabaseSettings) -> async_sessionmaker[AsyncSession]:
    """Return (and lazily create) the session factory singleton."""
    global _session_factory  # noqa: PLW0603
    if _session_factory is None:
        engine = get_engine(settings)
        _session_factory = async_sessionmaker(
            engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )
    return _session_factory


async def get_session(settings: DatabaseSettings) -> AsyncIterator[AsyncSession]:
    """FastAPI-compatible dependency that yields an ``AsyncSession``.

    Usage in a router::

        @router.get("/items")
        async def list_items(session: AsyncSession = Depends(get_session)):
            ...
    """
    factory = get_session_factory(settings)
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def dispose_engine() -> None:
    """Gracefully close the connection pool."""
    global _engine, _session_factory  # noqa: PLW0603
    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _session_factory = None
