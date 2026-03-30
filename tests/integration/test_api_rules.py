"""Integration tests for Rule CRUD and test endpoint."""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from iotguard.db.models import SecurityRule


class TestRuleList:
    """Test GET /v1/rules."""

    async def test_list_rules_empty(
        self,
        test_client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        resp = await test_client.get("/v1/rules", headers=auth_headers)
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    async def test_list_rules_with_data(
        self,
        test_client: AsyncClient,
        auth_headers: dict[str, str],
        db_session: AsyncSession,
    ) -> None:
        rule = SecurityRule(
            id=uuid.uuid4(),
            name="list-test-rule",
            description="Test rule for listing",
            pattern=r"rm\s+-rf",
            action="BLOCK",
            is_active=True,
            priority=10,
        )
        db_session.add(rule)
        await db_session.commit()

        resp = await test_client.get("/v1/rules", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 1


class TestRuleCreate:
    """Test POST /v1/rules."""

    async def test_create_rule(
        self,
        test_client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        resp = await test_client.post(
            "/v1/rules",
            json={
                "name": "no-format-command",
                "description": "Block format commands",
                "pattern": r"format\s+",
                "action": "BLOCK",
                "priority": 5,
            },
            headers=auth_headers,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "no-format-command"
        assert data["action"] == "BLOCK"
        assert data["priority"] == 5

    async def test_create_rule_with_warn_action(
        self,
        test_client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        resp = await test_client.post(
            "/v1/rules",
            json={
                "name": "warn-unlock",
                "pattern": r"unlock",
                "action": "WARN",
                "priority": 50,
            },
            headers=auth_headers,
        )
        assert resp.status_code == 201
        assert resp.json()["action"] == "WARN"

    async def test_create_rule_with_log_action(
        self,
        test_client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        resp = await test_client.post(
            "/v1/rules",
            json={
                "name": "log-everything",
                "pattern": r".*",
                "action": "LOG",
                "priority": 1000,
            },
            headers=auth_headers,
        )
        assert resp.status_code == 201
        assert resp.json()["action"] == "LOG"

    async def test_create_rule_invalid_action(
        self,
        test_client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        resp = await test_client.post(
            "/v1/rules",
            json={
                "name": "bad-action",
                "pattern": r"x",
                "action": "DESTROY",
            },
            headers=auth_headers,
        )
        assert resp.status_code == 422

    async def test_create_rule_requires_name(
        self,
        test_client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        resp = await test_client.post(
            "/v1/rules",
            json={"pattern": r"x", "action": "BLOCK"},
            headers=auth_headers,
        )
        assert resp.status_code == 422


class TestRuleDelete:
    """Test DELETE /v1/rules/{id}."""

    async def test_delete_rule(
        self,
        test_client: AsyncClient,
        auth_headers: dict[str, str],
        db_session: AsyncSession,
    ) -> None:
        rule = SecurityRule(
            id=uuid.uuid4(),
            name="delete-me-rule",
            pattern=r"delete_test",
            action="LOG",
            is_active=True,
            priority=100,
        )
        db_session.add(rule)
        await db_session.commit()

        resp = await test_client.delete(
            f"/v1/rules/{rule.id}",
            headers=auth_headers,
        )
        assert resp.status_code == 204

    async def test_delete_nonexistent_rule(
        self,
        test_client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        fake_id = uuid.uuid4()
        resp = await test_client.delete(
            f"/v1/rules/{fake_id}",
            headers=auth_headers,
        )
        assert resp.status_code == 404


class TestRuleTestEndpoint:
    """Test POST /v1/rules/test."""

    async def test_test_endpoint_requires_auth(
        self,
        test_client: AsyncClient,
    ) -> None:
        resp = await test_client.post(
            "/v1/rules/test",
            json={"command": "rm -rf /"},
        )
        assert resp.status_code == 401
