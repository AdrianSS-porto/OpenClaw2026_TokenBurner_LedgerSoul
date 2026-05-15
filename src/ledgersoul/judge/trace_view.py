"""Build judge-safe summaries from LedgerSoul runtime traces."""

from __future__ import annotations

from typing import Any

from ledgersoul.judge.security import redact_sensitive


def build_timeline(trace: dict[str, Any]) -> list[dict[str, Any]]:
    """Return a human-readable lifecycle timeline for a trace."""
    profile = trace.get("agent_profile", {}) or {}
    plan = trace.get("plan", {}) or {}
    verification = trace.get("verification", {}) or {}
    timeline: list[dict[str, Any]] = [
        {
            "label": "Agent contract loaded",
            "ok": profile.get("loaded") is True,
            "detail": "agent.md loaded" if profile.get("documents", {}).get("agent.md", {}).get("exists") else "agent.md missing",
        },
        {
            "label": "Event received",
            "ok": bool(trace.get("event", {}).get("event_id")),
            "detail": trace.get("event", {}).get("event_id"),
        },
        {
            "label": "Event classified",
            "ok": bool(plan.get("event_classification")),
            "detail": plan.get("event_classification"),
        },
        {
            "label": "Plan selected",
            "ok": bool(plan.get("goal")),
            "detail": plan.get("goal"),
        },
    ]

    for result in trace.get("tool_results", []) or []:
        timeline.append(
            {
                "label": "Tool executed",
                "ok": result.get("ok") is True,
                "detail": result.get("tool"),
            }
        )

    timeline.extend(
        [
            {
                "label": "Verification",
                "ok": verification.get("ok") is True,
                "detail": verification.get("reason"),
            },
            {
                "label": "Final status",
                "ok": trace.get("status") in {"completed", "duplicate", "escalated"},
                "detail": trace.get("status"),
            },
        ]
    )
    return timeline


def summarize_trace(trace: dict[str, Any]) -> dict[str, Any]:
    """Return the safe judge payload for a raw trace."""
    redacted = redact_sensitive(trace)
    plan = redacted.get("plan", {}) or {}
    return {
        "status": redacted.get("status"),
        "event_id": redacted.get("event", {}).get("event_id"),
        "classification": plan.get("event_classification"),
        "risk_level": plan.get("risk_level"),
        "goal": plan.get("goal"),
        "tools_used": [result.get("tool") for result in redacted.get("tool_results", []) or []],
        "verification": redacted.get("verification"),
        "timeline": build_timeline(redacted),
        "redacted_trace": redacted,
    }
