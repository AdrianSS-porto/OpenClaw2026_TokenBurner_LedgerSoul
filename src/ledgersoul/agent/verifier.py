"""Verifier: checks each required tool result and produces a VerificationResult."""

from __future__ import annotations

import json
from typing import Any

from ledgersoul.agent.models import AgentEvent, AgentPlan, ToolResult, VerificationResult


def _find(results: list[ToolResult], tool: str) -> ToolResult | None:
    for r in results:
        if r.tool == tool:
            return r
    return None


def _doku_content_payload(result: dict[str, Any]) -> dict[str, Any]:
    content = result.get("result", {}).get("content", [])
    if not content:
        return {}
    text = content[0].get("text", "") if isinstance(content[0], dict) else ""
    if not text:
        return {}
    try:
        parsed = json.loads(text)
        return parsed if isinstance(parsed, dict) else {}
    except json.JSONDecodeError:
        return {}


def _first_doku_transaction(payload: dict[str, Any]) -> dict[str, Any]:
    message = payload.get("message")
    if isinstance(message, list) and message and isinstance(message[0], dict):
        return message[0]
    if isinstance(message, dict):
        return message
    return {}


def verify_run(
    event: AgentEvent,
    plan: AgentPlan,
    tool_results: list[ToolResult],
) -> VerificationResult:
    # Any required tool failure fails verification.
    for r in tool_results:
        if not r.ok:
            return VerificationResult(
                ok=False,
                reason=f"tool_failed:{r.tool}",
                evidence={"error": r.error or "unknown"},
            )

    if plan.event_classification == "duplicate_event":
        # Verify no risky tool was executed.
        risky = {"check_payment_status", "create_recovery_link", "create_approval_request"}
        used = {r.tool for r in tool_results}
        if risky & used:
            return VerificationResult(
                ok=False,
                reason="duplicate_executed_risky_tool",
                evidence={"used_tools": sorted(used)},
            )
        audit = _find(tool_results, "write_audit_log")
        if not audit or not audit.result.get("written"):
            return VerificationResult(
                ok=False,
                reason="duplicate_missing_audit",
                evidence={},
            )
        return VerificationResult(
            ok=True,
            reason="duplicate_acknowledged",
            evidence={"audit": audit.result.get("entry", {})},
        )

    if plan.requires_human:
        approval = _find(tool_results, "create_approval_request")
        if not approval or approval.result.get("status") != "pending":
            return VerificationResult(
                ok=False,
                reason="approval_request_missing",
                evidence={},
            )
        return VerificationResult(
            ok=True,
            reason="approval_recorded",
            evidence={"approval": approval.result},
        )

    if plan.event_classification == "payment_failed":
        link = _find(tool_results, "create_recovery_link")
        if not link or not link.result.get("url"):
            return VerificationResult(
                ok=False,
                reason="recovery_link_missing",
                evidence={},
            )
        msg = _find(tool_results, "draft_customer_message")
        if not msg or not msg.result.get("message"):
            return VerificationResult(
                ok=False,
                reason="customer_message_missing",
                evidence={},
            )
        return VerificationResult(
            ok=True,
            reason="recovery_verified",
            evidence={
                "recovery_url": link.result.get("url"),
                "message_drafted": True,
            },
        )

    if plan.event_classification == "transaction_lookup_requested":
        transaction = _find(tool_results, "get_transaction_by_invoice_number")
        doku_transaction = _find(tool_results, "call_doku_mcp_tool")
        audit = _find(tool_results, "write_audit_log")
        if doku_transaction:
            payload = _doku_content_payload(doku_transaction.result)
            record = _first_doku_transaction(payload)
            invoice_number = record.get("invoice_number") or record.get("invoiceNumber") or event.metadata.get("invoice_number")
            transaction_status = record.get("status") or (payload.get("summary") or [{}])[0].get("status") if isinstance(payload.get("summary"), list) and payload.get("summary") else record.get("status")
            if not invoice_number:
                return VerificationResult(
                    ok=False,
                    reason="doku_transaction_lookup_missing",
                    evidence={"doku_result": doku_transaction.result},
                )
            if not audit or not audit.result.get("written"):
                return VerificationResult(
                    ok=False,
                    reason="audit_missing",
                    evidence={"doku_transaction": record},
                )
            return VerificationResult(
                ok=True,
                reason="doku_transaction_lookup_verified",
                evidence={
                    "invoice_number": invoice_number,
                    "transaction_status": transaction_status,
                    "order_status": record.get("order_status"),
                    "amount": record.get("amount"),
                },
            )
        if not transaction or not transaction.result.get("invoice_number"):
            return VerificationResult(
                ok=False,
                reason="transaction_lookup_missing",
                evidence={},
            )
        if not audit or not audit.result.get("written"):
            return VerificationResult(
                ok=False,
                reason="audit_missing",
                evidence={"transaction": transaction.result},
            )
        return VerificationResult(
            ok=True,
            reason="transaction_lookup_verified",
            evidence={
                "invoice_number": transaction.result.get("invoice_number"),
                "transaction_status": transaction.result.get("transaction_status"),
                "payment_method": transaction.result.get("payment_method"),
            },
        )

    if plan.event_classification == "doku_payment_methods_requested":
        doku_result = _find(tool_results, "call_doku_mcp_tool")
        if not doku_result or not doku_result.result or "error" in doku_result.result:
            return VerificationResult(
                ok=False,
                reason="doku_payment_methods_missing",
                evidence={"doku_result": doku_result.result if doku_result else None},
            )
        audit = _find(tool_results, "write_audit_log")
        if not audit or not audit.result.get("written"):
            return VerificationResult(
                ok=False,
                reason="audit_missing",
                evidence={"doku_result": doku_result.result},
            )
        return VerificationResult(
            ok=True,
            reason="doku_payment_methods_verified",
            evidence={"tool": "get_merchant_payment_methods"},
        )

    if plan.event_classification in ("payment_succeeded", "payment_recovered"):
        audit = _find(tool_results, "write_audit_log")
        if not audit or not audit.result.get("written"):
            return VerificationResult(
                ok=False,
                reason="audit_missing",
                evidence={},
            )
        return VerificationResult(
            ok=True,
            reason="record_verified",
            evidence={"audit": audit.result.get("entry", {})},
        )

    # Fallback: require an audit entry.
    audit = _find(tool_results, "write_audit_log")
    if not audit or not audit.result.get("written"):
        return VerificationResult(ok=False, reason="audit_missing", evidence={})
    return VerificationResult(ok=True, reason="default_verified", evidence={})
