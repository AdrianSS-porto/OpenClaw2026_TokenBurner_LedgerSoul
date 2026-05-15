"""Allowlisted judge workflows for the public demo surface."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Literal
from uuid import uuid4

JudgeRisk = Literal["read_only", "sandbox_write"]


@dataclass(frozen=True)
class JudgeWorkflow:
    id: str
    label: str
    description: str
    risk: JudgeRisk
    allowed_inputs: tuple[str, ...]
    expected_tools: tuple[str, ...]
    requires_confirmation: bool = False

    def to_public_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["allowed_inputs"] = list(self.allowed_inputs)
        data["expected_tools"] = list(self.expected_tools)
        return data


JUDGE_WORKFLOWS: dict[str, JudgeWorkflow] = {
    "transaction_lookup": JudgeWorkflow(
        id="transaction_lookup",
        label="Transaction lookup by invoice number",
        description="Reconcile a known invoice and show LedgerSoul's lifecycle trace.",
        risk="read_only",
        allowed_inputs=("invoice_number",),
        expected_tools=("get_transaction_by_invoice_number", "write_audit_log"),
    ),
    "doku_payment_methods": JudgeWorkflow(
        id="doku_payment_methods",
        label="DOKU payment methods",
        description="Call the DOKU MCP sandbox read-only payment-methods tool.",
        risk="read_only",
        allowed_inputs=(),
        expected_tools=("call_doku_mcp_tool", "write_audit_log"),
    ),
}


def validate_workflow_inputs(workflow_id: str, inputs: dict[str, Any]) -> dict[str, Any]:
    """Return only inputs allowed by the workflow registry."""
    workflow = JUDGE_WORKFLOWS.get(workflow_id)
    if workflow is None:
        raise ValueError(f"Unknown judge workflow: {workflow_id}")
    return {key: inputs[key] for key in workflow.allowed_inputs if key in inputs}


def build_event_for_workflow(workflow_id: str, inputs: dict[str, Any]) -> dict[str, Any]:
    """Convert a judge workflow request into a deterministic LedgerSoul event."""
    safe_inputs = validate_workflow_inputs(workflow_id, inputs)
    event_id = f"judge_{workflow_id}_{uuid4().hex[:12]}"

    if workflow_id == "transaction_lookup":
        invoice_number = str(safe_inputs.get("invoice_number") or "INV-LEDGERSOUL-001")
        return {
            "event_id": event_id,
            "type": "transaction.lookup_requested",
            "amount": 20000,
            "currency": "IDR",
            "metadata": {
                "invoice_number": invoice_number,
                "source": "judge_mode",
                "lookup_reason": "judge_requested_reconciliation",
            },
        }

    if workflow_id == "doku_payment_methods":
        return {
            "event_id": event_id,
            "type": "doku.payment_methods_requested",
            "metadata": {
                "source": "judge_mode",
                "doku_tool": "get_merchant_payment_methods",
            },
        }

    raise ValueError(f"Unsupported judge workflow: {workflow_id}")
