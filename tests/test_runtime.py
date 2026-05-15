from pathlib import Path


def test_full_payment_failed_lifecycle_returns_completed(runtime, base_failed_event):
    result = runtime.run(base_failed_event)

    assert result.status == "completed"
    assert result.verification.ok is True
    assert Path(result.trace_path).exists()


def test_high_value_refund_lifecycle_returns_escalated(runtime):
    event = {
        "event_id": "evt_refund_runtime_1",
        "type": "refund.requested",
        "amount": 500000,
        "customer_id": "cus_1",
        "payment_id": "pay_1",
    }

    result = runtime.run(event)

    assert result.status == "escalated"
    assert result.plan.requires_human is True
    assert "create_approval_request" in [r.tool for r in result.tool_results]


def test_trace_file_is_created(runtime, base_failed_event):
    result = runtime.run(base_failed_event)

    path = Path(result.trace_path)
    assert path.exists()
    assert path.parent.name == "traces"


def test_audit_log_is_appended(runtime, base_failed_event):
    runtime.run(base_failed_event)

    audit_path = Path(runtime.config.state_dir) / "audit_log.jsonl"
    assert audit_path.exists()
    assert "recovery_link_created" in audit_path.read_text()


def test_unknown_event_escalates(runtime):
    result = runtime.run({"event_id": "evt_unknown_1", "type": "weird.event"})

    assert result.status == "escalated"
    assert result.plan.event_classification == "unknown"
    assert result.verification.ok is True


def test_validation_error_returns_error(runtime):
    result = runtime.run({"type": "missing.event_id"})

    assert result.status == "error"
    assert result.verification.ok is False
