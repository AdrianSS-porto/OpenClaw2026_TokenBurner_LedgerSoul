"""Deterministic event-to-plan mapping."""

from __future__ import annotations

from ledgersoul.agent.config import AgentConfig
from ledgersoul.agent.models import AgentEvent, AgentPlan, PlanStep, RiskLevel

CLASSIFICATIONS = {
    "payment.failed": "payment_failed",
    "payment.succeeded": "payment_succeeded",
    "payment.recovered": "payment_recovered",
    "refund.requested": "refund_requested",
    "payment.suspicious": "suspicious_payment",
    "payment.api_failure": "api_failure",
    "transaction.lookup_requested": "transaction_lookup_requested",
    "doku.payment_methods_requested": "doku_payment_methods_requested",
}


def classify(event: AgentEvent) -> str:
    return CLASSIFICATIONS.get(event.type, "unknown")


def _risk_for(classification: str, event: AgentEvent, config: AgentConfig) -> RiskLevel:
    if classification == "payment_failed":
        return "medium"
    if classification in ("payment_succeeded", "payment_recovered"):
        return "low"
    if classification == "transaction_lookup_requested":
        return "low"
    if classification == "doku_payment_methods_requested":
        return "low"
    if classification == "refund_requested":
        if (event.amount or 0) > config.max_autonomous_amount:
            return "high"
        return "high" if config.require_human_approval else "medium"
    if classification == "suspicious_payment":
        return "high"
    if classification == "api_failure":
        return "medium"
    return "unknown"


def create_plan(event: AgentEvent, config: AgentConfig) -> AgentPlan:
    classification = classify(event)
    risk = _risk_for(classification, event, config)

    if classification == "payment_failed":
        steps = [
            PlanStep(name="check_payment_status", tool="check_payment_status",
                     reason="Confirm latest payment state"),
            PlanStep(name="create_recovery_link", tool="create_recovery_link",
                     reason="Offer customer a recovery path"),
            PlanStep(name="draft_customer_message", tool="draft_customer_message",
                     reason="Prepare customer-facing recovery message"),
            PlanStep(name="write_audit_log", tool="write_audit_log",
                     reason="Persist the recovery decision"),
        ]
        return AgentPlan(
            goal="Recover failed payment safely",
            event_classification=classification,
            risk_level=risk,
            requires_human=False,
            steps=steps,
        )

    if classification in ("payment_succeeded", "payment_recovered"):
        steps = [
            PlanStep(name="write_audit_log", tool="write_audit_log",
                     reason="Record successful payment outcome"),
        ]
        return AgentPlan(
            goal="Record successful payment",
            event_classification=classification,
            risk_level=risk,
            requires_human=False,
            steps=steps,
        )

    if classification == "transaction_lookup_requested":
        steps = [
            PlanStep(name="get_transaction_by_invoice_number", tool="get_transaction_by_invoice_number",
                     reason="Look up provider transaction details by invoice number"),
            PlanStep(name="write_audit_log", tool="write_audit_log",
                     reason="Persist the transaction reconciliation result"),
        ]
        return AgentPlan(
            goal="Reconcile transaction by invoice number",
            event_classification=classification,
            risk_level=risk,
            requires_human=False,
            steps=steps,
        )

    if classification == "doku_payment_methods_requested":
        steps = [
            PlanStep(name="call_doku_mcp_tool", tool="call_doku_mcp_tool",
                     reason="Call the allowlisted DOKU MCP read-only payment-methods tool"),
            PlanStep(name="write_audit_log", tool="write_audit_log",
                     reason="Persist the DOKU payment-methods lookup result"),
        ]
        return AgentPlan(
            goal="List DOKU sandbox payment methods",
            event_classification=classification,
            risk_level=risk,
            requires_human=False,
            steps=steps,
        )

    if classification == "refund_requested":
        steps = [
            PlanStep(name="create_approval_request", tool="create_approval_request",
                     reason="Refund requires human approval"),
            PlanStep(name="write_audit_log", tool="write_audit_log",
                     reason="Persist the escalation"),
        ]
        return AgentPlan(
            goal="Escalate refund for human approval",
            event_classification=classification,
            risk_level=risk,
            requires_human=True,
            steps=steps,
        )

    if classification == "suspicious_payment":
        steps = [
            PlanStep(name="create_approval_request", tool="create_approval_request",
                     reason="Suspicious payment requires review"),
            PlanStep(name="write_audit_log", tool="write_audit_log",
                     reason="Persist the escalation"),
        ]
        return AgentPlan(
            goal="Escalate suspicious payment",
            event_classification=classification,
            risk_level=risk,
            requires_human=True,
            steps=steps,
        )

    if classification == "api_failure":
        steps = [
            PlanStep(name="check_payment_status", tool="check_payment_status",
                     reason="Probe provider state after API failure"),
            PlanStep(name="create_approval_request", tool="create_approval_request",
                     reason="Escalate when verification cannot complete"),
            PlanStep(name="write_audit_log", tool="write_audit_log",
                     reason="Persist the escalation"),
        ]
        return AgentPlan(
            goal="Handle provider API failure",
            event_classification=classification,
            risk_level=risk,
            requires_human=True,
            steps=steps,
        )

    # unknown
    steps = [
        PlanStep(name="create_approval_request", tool="create_approval_request",
                 reason="Unknown event type requires human review"),
        PlanStep(name="write_audit_log", tool="write_audit_log",
                 reason="Persist the escalation"),
    ]
    return AgentPlan(
        goal="Escalate unknown event",
        event_classification="unknown",
        risk_level="unknown",
        requires_human=True,
        steps=steps,
    )


def duplicate_plan(event: AgentEvent) -> AgentPlan:
    return AgentPlan(
        goal="Acknowledge duplicate event without re-acting",
        event_classification="duplicate_event",
        risk_level="low",
        requires_human=False,
        steps=[
            PlanStep(name="write_audit_log", tool="write_audit_log",
                     reason="Record duplicate-event acknowledgement"),
        ],
    )
