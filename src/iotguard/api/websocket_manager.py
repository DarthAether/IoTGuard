"""WebSocket connection manager for real-time event broadcasts."""

from __future__ import annotations

import json
from typing import Any

import structlog
from fastapi import WebSocket

logger = structlog.get_logger(__name__)


class ConnectionManager:
    """Track active WebSocket connections and broadcast JSON messages."""

    def __init__(self) -> None:
        self._active: list[WebSocket] = []

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        self._active.append(ws)
        logger.info("ws_connected", total=len(self._active))

    def disconnect(self, ws: WebSocket) -> None:
        if ws in self._active:
            self._active.remove(ws)
        logger.info("ws_disconnected", total=len(self._active))

    async def broadcast(self, message: dict[str, Any]) -> None:
        """Send *message* (serialised to JSON) to every connected client."""
        payload = json.dumps(message)
        stale: list[WebSocket] = []
        for ws in self._active:
            try:
                await ws.send_text(payload)
            except Exception:
                stale.append(ws)
        for ws in stale:
            self.disconnect(ws)

    async def send_personal(self, ws: WebSocket, message: dict[str, Any]) -> None:
        try:
            await ws.send_json(message)
        except Exception:
            self.disconnect(ws)

    @property
    def active_count(self) -> int:
        return len(self._active)
