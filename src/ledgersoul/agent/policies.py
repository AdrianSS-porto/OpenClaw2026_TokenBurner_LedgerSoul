"""Policy adjustments to the plan based on event, config, and memory state."""

from __future__ import annotations

from ledgersoul.agent.config import AgentConfig
from ledgersoul.agent.memory import AgentMemory
from ledgersoul.agent.models import AgentEvent, AgentPlan


def apply_policy(
    event: AgentEvent,
    plan: AgentPlan,
    config: AgentConfig,
    memory: AgentMemory,
) -> AgentPlan:
    """Adjust the plan in-place style: returns a possibly modified AgentPlan.

    Idempotency check is handled in `AgentRuntime` before this function. If a duplicate
    is encountered defensively here, force a no-op plan with `requires_human=False`.
    """
    # Duplicate defense (runtime should have already routed these).
    if memory.is_processed(event.event_id):
        plan.requires_human = False
        return plan

    # Amount threshold applies to money-moving or customer-impacting actions, not read-only lookup.
    if plan.event_classification != "transaction_lookup_requested" and (
        event.amount or 0
    ) > config.max_autonomous_amount:
        plan.requires_human = True

    # Unknown event always requires human
    if plan.event_classification == "unknown":
        plan.requires_human = True

    # Suspicious payments require human
    if plan.event_classification == "suspicious_payment":
        plan.requires_human = True

    # Refund + approval-required policy
    if plan.event_classification == "refund_requested" and config.require_human_approval:
        plan.requires_human = True

    # API failures require human in MVP (no real retry surface)
    if plan.event_classification == "api_failure":
        plan.requires_human = True

    return plan
