"""LLM Reasoning Agent — first stage of the multi-agent pipeline.

The Reasoning Agent ingests a raw payment event and produces a structured
reasoning output: a classification, a confidence score, a free-form intent
summary, and a list of suggested tools. The deterministic Planner Agent
remains the source of truth — the reasoner's output is recorded in the
trace and used to enrich planning, but it can never bypass policy or
verification.

This module is intentionally robust:
  - When ``LLM_API_BASE`` and ``LLM_API_KEY`` are configured, it makes an
    OpenAI-compatible /chat/completions call (via httpx) and parses a JSON
    response.
  - When the LLM is unavailable, misconfigured, slow, or returns invalid
    JSON, it falls back to a deterministic reasoning path that mirrors the
    planner's classification map.
  - It never raises — failures degrade to ``mode="fallback"`` with a clear
    fallback reason recorded in the trace.

This design keeps the multi-agent claim honest:
  Reasoning Agent (LLM)  ──►  Planner Agent (rules + policy)
                              ──►  Executor Agent (TOOL_REGISTRY)
                                   ──►  Verifier Agent (deterministic)
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any, Literal

import httpx

from ledgersoul.agent.config import AgentConfig
from ledgersoul.agent.models import AgentEvent
from ledgersoul.agent.planner import CLASSIFICATIONS

ReasoningMode = Literal["llm", "fallback", "disabled"]


# ---- Output model --------------------------------------------------------

@dataclass
class ReasoningOutput:
    """Structured reasoning result produced by the Reasoning Agent."""

    classification: str
    confidence: float
    intent: str
    suggested_tools: list[str] = field(default_factory=list)
    rationale: str = ""
    mode: ReasoningMode = "fallback"
    fallback_reason: str | None = None
    model: str | None = None
    latency_ms: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "classification": self.classification,
            "confidence": self.confidence,
            "intent": self.intent,
            "suggested_tools": list(self.suggested_tools),
            "rationale": self.rationale,
            "mode": self.mode,
            "fallback_reason": self.fallback_reason,
            "model": self.model,
            "latency_ms": self.latency_ms,
        }


# ---- Deterministic fallback ---------------------------------------------

_FALLBACK_INTENTS: dict[str, tuple[str, list[str]]] = {
    "payment_failed": (
        "Recover the failed payment automatically and notify the customer.",
        ["check_payment_status", "create_recovery_link", "draft_customer_message", "write_audit_log"],
    ),
    "payment_succeeded": (
        "Record the successful payment for downstream reconciliation.",
        ["write_audit_log"],
    ),
    "payment_recovered": (
        "Record the recovered payment for downstream reconciliation.",
        ["write_audit_log"],
    ),
    "refund_requested": (
        "Refund requires human approval — file a ticket and wait.",
        ["create_approval_request", "write_audit_log"],
    ),
    "suspicious_payment": (
        "Risk is high — escalate the suspicious payment for review.",
        ["create_approval_request", "write_audit_log"],
    ),
    "api_failure": (
        "Provider API failed — verify state and escalate if uncertain.",
        ["check_payment_status", "create_approval_request", "write_audit_log"],
    ),
    "transaction_lookup_requested": (
        "Reconcile the transaction by invoice number.",
        ["get_transaction_by_invoice_number", "write_audit_log"],
    ),
    "doku_payment_methods_requested": (
        "List DOKU sandbox payment methods through the allowlisted MCP tool.",
        ["call_doku_mcp_tool", "write_audit_log"],
    ),
}


def _deterministic_reason(event: AgentEvent, *, mode: ReasoningMode = "fallback",
                          fallback_reason: str | None = None,
                          model: str | None = None,
                          latency_ms: int | None = None) -> ReasoningOutput:
    classification = CLASSIFICATIONS.get(event.type, "unknown")
    intent, tools = _FALLBACK_INTENTS.get(
        classification,
        (
            "Unknown event type — escalate for human review.",
            ["create_approval_request", "write_audit_log"],
        ),
    )
    confidence = 0.95 if classification != "unknown" else 0.20
    return ReasoningOutput(
        classification=classification,
        confidence=confidence,
        intent=intent,
        suggested_tools=tools,
        rationale=f"Deterministic classification of event type {event.type!r}.",
        mode=mode,
        fallback_reason=fallback_reason,
        model=model,
        latency_ms=latency_ms,
    )


# ---- LLM client ----------------------------------------------------------

_SYSTEM_PROMPT = """You are LedgerSoul's Reasoning Agent. Your job is to read a single payment event from a DOKU merchant and decide what kind of operational situation it is, with a confidence score and a brief intent summary.

You MUST respond with a single JSON object and nothing else. The JSON object must have these keys:

  classification:    one of [
                       "payment_failed", "payment_succeeded", "payment_recovered",
                       "refund_requested", "suspicious_payment", "api_failure",
                       "transaction_lookup_requested", "doku_payment_methods_requested",
                       "unknown"
                     ]
  confidence:        a float in [0.0, 1.0]
  intent:            a short natural-language sentence describing what the agent should achieve
  suggested_tools:   an ordered array of tool names from this allowlist:
                       ["check_payment_status", "create_recovery_link",
                        "draft_customer_message", "create_approval_request",
                        "get_transaction_by_invoice_number",
                        "list_doku_mcp_tools", "call_doku_mcp_tool",
                        "write_audit_log"]
                     Always end the array with "write_audit_log".
  rationale:         one sentence explaining why you chose that classification.

Refuse to invent tools that are not in the allowlist. Refuse to fabricate transaction data."""


def _llm_reason(event: AgentEvent, base_url: str, api_key: str, model: str,
                timeout_s: float) -> ReasoningOutput:
    import time

    user_payload = {
        "event_id": event.event_id,
        "type": event.type,
        "amount": event.amount,
        "currency": event.currency,
        "reason": event.reason,
        "metadata": event.metadata or {},
    }
    body = {
        "model": model,
        "temperature": 0,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user",
             "content": "Classify this payment event:\n" + json.dumps(user_payload)},
        ],
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    url = base_url.rstrip("/") + "/chat/completions"

    started = time.monotonic()
    try:
        with httpx.Client(timeout=timeout_s) as client:
            resp = client.post(url, json=body, headers=headers)
    except Exception as exc:
        return _deterministic_reason(
            event,
            fallback_reason=f"llm_transport_error:{type(exc).__name__}",
            model=model,
        )
    elapsed_ms = int((time.monotonic() - started) * 1000)

    if resp.status_code >= 400:
        return _deterministic_reason(
            event,
            fallback_reason=f"llm_http_{resp.status_code}",
            model=model,
            latency_ms=elapsed_ms,
        )

    try:
        data = resp.json()
        text = data["choices"][0]["message"]["content"]
        parsed = json.loads(text)
    except Exception as exc:
        return _deterministic_reason(
            event,
            fallback_reason=f"llm_parse_error:{type(exc).__name__}",
            model=model,
            latency_ms=elapsed_ms,
        )

    valid_classes = set(CLASSIFICATIONS.values()) | {"unknown"}
    classification = parsed.get("classification", "unknown")
    if classification not in valid_classes:
        return _deterministic_reason(
            event,
            fallback_reason=f"llm_invalid_classification:{classification!r}",
            model=model,
            latency_ms=elapsed_ms,
        )

    confidence = parsed.get("confidence", 0.5)
    try:
        confidence = float(confidence)
    except Exception:
        confidence = 0.5
    confidence = max(0.0, min(1.0, confidence))

    suggested = parsed.get("suggested_tools") or []
    if not isinstance(suggested, list):
        suggested = []
    # Restrict to the documented allowlist
    allowlist = {
        "check_payment_status", "create_recovery_link", "draft_customer_message",
        "create_approval_request", "get_transaction_by_invoice_number",
        "list_doku_mcp_tools", "call_doku_mcp_tool", "write_audit_log",
    }
    suggested = [t for t in suggested if isinstance(t, str) and t in allowlist]

    return ReasoningOutput(
        classification=classification,
        confidence=confidence,
        intent=str(parsed.get("intent", ""))[:240],
        suggested_tools=suggested,
        rationale=str(parsed.get("rationale", ""))[:240],
        mode="llm",
        model=model,
        latency_ms=elapsed_ms,
    )


# ---- Public entrypoint ---------------------------------------------------

def reason_about(event: AgentEvent, config: AgentConfig | None = None) -> ReasoningOutput:
    """Run the Reasoning Agent for a single event.

    Reads the LLM endpoint config from environment so it works without
    requiring config schema changes. Falls back deterministically if any
    part of the LLM path fails or is not configured.
    """
    base_url = os.getenv("LLM_API_BASE", "").strip()
    api_key = os.getenv("LLM_API_KEY", "").strip()
    model = os.getenv("LLM_MODEL", "gpt-4o-mini").strip()
    try:
        timeout_s = float(os.getenv("LLM_TIMEOUT_S", "8"))
    except ValueError:
        timeout_s = 8.0

    if not base_url or not api_key:
        return _deterministic_reason(
            event,
            mode="disabled",
            fallback_reason="llm_not_configured",
            model=model,
        )

    return _llm_reason(event, base_url=base_url, api_key=api_key,
                       model=model, timeout_s=timeout_s)
