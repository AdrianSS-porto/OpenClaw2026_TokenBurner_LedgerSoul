def test_first_event_processes_normally(runtime, base_failed_event):
    result = runtime.run(base_failed_event)

    assert result.status == "completed"
    assert result.plan.event_classification == "payment_failed"
    assert "create_recovery_link" in [r.tool for r in result.tool_results]


def test_same_event_id_again_returns_duplicate(runtime, base_failed_event):
    first = runtime.run(base_failed_event)
    second = runtime.run(base_failed_event)

    assert first.status == "completed"
    assert second.status == "duplicate"
    assert second.plan.event_classification == "duplicate_event"


def test_duplicate_does_not_create_second_recovery_link(runtime, base_failed_event):
    runtime.run(base_failed_event)
    duplicate = runtime.run(base_failed_event)

    tools = [r.tool for r in duplicate.tool_results]
    assert tools == ["write_audit_log"]
    assert "create_recovery_link" not in tools
    assert duplicate.verification.ok is True
