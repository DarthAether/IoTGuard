"""Locust load test for IoTGuard API.

Exercises the /health, /v1/analyze, and /v1/devices endpoints under load.

Usage:
    locust -f tests/load/locustfile.py --host http://localhost:8000
"""

from __future__ import annotations

import json
import random
import uuid

from locust import HttpUser, between, task


class IoTGuardUser(HttpUser):
    """Simulates an authenticated user interacting with the IoTGuard API."""

    wait_time = between(0.5, 2.0)

    _access_token: str = ""

    def on_start(self) -> None:
        """Authenticate at the start of each user session.

        If authentication fails (e.g., the user doesn't exist), the load test
        continues with unauthenticated requests so that /health still works.
        """
        resp = self.client.post(
            "/auth/token",
            json={"username": "admin", "password": "admin"},
        )
        if resp.status_code == 200:
            self._access_token = resp.json().get("access_token", "")

    @property
    def _auth_headers(self) -> dict[str, str]:
        if self._access_token:
            return {"Authorization": f"Bearer {self._access_token}"}
        return {}

    # ------------------------------------------------------------------
    # Tasks
    # ------------------------------------------------------------------

    @task(5)
    def health_check(self) -> None:
        """High-frequency liveness probe."""
        self.client.get("/health", name="/health")

    @task(3)
    def list_devices(self) -> None:
        """List all registered devices."""
        self.client.get(
            "/v1/devices",
            headers=self._auth_headers,
            name="/v1/devices [GET]",
        )

    @task(2)
    def analyze_command(self) -> None:
        """Submit a command for security analysis."""
        commands = [
            "turn_on light",
            "unlock door",
            "set_temperature 22",
            "start_recording",
            "rm -rf /tmp",
            "format disk",
            "set_brightness 50",
            "lock",
            "turn_off camera",
        ]
        device_ids = [
            "door_lock_01",
            "camera_01",
            "thermostat_01",
            "light_01",
            "speaker_01",
        ]

        self.client.post(
            "/v1/analyze",
            json={
                "command": random.choice(commands),
                "device_id": random.choice(device_ids),
            },
            headers=self._auth_headers,
            name="/v1/analyze [POST]",
        )

    @task(1)
    def create_and_delete_device(self) -> None:
        """Create a temporary device and then delete it."""
        dev_id = f"load-test-{uuid.uuid4().hex[:8]}"
        create_resp = self.client.post(
            "/v1/devices",
            json={
                "device_id": dev_id,
                "name": f"Load Test {dev_id}",
                "device_type": "generic",
            },
            headers=self._auth_headers,
            name="/v1/devices [POST]",
        )
        if create_resp.status_code == 201:
            device_uuid = create_resp.json().get("id")
            if device_uuid:
                self.client.delete(
                    f"/v1/devices/{device_uuid}",
                    headers=self._auth_headers,
                    name="/v1/devices/{id} [DELETE]",
                )

    @task(1)
    def get_analysis_history(self) -> None:
        """Query analysis history."""
        self.client.get(
            "/v1/analysis/history",
            headers=self._auth_headers,
            name="/v1/analysis/history [GET]",
        )

    @task(1)
    def list_rules(self) -> None:
        """List security rules."""
        self.client.get(
            "/v1/rules",
            headers=self._auth_headers,
            name="/v1/rules [GET]",
        )
