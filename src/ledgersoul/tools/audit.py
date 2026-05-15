"""Audit tool: explicit `write_audit_log` is the only sanctioned way to record audits."""

from __future__ import annotations

from typing import Any

from ledgersoul.agent.memory import AgentMemory
from ledgersoul.agent.models import AgentEvent


def build_audit_entry(event: AgentEvent, action: str, result: dict[str, Any]) -> dict[str, Any]:
    return {
        "event_id": event.event_id,
        "event_type": event.type,
        "action": action,
        "result": result,
    }


def write_audit_log(
    memory: AgentMemory,
    event: AgentEvent,
    action: str,
    result: dict[str, Any],
) -> dict[str, Any]:
    """Append an audit entry to `state/audit_log.jsonl`.

    Returns a dict suitable for inclusion in a `ToolResult.result`.
    """
    entry = build_audit_entry(event, action, result)
    memory.append_audit(entry)
    return {"written": True, "entry": entry}
