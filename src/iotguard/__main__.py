"""Entry point for ``python -m iotguard``."""

from __future__ import annotations

import uvicorn

from iotguard.api.app import create_app
from iotguard.core.config import get_settings


def main() -> None:
    settings = get_settings()
    app = create_app(settings)
    uvicorn.run(
        app,
        host=settings.api.host,
        port=settings.api.port,
        log_level=settings.observability.log_level.lower(),
    )


if __name__ == "__main__":
    main()
