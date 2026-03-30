"""Pydantic models for the analysis pipeline.

These models define the data contracts between API endpoints, service layers,
and analysis engines.
"""

from __future__ import annotations

import enum
from typing import Any

from pydantic import BaseModel, Field


class RiskLevel(str, enum.Enum):
    """Ordered risk enumeration from safest to most dangerous."""

    NONE = "NONE"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


# ---------------------------------------------------------------------------
# Core result model (used by engines and the service)
# ---------------------------------------------------------------------------


class AnalysisResult(BaseModel):
    """Unified output of the analysis pipeline."""

    risk_level: RiskLevel
    explanation: str
    suggestions: list[str] = Field(default_factory=list)
    safe_alternatives: list[str] = Field(default_factory=list)
    rule_violations: list[str] = Field(default_factory=list)
    was_blocked: bool = False


# ---------------------------------------------------------------------------
# Request / response models (used by the API layer)
# ---------------------------------------------------------------------------


class AnalysisRequest(BaseModel):
    """Incoming analysis request from the API."""

    command: str = Field(..., min_length=1, max_length=4096)
    device_id: str = Field(..., min_length=1, max_length=128)
    user_context: dict[str, Any] = Field(default_factory=dict)


class AnalysisResponse(BaseModel):
    """Serialised analysis result returned to clients."""

    command: str
    device_id: str
    risk_level: RiskLevel
    explanation: str
    suggestions: list[str] = Field(default_factory=list)
    safe_alternatives: list[str] = Field(default_factory=list)
    rule_violations: list[str] = Field(default_factory=list)
    was_blocked: bool = False
