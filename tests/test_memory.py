from ledgersoul.agent.memory import AgentMemory


def test_memory_marks_processed_with_status(tmp_path):
    memory = AgentMemory(str(tmp_path))

    assert memory.is_processed("evt_1") is False
    memory.mark_processed("evt_1", "completed")

    assert memory.is_processed("evt_1") is True
    summary = memory.get_state_summary()
    assert summary["processed_count"] == 1
    assert summary["last_processed"][-1] == {"event_id": "evt_1", "status": "completed"}


def test_memory_appends_audit_memory_and_approval(tmp_path):
    memory = AgentMemory(str(tmp_path))

    memory.append_audit({"event_id": "evt_1", "action": "x"})
    memory.append_memory({"event_id": "evt_1", "status": "completed"})
    memory.append_pending_approval({"event_id": "evt_2", "approval_id": "a1"})

    summary = memory.get_state_summary()
    assert summary["audit_count"] == 1
    assert summary["memory_count"] == 1
    assert summary["pending_approvals_count"] == 1
    assert memory.has_approval_for("evt_2") is True
