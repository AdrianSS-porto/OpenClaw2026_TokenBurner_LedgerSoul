"""Tiny explicit tool registry.

Tools must be invoked through this dict. Adding a tool means:
1. implement under `ledgersoul.tools`
2. register here
3. document in `tools.md`
4. add a verifier rule and a test
"""

from __future__ import annotations

from typing import Callable

from ledgersoul.tools.approvals import create_approval_request
from ledgersoul.tools.audit import write_audit_log
from ledgersoul.tools.doku_mcp import call_doku_mcp_tool, list_doku_mcp_tools
from ledgersoul.tools.messaging import draft_customer_message
from ledgersoul.tools.payments import (
    check_payment_status,
    create_recovery_link,
    get_transaction_by_invoice_number,
)

TOOL_REGISTRY: dict[str, Callable] = {
    "check_payment_status": check_payment_status,
    "create_recovery_link": create_recovery_link,
    "get_transaction_by_invoice_number": get_transaction_by_invoice_number,
    "draft_customer_message": draft_customer_message,
    "create_approval_request": create_approval_request,
    "write_audit_log": write_audit_log,
    "list_doku_mcp_tools": list_doku_mcp_tools,
    "call_doku_mcp_tool": call_doku_mcp_tool,
}


def get_tool(name: str) -> Callable:
    try:
        return TOOL_REGISTRY[name]
    except KeyError as exc:
        raise ValueError(f"Unknown tool: {name}") from exc
