"""Tool execution. All tools are resolved through TOOL_REGISTRY."""

from __future__ import annotations

from typing import Any

from ledgersoul.agent.config import AgentConfig
from ledgersoul.agent.memory import AgentMemory
from ledgersoul.agent.models import AgentEvent, AgentPlan, ToolResult
from ledgersoul.agent.tool_registry import get_tool


def _safe_call(registered_tool: str, **kwargs: Any) -> ToolResult:
    fn = get_tool(registered_tool)
    try:
        result = fn(**kwargs)
        return ToolResult(tool=registered_tool, ok=True, result=result)
    except Exception as exc:  # pragma: no cover - defensive
        return ToolResult(
            tool=registered_tool,
            ok=False,
            result={},
            error=f"{type(exc).__name__}: {exc}",
        )


def execute_plan(
    event: AgentEvent,
    plan: AgentPlan,
    config: AgentConfig,
    memory: AgentMemory,
) -> list[ToolResult]:
    """Execute plan steps via the registry. Returns the ordered list of ToolResults."""
    results: list[ToolResult] = []

    # Duplicate plans: write a single audit entry and stop.
    if plan.event_classification == "duplicate_event":
        results.append(
            _safe_call(
                "write_audit_log",
                memory=memory,
                event=event,
                action="duplicate_event_acknowledged",
                result={"event_id": event.event_id},
            )
        )
        return results

    # Escalation flow: approval + audit only.
    if plan.requires_human:
        approval = _safe_call(
            "create_approval_request",
            event=event,
            reason=f"{plan.event_classification}:{plan.risk_level}",
        )
        results.append(approval)
        if approval.ok:
            memory.append_pending_approval(approval.result)
        results.append(
            _safe_call(
                "write_audit_log",
                memory=memory,
                event=event,
                action="approval_requested",
                result=approval.result,
            )
        )
        return results

    # Recovery flow for failed payments.
    if plan.event_classification == "payment_failed":
        status = _safe_call("check_payment_status", payment_id=event.payment_id)
        results.append(status)

        link = _safe_call(
            "create_recovery_link",
            payment_id=event.payment_id,
            customer_id=event.customer_id,
            amount=event.amount,
        )
        results.append(link)

        recovery_url = link.result.get("url") if link.ok else None
        msg = _safe_call(
            "draft_customer_message",
            event=event,
            recovery_link=recovery_url,
        )
        results.append(msg)

        results.append(
            _safe_call(
                "write_audit_log",
                memory=memory,
                event=event,
                action="recovery_link_created",
                result={
                    "payment_status": status.result,
                    "recovery_link": link.result,
                    "message_draft": msg.result,
                },
            )
        )
        return results

    # Transaction reconciliation flow.
    if plan.event_classification == "transaction_lookup_requested":
        invoice_number = event.metadata.get("invoice_number")
        if event.metadata.get("provider") == "doku" or event.metadata.get("source") == "doku_webhook":
            transaction = _safe_call(
                "call_doku_mcp_tool",
                config=config,
                tool_name="get_transaction_by_invoice_number",
                tool_request={"invoiceNumber": invoice_number, "pageNumber": 1, "pageSize": 10},
            )
        else:
            transaction = _safe_call("get_transaction_by_invoice_number", invoice_number=invoice_number)
        results.append(transaction)
        results.append(
            _safe_call(
                "write_audit_log",
                memory=memory,
                event=event,
                action="transaction_lookup_completed",
                result={"transaction": transaction.result},
            )
        )
        return results

    # DOKU MCP read-only payment-methods workflow.
    if plan.event_classification == "doku_payment_methods_requested":
        doku = _safe_call(
            "call_doku_mcp_tool",
            config=config,
            tool_name="get_merchant_payment_methods",
            tool_request="List merchant payment methods available in DOKU sandbox.",
        )
        results.append(doku)
        results.append(
            _safe_call(
                "write_audit_log",
                memory=memory,
                event=event,
                action="doku_payment_methods_listed",
                result={"doku_payment_methods": doku.result},
            )
        )
        return results

    # Record-only flows (succeeded / recovered).
    if plan.event_classification in ("payment_succeeded", "payment_recovered"):
        results.append(
            _safe_call(
                "write_audit_log",
                memory=memory,
                event=event,
                action=f"{plan.event_classification}_recorded",
                result={"event_id": event.event_id, "amount": event.amount},
            )
        )
        return results

    # Fallback: should not happen because policy escalates unknown plans.
    results.append(
        _safe_call(
            "write_audit_log",
            memory=memory,
            event=event,
            action="noop_fallback",
            result={"event_classification": plan.event_classification},
        )
    )
    return results
