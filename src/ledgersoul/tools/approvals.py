"""Approval request tool."""

from __future__ import annotations

from typing import Any

from ledgersoul.agent.models import AgentEvent


def create_approval_request(event: AgentEvent, reason: str) -> dict[str, Any]:
    return {
        "approval_id": f"approval_{event.event_id}",
        "event_id": event.event_id,
        "reason": reason,
        "status": "pending",
    }
