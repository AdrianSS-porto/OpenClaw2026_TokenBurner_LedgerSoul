"""Transaction lookup/reconciliation use case tests."""

from __future__ import annotations

import json

from ledgersoul.agent.models import AgentEvent
from ledgersoul.agent.planner import classify, create_plan
from ledgersoul.agent.runtime import AgentRuntime
from ledgersoul.tools.payments import get_transaction_by_invoice_number


def transaction_lookup_event() -> dict:
    return {
        "event_id": "evt_transaction_lookup_test_001",
        "type": "transaction.lookup_requested",
        "timestamp": "2026-05-15T11:00:00Z",
        "amount": 20000,
        "currency": "IDR",
        "customer_id": "cus_txn_test",
        "payment_id": "pay_txn_test",
        "reason": "customer_asks_order_status",
        "metadata": {
            "invoice_number": "INV-LEDGERSOUL-001",
            "customer_name": "Test Buyer",
        },
    }


def test_transaction_lookup_is_classified_and_planned(config) -> None:
    event = AgentEvent.model_validate(transaction_lookup_event())
    plan = create_plan(event, config)

    assert classify(event) == "transaction_lookup_requested"
    assert plan.goal == "Reconcile transaction by invoice number"
    assert plan.event_classification == "transaction_lookup_requested"
    assert plan.risk_level == "low"
    assert plan.requires_human is False
    assert [step.tool for step in plan.steps] == [
        "get_transaction_by_invoice_number",
        "write_audit_log",
    ]


def test_get_transaction_by_invoice_number_returns_mock_reconciliation_record() -> None:
    result = get_transaction_by_invoice_number("INV-LEDGERSOUL-001")

    assert result["invoice_number"] == "INV-LEDGERSOUL-001"
    assert result["transaction_status"] == "paid"
    assert result["payment_method"] == "DOKU Sandbox Checkout"
    assert result["source"] == "mock_transaction_registry"


def test_runtime_completes_transaction_lookup_and_writes_trace(runtime: AgentRuntime) -> None:
    result = runtime.run(transaction_lookup_event())

    assert result.status == "completed"
    assert result.plan.event_classification == "transaction_lookup_requested"
    assert result.verification.ok is True
    assert result.verification.reason == "transaction_lookup_verified"
    assert result.verification.evidence["invoice_number"] == "INV-LEDGERSOUL-001"
    assert [tool.tool for tool in result.tool_results] == [
        "get_transaction_by_invoice_number",
        "write_audit_log",
    ]

    assert result.trace_path is not None
    with open(result.trace_path, "r", encoding="utf-8") as f:
        trace = json.load(f)
    assert trace["plan"]["goal"] == "Reconcile transaction by invoice number"
    assert trace["tool_results"][0]["result"]["transaction_status"] == "paid"
