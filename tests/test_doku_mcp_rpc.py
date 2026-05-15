"""Tests for DOKU MCP RPC flows without hitting the network."""

from __future__ import annotations

from typing import Any

import pytest

from ledgersoul.agent.config import AgentConfig
from ledgersoul.tools import doku_mcp


class FakeResponse:
    def __init__(self, payload: dict[str, Any], status_error: Exception | None = None) -> None:
        self.payload = payload
        self.status_error = status_error

    def raise_for_status(self) -> None:
        if self.status_error:
            raise self.status_error

    def json(self) -> dict[str, Any]:
        return self.payload


def configured_doku_config(config: AgentConfig) -> AgentConfig:
    return AgentConfig(
        **{
            **config.__dict__,
            "payment_provider": "doku",
            "payment_api_mode": "sandbox",
            "doku_client_id": "BRN-test",
            "doku_api_key": "secret-test",
            "doku_authorization": "",
        }
    )


def test_call_doku_mcp_rpc_sends_json_rpc_payload_and_headers(
    config: AgentConfig,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cfg = configured_doku_config(config)
    captured: dict[str, Any] = {}

    def fake_post(url: str, headers: dict[str, str], json: dict[str, Any], timeout: float) -> FakeResponse:
        captured.update({"url": url, "headers": headers, "json": json, "timeout": timeout})
        return FakeResponse({"jsonrpc": "2.0", "id": 7, "result": {"ok": True}})

    monkeypatch.setattr(doku_mcp.httpx, "post", fake_post)

    result = doku_mcp.call_doku_mcp_rpc(cfg, "tools/list", {}, request_id=7)

    assert result["result"] == {"ok": True}
    assert captured["url"] == "https://api-sandbox.doku.com/doku-mcp-server/mcp"
    assert captured["headers"]["Client-Id"] == "BRN-test"
    assert captured["headers"]["Authorization"] == "Basic c2VjcmV0LXRlc3Q6"
    assert captured["headers"]["Accept"] == "application/json, text/event-stream"
    assert captured["json"] == {"jsonrpc": "2.0", "id": 7, "method": "tools/list", "params": {}}
    assert captured["timeout"] == 30.0


def test_call_doku_mcp_rpc_adds_protocol_version_header(
    config: AgentConfig,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cfg = configured_doku_config(config)
    captured: dict[str, Any] = {}

    def fake_post(url: str, headers: dict[str, str], json: dict[str, Any], timeout: float) -> FakeResponse:
        captured.update({"headers": headers})
        return FakeResponse({"jsonrpc": "2.0", "id": 1, "result": {}})

    monkeypatch.setattr(doku_mcp.httpx, "post", fake_post)

    doku_mcp.call_doku_mcp_rpc(cfg, "tools/list", protocol_version="2025-06-18")

    assert captured["headers"]["mcp-protocol-version"] == "2025-06-18"


def test_call_doku_mcp_rpc_rejects_missing_configuration(config: AgentConfig) -> None:
    with pytest.raises(ValueError, match="DOKU MCP is not configured"):
        doku_mcp.call_doku_mcp_rpc(config, "tools/list")


def test_list_doku_mcp_tools_initializes_then_lists_tools(
    config: AgentConfig,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cfg = configured_doku_config(config)
    calls: list[dict[str, Any]] = []

    def fake_call(
        config: AgentConfig,
        method: str,
        params: dict[str, Any] | None = None,
        request_id: int = 1,
        protocol_version: str | None = None,
    ) -> dict[str, Any]:
        calls.append({"method": method, "request_id": request_id, "protocol_version": protocol_version})
        if method == "initialize":
            return {
                "result": {
                    "protocolVersion": "2025-06-18",
                    "serverInfo": {"name": "webmvc-doku-mcp-server", "version": "1.0.0"},
                }
            }
        return {"result": {"tools": [{"name": "create_qris_payment"}]}}

    monkeypatch.setattr(doku_mcp, "call_doku_mcp_rpc", fake_call)

    result = doku_mcp.list_doku_mcp_tools(cfg)

    assert result["server"]["name"] == "webmvc-doku-mcp-server"
    assert result["protocolVersion"] == "2025-06-18"
    assert result["tools"] == [{"name": "create_qris_payment"}]
    assert calls == [
        {"method": "initialize", "request_id": 0, "protocol_version": None},
        {"method": "tools/list", "request_id": 1, "protocol_version": "2025-06-18"},
    ]


def test_call_doku_mcp_tool_wraps_tool_request_argument(
    config: AgentConfig,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cfg = configured_doku_config(config)
    calls: list[dict[str, Any]] = []

    def fake_call(
        config: AgentConfig,
        method: str,
        params: dict[str, Any] | None = None,
        request_id: int = 1,
        protocol_version: str | None = None,
    ) -> dict[str, Any]:
        calls.append({
            "method": method,
            "params": params,
            "request_id": request_id,
            "protocol_version": protocol_version,
        })
        if method == "initialize":
            return {"result": {"protocolVersion": "2025-06-18"}}
        return {"result": {"content": [{"type": "text", "text": "ok"}]}}

    monkeypatch.setattr(doku_mcp, "call_doku_mcp_rpc", fake_call)

    result = doku_mcp.call_doku_mcp_tool(
        cfg,
        "create_doku_customer_form_payment_link",
        "create a sandbox payment link for invoice INV-001 amount 20000 IDR",
    )

    assert result["result"]["content"][0]["text"] == "ok"
    assert calls[1] == {
        "method": "tools/call",
        "params": {
            "name": "create_doku_customer_form_payment_link",
            "arguments": {
                "toolRequest": "create a sandbox payment link for invoice INV-001 amount 20000 IDR"
            },
        },
        "request_id": 2,
        "protocol_version": "2025-06-18",
    }
