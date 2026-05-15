"""Tests for DOKU MCP configuration and helpers."""

from __future__ import annotations

from ledgersoul.agent.config import AgentConfig
from ledgersoul.tools.doku_mcp import (
    build_basic_authorization,
    doku_mcp_config_status,
    doku_mcp_headers,
)


def test_build_basic_authorization_includes_required_trailing_colon() -> None:
    assert build_basic_authorization("api_key_test") == "Basic YXBpX2tleV90ZXN0Og=="


def test_doku_mcp_status_reports_missing_client_id(config: AgentConfig) -> None:
    cfg = AgentConfig(**{**config.__dict__, "payment_provider": "doku", "doku_api_key": "key"})
    status = doku_mcp_config_status(cfg)
    assert status["configured"] is False
    assert "DOKU_CLIENT_ID" in status["missing"]
    assert status["headers"]["Authorization"] == "set"


def test_doku_mcp_headers_prefer_explicit_authorization(config: AgentConfig) -> None:
    cfg = AgentConfig(
        **{
            **config.__dict__,
            "doku_client_id": "BRN-test",
            "doku_api_key": "raw-key",
            "doku_authorization": "Basic explicit",
        }
    )
    headers = doku_mcp_headers(cfg)
    assert headers["Client-Id"] == "BRN-test"
    assert headers["Authorization"] == "Basic explicit"
    assert headers["Accept"] == "application/json, text/event-stream"
