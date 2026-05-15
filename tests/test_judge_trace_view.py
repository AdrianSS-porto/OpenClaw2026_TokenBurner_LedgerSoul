"""Judge trace summary tests."""

from __future__ import annotations

from ledgersoul.judge.trace_view import build_timeline, summarize_trace


def test_build_timeline_explains_agent_lifecycle() -> None:
    trace = {
        "status": "completed",
        "agent_profile": {"loaded": True, "documents": {"agent.md": {"exists": True}}},
        "event": {"event_id": "evt_1"},
        "plan": {
            "goal": "Reconcile transaction",
            "event_classification": "transaction_lookup_requested",
            "risk_level": "low",
        },
        "tool_results": [{"tool": "get_transaction_by_invoice_number", "ok": True, "result": {}}],
        "verification": {"ok": True, "reason": "transaction_lookup_verified"},
    }

    timeline = build_timeline(trace)

    assert timeline[0]["label"] == "Agent contract loaded"
    assert any(step["label"] == "Tool executed" for step in timeline)
    assert timeline[-1]["label"] == "Final status"


def test_summarize_trace_returns_safe_judge_payload() -> None:
    trace = {
        "status": "completed",
        "event": {"event_id": "evt_1"},
        "plan": {"event_classification": "transaction_lookup_requested", "risk_level": "low"},
        "tool_results": [{"tool": "write_audit_log", "ok": True, "result": {"Authorization": "Basic leak"}}],
        "verification": {"ok": True, "reason": "ok"},
    }

    summary = summarize_trace(trace)

    assert summary["status"] == "completed"
    assert summary["classification"] == "transaction_lookup_requested"
    assert summary["tools_used"] == ["write_audit_log"]
    assert summary["redacted_trace"]["tool_results"][0]["result"]["Authorization"] == "[REDACTED]"
