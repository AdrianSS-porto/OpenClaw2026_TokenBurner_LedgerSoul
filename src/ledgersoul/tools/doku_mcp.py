"""DOKU MCP Server helpers.

The DOKU MCP Server is exposed over Streamable HTTP JSON-RPC and requires:
- Client-Id header with the DOKU client/brand ID
- Authorization header with `Basic <base64(api_key + ":")>`
"""

from __future__ import annotations

import base64
from typing import Any

import httpx

from ledgersoul.agent.config import AgentConfig

DOKU_SANDBOX_MCP_URL = "https://api-sandbox.doku.com/doku-mcp-server/mcp"
DOKU_PRODUCTION_MCP_URL = "https://mcp.doku.com/mcp"


def build_basic_authorization(api_key: str | None) -> str | None:
    """Build DOKU's required Basic auth header from a raw API key.

    DOKU's docs require base64 encoding the string `<api_key>:` including the trailing colon.
    """
    if not api_key:
        return None
    encoded = base64.b64encode(f"{api_key}:".encode("utf-8")).decode("ascii")
    return f"Basic {encoded}"


def doku_mcp_headers(config: AgentConfig) -> dict[str, str]:
    """Return HTTP headers for DOKU MCP without leaking secrets in logs."""
    authorization = config.doku_authorization or build_basic_authorization(config.doku_api_key)
    headers = {
        "Client-Id": config.doku_client_id or "",
        "Authorization": authorization or "",
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
    }
    return headers


def doku_mcp_config_status(config: AgentConfig) -> dict[str, Any]:
    """Describe whether DOKU MCP is configured. Does not perform a network call."""
    has_authorization = bool(config.doku_authorization or config.doku_api_key)
    missing = []
    if not config.doku_mcp_url:
        missing.append("DOKU_MCP_URL")
    if not config.doku_client_id:
        missing.append("DOKU_CLIENT_ID")
    if not has_authorization:
        missing.append("DOKU_AUTHORIZATION or DOKU_API_KEY")

    return {
        "provider": config.payment_provider,
        "payment_api_mode": config.payment_api_mode,
        "mcp_url": config.doku_mcp_url,
        "configured": not missing,
        "missing": missing,
        "headers": {
            "Client-Id": "set" if config.doku_client_id else "missing",
            "Authorization": "set" if has_authorization else "missing",
        },
    }


def call_doku_mcp_rpc(
    config: AgentConfig,
    method: str,
    params: dict[str, Any] | None = None,
    request_id: int = 1,
    protocol_version: str | None = None,
) -> dict[str, Any]:
    """Call DOKU MCP JSON-RPC over HTTP.

    This is intentionally explicit and small. Runtime flows do not call it unless a plan/tool opts in.
    """
    status = doku_mcp_config_status(config)
    if not status["configured"]:
        raise ValueError(f"DOKU MCP is not configured; missing: {', '.join(status['missing'])}")

    headers = doku_mcp_headers(config)
    if protocol_version:
        headers["mcp-protocol-version"] = protocol_version

    payload = {
        "jsonrpc": "2.0",
        "id": request_id,
        "method": method,
        "params": params or {},
    }
    response = httpx.post(config.doku_mcp_url, headers=headers, json=payload, timeout=30.0)
    response.raise_for_status()
    return response.json()


def list_doku_mcp_tools(config: AgentConfig) -> dict[str, Any]:
    """Initialize a DOKU MCP session and return available tools."""
    init = call_doku_mcp_rpc(config, "initialize", {}, request_id=0)
    protocol_version = init.get("result", {}).get("protocolVersion")
    tools = call_doku_mcp_rpc(
        config,
        "tools/list",
        {},
        request_id=1,
        protocol_version=protocol_version,
    )
    return {
        "server": init.get("result", {}).get("serverInfo", {}),
        "protocolVersion": protocol_version,
        "tools": tools.get("result", {}).get("tools", []),
    }


def call_doku_mcp_tool(config: AgentConfig, tool_name: str, tool_request: str) -> dict[str, Any]:
    """Call one DOKU MCP tool explicitly.

    DOKU examples wrap arguments as {"toolRequest": "..."}; keep that convention here.
    """
    init = call_doku_mcp_rpc(config, "initialize", {}, request_id=0)
    protocol_version = init.get("result", {}).get("protocolVersion")
    return call_doku_mcp_rpc(
        config,
        "tools/call",
        {"name": tool_name, "arguments": {"toolRequest": tool_request}},
        request_id=2,
        protocol_version=protocol_version,
    )
