"""Read-only DOKU payment-method workflow runtime tests."""

from __future__ import annotations

from ledgersoul.agent.models import AgentEvent
from ledgersoul.agent.planner import create_plan


def doku_payment_methods_event() -> dict:
    return {
        "event_id": "evt_doku_payment_methods",
        "type": "doku.payment_methods_requested",
        "metadata": {"source": "judge_mode"},
    }


def test_doku_payment_methods_plans_read_only_tool(config) -> None:
    event = AgentEvent.model_validate(doku_payment_methods_event())

    plan = create_plan(event, config)

    assert plan.event_classification == "doku_payment_methods_requested"
    assert plan.risk_level == "low"
    assert plan.requires_human is False
    assert [step.tool for step in plan.steps] == ["call_doku_mcp_tool", "write_audit_log"]


def test_doku_payment_methods_runtime_uses_registry_and_verifies(runtime, monkeypatch) -> None:
    calls: list[str] = []

    def fake_get_tool(name: str):
        calls.append(name)
        if name == "call_doku_mcp_tool":
            return lambda **kwargs: {
                "result": {"content": [{"type": "text", "text": "VIRTUAL_ACCOUNT"}]},
                "called_tool": kwargs["tool_name"],
            }
        if name == "write_audit_log":
            return lambda **kwargs: {"written": True, "entry": {"action": kwargs["action"]}}
        raise AssertionError(name)

    monkeypatch.setattr("ledgersoul.agent.executor.get_tool", fake_get_tool)

    result = runtime.run(doku_payment_methods_event())

    assert result.status == "completed"
    assert result.verification.ok is True
    assert result.verification.reason == "doku_payment_methods_verified"
    assert [tool.tool for tool in result.tool_results] == ["call_doku_mcp_tool", "write_audit_log"]
    assert result.tool_results[0].result["called_tool"] == "get_merchant_payment_methods"
    assert calls == ["call_doku_mcp_tool", "write_audit_log"]
