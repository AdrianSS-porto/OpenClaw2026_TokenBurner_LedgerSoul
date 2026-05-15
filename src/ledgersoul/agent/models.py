"""Pydantic models and standardized run statuses for LedgerSoul."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

RunStatus = Literal[
    "completed",
    "escalated",
    "duplicate",
    "blocked",
    "failed_verification",
    "error",
]

RiskLevel = Literal["low", "medium", "high", "unknown"]


class AgentEvent(BaseModel):
    event_id: str
    type: str
    timestamp: str | None = None
    amount: int | None = None
    currency: str | None = None
    customer_id: str | None = None
    payment_id: str | None = None
    reason: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class PlanStep(BaseModel):
    name: str
    tool: str | None = None
    reason: str


class AgentPlan(BaseModel):
    goal: str
    event_classification: str
    risk_level: RiskLevel
    requires_human: bool
    steps: list[PlanStep]


class ToolResult(BaseModel):
    tool: str
    ok: bool
    result: dict[str, Any]
    error: str | None = None


class VerificationResult(BaseModel):
    ok: bool
    reason: str
    evidence: dict[str, Any] = Field(default_factory=dict)


class AgentRunResult(BaseModel):
    event_id: str
    status: RunStatus
    plan: AgentPlan
    tool_results: list[ToolResult]
    verification: VerificationResult
    reflection: dict[str, Any]
    trace_path: str | None = None
