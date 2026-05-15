from ledgersoul.agent.tool_registry import TOOL_REGISTRY, get_tool


def test_tiny_registry_contains_required_tools():
    assert set(TOOL_REGISTRY) == {
        "check_payment_status",
        "create_recovery_link",
        "get_transaction_by_invoice_number",
        "draft_customer_message",
        "create_approval_request",
        "write_audit_log",
        "list_doku_mcp_tools",
        "call_doku_mcp_tool",
    }


def test_get_tool_returns_callable():
    assert callable(get_tool("check_payment_status"))


def test_get_tool_rejects_unknown_tool():
    try:
        get_tool("does_not_exist")
    except ValueError as exc:
        assert "Unknown tool" in str(exc)
    else:
        raise AssertionError("expected ValueError")
