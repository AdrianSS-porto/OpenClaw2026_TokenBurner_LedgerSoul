"""DOKU webhook endpoint tests."""

from __future__ import annotations

from fastapi.testclient import TestClient

from ledgersoul.server.api import create_app


def test_doku_webhook_runs_agent_transaction_check(config, monkeypatch) -> None:
    captured_events: list[dict] = []

    def fake_call_doku_mcp_tool(**kwargs):
        assert kwargs["tool_name"] == "get_transaction_by_invoice_number"
        assert kwargs["tool_request"]["invoiceNumber"] == "LS-CHECKOUT-123"
        return {
            "result": {
                "content": [
                    {
                        "type": "text",
                        "text": (
                            '{"summary":[{"tpt":1,"tpv":25000.0,"status":"PENDING"}],'
                            '"message":[{"invoice_number":"LS-CHECKOUT-123",'
                            '"amount":25000.0,"status":"PENDING",'
                            '"order_status":"ORDER_GENERATED",'
                            '"customer_name":"LedgerSoul Sandbox Buyer"}]}'
                        ),
                    }
                ]
            },
            "isError": False,
        }

    def spying_run(self, event_data):  # noqa: ANN001
        captured_events.append(event_data)
        return original_run(self, event_data)

    monkeypatch.setattr("ledgersoul.agent.executor.get_tool", lambda name: fake_call_doku_mcp_tool if name == "call_doku_mcp_tool" else original_get_tool(name))
    from ledgersoul.agent.runtime import AgentRuntime
    from ledgersoul.agent.tool_registry import get_tool as original_get_tool

    original_run = AgentRuntime.run
    monkeypatch.setattr(AgentRuntime, "run", spying_run)

    client = TestClient(create_app(config))
    response = client.post(
        "/webhooks/doku",
        json={
            "order": {"invoice_number": "LS-CHECKOUT-123", "amount": "25000", "currency": "IDR"},
            "transaction": {"status": "PENDING"},
            "customer": {"name": "LedgerSoul Sandbox Buyer"},
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "completed"
    assert body["verification"]["ok"] is True
    assert body["verification"]["reason"] == "doku_transaction_lookup_verified"
    assert body["verification"]["evidence"]["invoice_number"] == "LS-CHECKOUT-123"
    assert body["verification"]["evidence"]["transaction_status"] == "PENDING"

    assert captured_events[0]["type"] == "transaction.lookup_requested"
    assert captured_events[0]["metadata"]["source"] == "doku_webhook"
    assert captured_events[0]["metadata"]["provider"] == "doku"
    assert captured_events[0]["metadata"]["invoice_number"] == "LS-CHECKOUT-123"


def test_doku_webhook_rejects_payload_without_invoice(config) -> None:
    client = TestClient(create_app(config))

    response = client.post("/webhooks/doku", json={"transaction": {"status": "PENDING"}})

    assert response.status_code == 400
    assert response.json()["detail"] == "DOKU webhook payload missing invoice number"
