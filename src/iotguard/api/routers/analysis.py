"""Command analysis endpoints."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field
from fastapi import APIRouter, Query

from iotguard.analysis.models import (
    AnalysisRequest as AnalysisRequestModel,
    AnalysisResponse as AnalysisResponseModel,
)
from iotguard.api.dependencies import (
    AnalysisServiceDep,
    DbSession,
    DeviceServiceDep,
    OperatorUser,
    ViewerUser,
)
from iotguard.db.repositories import CommandLogRepository

router = APIRouter(prefix="/v1", tags=["analysis"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class AnalyzeRequest(BaseModel):
    command: str = Field(..., min_length=1, max_length=4096)
    device_id: str = Field(..., min_length=1, max_length=128)
    user_context: dict[str, Any] = Field(default_factory=dict)


class AnalysisResponse(BaseModel):
    command: str
    device_id: str
    risk_level: str
    explanation: str
    suggestions: list[str] = Field(default_factory=list)
    safe_alternatives: list[str] = Field(default_factory=list)
    rule_violations: list[str] = Field(default_factory=list)
    was_blocked: bool = False


class AnalyzeAndExecuteResponse(BaseModel):
    analysis: AnalysisResponse
    executed: bool = False
    execution_result: dict[str, Any] | None = None


class CommandLogItem(BaseModel):
    id: str
    device_id: str | None
    command: str
    risk_level: str
    risk_explanation: str | None
    was_blocked: bool
    timestamp: datetime

    class Config:
        from_attributes = True


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _to_response(body: AnalyzeRequest, result: object) -> AnalysisResponse:
    """Map an AnalysisResult from the service to the API response."""
    # result is an AnalysisResult (Pydantic BaseModel)
    r: Any = result
    return AnalysisResponse(
        command=body.command,
        device_id=body.device_id,
        risk_level=r.risk_level.value if hasattr(r.risk_level, "value") else str(r.risk_level),
        explanation=r.explanation,
        suggestions=r.suggestions,
        safe_alternatives=r.safe_alternatives,
        rule_violations=r.rule_violations,
        was_blocked=r.was_blocked,
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/analyze", response_model=AnalysisResponse)
async def analyze_command(
    body: AnalyzeRequest,
    user: OperatorUser,
    analysis_svc: AnalysisServiceDep,
) -> AnalysisResponse:
    """Analyse an IoT command for security risks."""
    req = AnalysisRequestModel(
        command=body.command,
        device_id=body.device_id,
        user_context=body.user_context,
    )
    result = await analysis_svc.analyze(req, user_id=uuid.UUID(user.sub))
    return _to_response(body, result)


@router.post("/analyze-and-execute", response_model=AnalyzeAndExecuteResponse)
async def analyze_and_execute(
    body: AnalyzeRequest,
    user: OperatorUser,
    analysis_svc: AnalysisServiceDep,
    device_svc: DeviceServiceDep,
) -> AnalyzeAndExecuteResponse:
    """Analyse a command, and if safe, execute it on the device."""
    req = AnalysisRequestModel(
        command=body.command,
        device_id=body.device_id,
        user_context=body.user_context,
    )
    result = await analysis_svc.analyze(req, user_id=uuid.UUID(user.sub))
    analysis_resp = _to_response(body, result)

    if result.was_blocked:
        return AnalyzeAndExecuteResponse(analysis=analysis_resp, executed=False)

    # Parse device_id to UUID for execution
    try:
        device_uuid = uuid.UUID(body.device_id)
    except ValueError:
        return AnalyzeAndExecuteResponse(analysis=analysis_resp, executed=False)

    exec_result = await device_svc.execute_command(
        device_uuid, body.command, user=user.sub,
    )
    return AnalyzeAndExecuteResponse(
        analysis=analysis_resp,
        executed=True,
        execution_result=exec_result,
    )


@router.get("/analysis/history", response_model=list[CommandLogItem])
async def analysis_history(
    user: ViewerUser,
    session: DbSession,
    device_id: uuid.UUID | None = Query(None),
    risk_level: str | None = Query(None),
    since: datetime | None = Query(None),
    until: datetime | None = Query(None),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=250),
) -> list[CommandLogItem]:
    """Query the command analysis history with optional filters."""
    repo = CommandLogRepository(session)
    logs = await repo.list_recent(
        offset=offset,
        limit=limit,
        device_id=device_id,
        risk_level=risk_level,
        since=since,
        until=until,
    )
    return [
        CommandLogItem(
            id=str(log.id),
            device_id=str(log.device_id) if log.device_id else None,
            command=log.command,
            risk_level=log.risk_level,
            risk_explanation=log.risk_explanation,
            was_blocked=log.was_blocked,
            timestamp=log.timestamp,
        )
        for log in logs
    ]
