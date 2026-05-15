"""Policy tests."""

from __future__ import annotations

from ledgersoul.agent.memory import AgentMemory
from ledgersoul.agent.models import AgentEvent
from ledgersoul.agent.planner import create_plan
from ledgersoul.agent.policies import apply_policy


def test_low_value_failed_payment_does_not_require_human(config):
    event = AgentEvent(event_id="e1", type="payment.failed", amount=100,
                       customer_id="c", payment_id="p")
    plan = create_plan(event, config)
    plan = apply_policy(event, plan, config, AgentMemory(config.state_dir))
    assert plan.requires_human is False
    assert plan.event_classification == "payment_failed"


def test_high_value_refund_requires_human(config):
    event = AgentEvent(event_id="e2", type="refund.requested", amount=500000,
                       customer_id="c", payment_id="p")
    plan = create_plan(event, config)
    plan = apply_policy(event, plan, config, AgentMemory(config.state_dir))
    assert plan.requires_human is True
    assert plan.risk_level == "high"


def test_suspicious_event_requires_human(config):
    event = AgentEvent(event_id="e3", type="payment.suspicious", amount=100,
                       customer_id="c", payment_id="p")
    plan = create_plan(event, config)
    plan = apply_policy(event, plan, config, AgentMemory(config.state_dir))
    assert plan.requires_human is True


def test_unknown_event_requires_human(config):
    event = AgentEvent(event_id="e4", type="something.weird")
    plan = create_plan(event, config)
    plan = apply_policy(event, plan, config, AgentMemory(config.state_dir))
    assert plan.requires_human is True
    assert plan.event_classification == "unknown"


def test_amount_above_threshold_requires_human(config):
    event = AgentEvent(event_id="e5", type="payment.failed", amount=10_000_001,
                       customer_id="c", payment_id="p")
    plan = create_plan(event, config)
    plan = apply_policy(event, plan, config, AgentMemory(config.state_dir))
    assert plan.requires_human is True
