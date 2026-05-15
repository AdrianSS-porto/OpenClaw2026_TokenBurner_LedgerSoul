"""Run reflection."""

from __future__ import annotations

from typing import Any

from ledgersoul.agent.models import AgentEvent, AgentPlan, ToolResult, VerificationResult


def reflect(
    event: AgentEvent,
    plan: AgentPlan,
    tool_results: list[ToolResult],
    verification: VerificationResult,
) -> dict[str, Any]:
    used = [r.tool for r in tool_results]
    human_required = plan.requires_human or plan.event_classification == "unknown"

    if plan.event_classification == "duplicate_event":
        summary = f"Duplicate event {event.event_id} acknowledged without re-acting."
        confidence = 0.99 if verification.ok else 0.4
        next_step = "No further action."
    elif human_required:
        summary = (
            f"{plan.event_classification} for event {event.event_id} escalated for "
            f"human approval."
        )
        confidence = 0.9 if verification.ok else 0.3
        next_step = "Wait for human reviewer to resolve approval request."
    elif plan.event_classification == "payment_failed" and verification.ok:
        summary = (
            f"Payment {event.payment_id} verified failed; recovery link drafted and "
            f"audit log written."
        )
        confidence = 0.9
        next_step = "Wait for customer to complete recovery."
    elif plan.event_classification in ("payment_succeeded", "payment_recovered") and verification.ok:
        summary = f"{plan.event_classification} for event {event.event_id} recorded."
        confidence = 0.95
        next_step = "No further action."
    elif not verification.ok:
        summary = f"Run failed verification: {verification.reason}."
        confidence = 0.2
        next_step = "Operator should inspect trace and audit log."
    else:
        summary = f"Run completed for event {event.event_id}."
        confidence = 0.7
        next_step = "Monitor for follow-up events."

    return {
        "event_id": event.event_id,
        "outcome": verification.reason,
        "confidence": confidence,
        "human_required": human_required,
        "summary": summary,
        "tools_used": used,
        "next_step": next_step,
    }
