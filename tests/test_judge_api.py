"""Judge API endpoint tests."""

from __future__ import annotations

from fastapi.testclient import TestClient

from ledgersoul.server.api import create_app

AUTH = {"Authorization": "Bearer judge-token"}


def test_judge_workflows_requires_token(judge_config) -> None:
    client = TestClient(create_app(judge_config))

    assert client.get("/judge/workflows").status_code == 401
    assert client.get("/judge/workflows", headers=AUTH).status_code == 200


def test_judge_run_transaction_lookup(judge_config) -> None:
    client = TestClient(create_app(judge_config))

    response = client.post(
        "/judge/runs",
        headers=AUTH,
        json={"workflow": "transaction_lookup", "inputs": {"invoice_number": "INV-LEDGERSOUL-001"}},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "completed"
    assert body["classification"] == "transaction_lookup_requested"
    assert body["tools_used"] == ["get_transaction_by_invoice_number", "write_audit_log"]
    assert body["verification"]["ok"] is True
    assert body["trace_name"].endswith(".json")


def test_judge_rejects_unknown_workflow(judge_config) -> None:
    client = TestClient(create_app(judge_config))

    response = client.post(
        "/judge/runs",
        headers=AUTH,
        json={"workflow": "call_any_tool", "inputs": {"tool_name": "anything"}},
    )

    assert response.status_code == 400


def test_judge_trace_endpoint_returns_redacted_trace(judge_config) -> None:
    client = TestClient(create_app(judge_config))
    run = client.post(
        "/judge/runs",
        headers=AUTH,
        json={"workflow": "transaction_lookup", "inputs": {"invoice_number": "INV-LEDGERSOUL-001"}},
    ).json()

    trace = client.get(f"/judge/runs/{run['trace_name']}/trace", headers=AUTH)

    assert trace.status_code == 200
    body = trace.json()
    assert body["status"] == "completed"
    assert "redacted_trace" in body
    assert "SHOULD_NOT_LEAK" not in trace.text
