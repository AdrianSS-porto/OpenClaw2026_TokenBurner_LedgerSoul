"""Judge workflow registry tests."""

from __future__ import annotations

import pytest

from ledgersoul.judge.workflows import JUDGE_WORKFLOWS, build_event_for_workflow, validate_workflow_inputs


def test_registry_contains_only_expected_mvp_workflows() -> None:
    assert set(JUDGE_WORKFLOWS) == {"transaction_lookup", "doku_payment_methods"}
    assert JUDGE_WORKFLOWS["transaction_lookup"].risk == "read_only"
    assert JUDGE_WORKFLOWS["doku_payment_methods"].risk == "read_only"


def test_transaction_lookup_builds_safe_event() -> None:
    event = build_event_for_workflow(
        "transaction_lookup",
        {"invoice_number": "INV-LEDGERSOUL-001", "ignored": "not allowed"},
    )

    assert event["type"] == "transaction.lookup_requested"
    assert event["event_id"].startswith("judge_transaction_lookup_")
    assert event["metadata"]["invoice_number"] == "INV-LEDGERSOUL-001"
    assert event["metadata"]["source"] == "judge_mode"
    assert "ignored" not in event["metadata"]


def test_payment_methods_builds_safe_doku_event() -> None:
    event = build_event_for_workflow("doku_payment_methods", {"tool_name": "not_allowed"})

    assert event["type"] == "doku.payment_methods_requested"
    assert event["metadata"]["doku_tool"] == "get_merchant_payment_methods"
    assert "tool_name" not in event["metadata"]


def test_unknown_workflow_is_rejected() -> None:
    with pytest.raises(ValueError):
        validate_workflow_inputs("not_allowed", {})
