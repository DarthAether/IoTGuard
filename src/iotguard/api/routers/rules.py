"""Security rule management endpoints."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field
from fastapi import APIRouter, HTTPException, status

from iotguard.api.dependencies import (
    AnalysisServiceDep,
    DbSession,
    OperatorUser,
    ViewerUser,
)
from iotguard.db.models import SecurityRule
from iotguard.db.repositories import SecurityRuleRepository

router = APIRouter(prefix="/v1/rules", tags=["rules"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class RuleOut(BaseModel):
    id: str
    name: str
    description: str | None
    pattern: str
    action: str
    is_active: bool
    priority: int
    created_at: datetime

    class Config:
        from_attributes = True


class RuleCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=256)
    description: str | None = None
    pattern: str = Field(..., min_length=1)
    action: str = Field("BLOCK", pattern=r"^(BLOCK|WARN|LOG)$")
    priority: int = Field(100, ge=0, le=10000)


class RuleUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    pattern: str | None = None
    action: str | None = Field(None, pattern=r"^(BLOCK|WARN|LOG)$")
    is_active: bool | None = None
    priority: int | None = Field(None, ge=0, le=10000)


class RuleTestRequest(BaseModel):
    command: str


class RuleTestResponse(BaseModel):
    blocked: bool
    reason: str
    matched_rules: list[str]


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("", response_model=list[RuleOut])
async def list_rules(
    user: ViewerUser,
    session: DbSession,
    offset: int = 0,
    limit: int = 50,
) -> list[RuleOut]:
    repo = SecurityRuleRepository(session)
    rules = await repo.list_all(offset=offset, limit=limit)
    return [
        RuleOut(
            id=str(r.id),
            name=r.name,
            description=r.description,
            pattern=r.pattern,
            action=r.action,
            is_active=r.is_active,
            priority=r.priority,
            created_at=r.created_at,
        )
        for r in rules
    ]


@router.post("", response_model=RuleOut, status_code=201)
async def create_rule(
    body: RuleCreate,
    user: OperatorUser,
    session: DbSession,
) -> RuleOut:
    repo = SecurityRuleRepository(session)
    rule = SecurityRule(
        name=body.name,
        description=body.description,
        pattern=body.pattern,
        action=body.action,
        priority=body.priority,
    )
    rule = await repo.create(rule)
    return RuleOut(
        id=str(rule.id),
        name=rule.name,
        description=rule.description,
        pattern=rule.pattern,
        action=rule.action,
        is_active=rule.is_active,
        priority=rule.priority,
        created_at=rule.created_at,
    )


@router.patch("/{rule_id}", response_model=RuleOut)
async def update_rule(
    rule_id: uuid.UUID,
    body: RuleUpdate,
    user: OperatorUser,
    session: DbSession,
) -> RuleOut:
    repo = SecurityRuleRepository(session)
    existing = await repo.get_by_id(rule_id)  # type: ignore[arg-type]
    if existing is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rule not found")
    values = body.model_dump(exclude_unset=True)
    if values:
        await repo.update(rule_id, values)
        await session.refresh(existing)
    return RuleOut(
        id=str(existing.id),
        name=existing.name,
        description=existing.description,
        pattern=existing.pattern,
        action=existing.action,
        is_active=existing.is_active,
        priority=existing.priority,
        created_at=existing.created_at,
    )


@router.delete("/{rule_id}", status_code=204)
async def delete_rule(
    rule_id: uuid.UUID,
    user: OperatorUser,
    session: DbSession,
) -> None:
    repo = SecurityRuleRepository(session)
    existing = await repo.get_by_id(rule_id)  # type: ignore[arg-type]
    if existing is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rule not found")
    await repo.delete(rule_id)


@router.post("/test", response_model=RuleTestResponse)
async def test_rules(
    body: RuleTestRequest,
    user: OperatorUser,
    analysis_svc: AnalysisServiceDep,
) -> RuleTestResponse:
    """Dry-run a command against active security rules."""
    result = await analysis_svc.test_command_against_rules(body.command)
    return RuleTestResponse(
        blocked=result["blocked"],
        reason=result.get("reason", ""),
        matched_rules=result.get("matched_rules", []),
    )
