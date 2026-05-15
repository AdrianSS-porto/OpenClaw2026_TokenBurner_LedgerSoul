"""Tests for the LLM Reasoning Agent (multi-agent first stage)."""

from __future__ import annotations

from unittest.mock import patch

from ledgersoul.agent.models import AgentEvent
from ledgersoul.agent.reasoner import ReasoningOutput, reason_about


def _event(event_type: str, **kwargs) -> AgentEvent:
    return AgentEvent.model_validate({
        "event_id": "evt_test_reason",
        "type": event_type,
        **kwargs,
    })


def test_reasoner_falls_back_when_llm_not_configured(monkeypatch):
    monkeypatch.delenv("LLM_API_BASE", raising=False)
    monkeypatch.delenv("LLM_API_KEY", raising=False)

    out = reason_about(_event("payment.failed", amount=20000, currency="IDR"))

    assert isinstance(out, ReasoningOutput)
    assert out.classification == "payment_failed"
    assert out.mode == "disabled"
    assert out.fallback_reason == "llm_not_configured"
    assert "write_audit_log" in out.suggested_tools
    assert out.confidence > 0.5


def test_reasoner_fallback_for_unknown_event(monkeypatch):
    monkeypatch.delenv("LLM_API_BASE", raising=False)
    monkeypatch.delenv("LLM_API_KEY", raising=False)

    out = reason_about(_event("nonexistent.weird"))

    assert out.classification == "unknown"
    assert out.confidence < 0.5
    assert "create_approval_request" in out.suggested_tools
    assert out.suggested_tools[-1] == "write_audit_log"


def test_reasoner_handles_llm_transport_error(monkeypatch):
    monkeypatch.setenv("LLM_API_BASE", "http://127.0.0.1:1")  # unreachable
    monkeypatch.setenv("LLM_API_KEY", "fake")
    monkeypatch.setenv("LLM_TIMEOUT_S", "0.5")

    out = reason_about(_event("transaction.lookup_requested",
                              metadata={"invoice_number": "INV-1"}))

    # Falls back deterministically when transport fails
    assert out.classification == "transaction_lookup_requested"
    assert out.mode == "fallback"
    assert out.fallback_reason and out.fallback_reason.startswith("llm_transport_error")
    assert "get_transaction_by_invoice_number" in out.suggested_tools


def test_reasoner_parses_llm_response(monkeypatch):
    monkeypatch.setenv("LLM_API_BASE", "https://example.invalid/v1")
    monkeypatch.setenv("LLM_API_KEY", "fake")
    monkeypatch.setenv("LLM_MODEL", "test-model")

    fake_payload = {
        "choices": [
            {"message": {"content": (
                '{"classification": "payment_failed", "confidence": 0.92, '
                '"intent": "Recover failed payment", '
                '"suggested_tools": ["create_recovery_link", "write_audit_log"], '
                '"rationale": "Event type indicates a failed payment."}'
            )}}
        ]
    }

    class _FakeResponse:
        status_code = 200

        def json(self):
            return fake_payload

    class _FakeClient:
        def __init__(self, *a, **kw):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def post(self, url, json, headers):  # noqa: A002
            return _FakeResponse()

    with patch("ledgersoul.agent.reasoner.httpx.Client", _FakeClient):
        out = reason_about(_event("payment.failed", amount=20000, currency="IDR"))

    assert out.mode == "llm"
    assert out.classification == "payment_failed"
    assert out.confidence == 0.92
    assert out.suggested_tools == ["create_recovery_link", "write_audit_log"]
    assert out.model == "test-model"
    assert out.latency_ms is not None and out.latency_ms >= 0


def test_reasoner_rejects_invalid_classification(monkeypatch):
    monkeypatch.setenv("LLM_API_BASE", "https://example.invalid/v1")
    monkeypatch.setenv("LLM_API_KEY", "fake")

    fake_payload = {
        "choices": [
            {"message": {"content": '{"classification": "definitely_not_real", "confidence": 0.99}'}}
        ]
    }

    class _FakeResponse:
        status_code = 200

        def json(self):
            return fake_payload

    class _FakeClient:
        def __init__(self, *a, **kw):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def post(self, url, json, headers):  # noqa: A002
            return _FakeResponse()

    with patch("ledgersoul.agent.reasoner.httpx.Client", _FakeClient):
        out = reason_about(_event("payment.failed", amount=1, currency="IDR"))

    # Falls back deterministically when the LLM returns an out-of-allowlist class
    assert out.mode == "fallback"
    assert out.fallback_reason and "llm_invalid_classification" in out.fallback_reason
    assert out.classification == "payment_failed"
