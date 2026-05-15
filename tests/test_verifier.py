from ledgersoul.agent.executor import execute_plan
from ledgersoul.agent.memory import AgentMemory
from ledgersoul.agent.models import AgentEvent, ToolResult
from ledgersoul.agent.planner import create_plan, duplicate_plan
from ledgersoul.agent.verifier import verify_run


def test_recovery_flow_verifies_when_url_exists(config):
    memory = AgentMemory(config.state_dir)
    event = AgentEvent(event_id="evt_v1", type="payment.failed", amount=100, customer_id="c", payment_id="p")
    plan = create_plan(event, config)
    results = execute_plan(event, plan, config, memory)

    verification = verify_run(event, plan, results)

    assert verification.ok is True
    assert verification.reason == "recovery_verified"
    assert verification.evidence["recovery_url"].startswith("https://mock-payments.local/recover/")


def test_approval_flow_verifies_when_approval_exists(config):
    memory = AgentMemory(config.state_dir)
    event = AgentEvent(event_id="evt_v2", type="refund.requested", amount=500000, customer_id="c", payment_id="p")
    plan = create_plan(event, config)
    results = execute_plan(event, plan, config, memory)

    verification = verify_run(event, plan, results)

    assert verification.ok is True
    assert verification.reason == "approval_recorded"
    assert verification.evidence["approval"]["status"] == "pending"


def test_verification_fails_if_required_tool_failed(config):
    event = AgentEvent(event_id="evt_v3", type="payment.failed", amount=100, customer_id="c", payment_id="p")
    plan = create_plan(event, config)
    results = [ToolResult(tool="check_payment_status", ok=False, result={}, error="boom")]

    verification = verify_run(event, plan, results)

    assert verification.ok is False
    assert verification.reason == "tool_failed:check_payment_status"


def test_duplicate_verifies_no_risky_action(config):
    event = AgentEvent(event_id="evt_v4", type="payment.failed")
    plan = duplicate_plan(event)
    results = [ToolResult(tool="write_audit_log", ok=True, result={"written": True})]

    verification = verify_run(event, plan, results)

    assert verification.ok is True
    assert verification.reason == "duplicate_acknowledged"


def test_duplicate_fails_if_risky_action_happened(config):
    event = AgentEvent(event_id="evt_v5", type="payment.failed")
    plan = duplicate_plan(event)
    results = [ToolResult(tool="create_recovery_link", ok=True, result={"url": "x"})]

    verification = verify_run(event, plan, results)

    assert verification.ok is False
    assert verification.reason == "duplicate_executed_risky_tool"
