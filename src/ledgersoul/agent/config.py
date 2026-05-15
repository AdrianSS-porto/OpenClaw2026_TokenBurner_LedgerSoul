"""Configuration loader for LedgerSoul."""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv


@dataclass
class AgentConfig:
    agent_mode: str
    port: int
    state_dir: str
    trace_dir: str
    payment_provider: str
    payment_api_mode: str
    payment_api_key: str
    doku_api_key: str
    doku_client_id: str
    doku_authorization: str
    doku_mcp_url: str
    messaging_mode: str
    max_autonomous_amount: int
    require_human_approval: bool
    max_retries: int
    judge_mode: bool
    judge_demo_token: str
    judge_allow_sandbox_writes: bool
    public_demo_base_url: str


def load_config() -> AgentConfig:
    load_dotenv()
    payment_api_key = os.getenv("PAYMENT_API_KEY", "")
    doku_api_key = os.getenv("DOKU_API_KEY", payment_api_key)
    return AgentConfig(
        agent_mode=os.getenv("AGENT_MODE", "demo"),
        port=int(os.getenv("PORT", "8000")),
        state_dir=os.getenv("STATE_DIR", "./state"),
        trace_dir=os.getenv("TRACE_DIR", "./traces"),
        payment_provider=os.getenv("PAYMENT_PROVIDER", "mock"),
        payment_api_mode=os.getenv("PAYMENT_API_MODE", "mock"),
        payment_api_key=payment_api_key,
        doku_api_key=doku_api_key,
        doku_client_id=os.getenv("DOKU_CLIENT_ID", ""),
        doku_authorization=os.getenv("DOKU_AUTHORIZATION", ""),
        doku_mcp_url=os.getenv(
            "DOKU_MCP_URL",
            "https://api-sandbox.doku.com/doku-mcp-server/mcp",
        ),
        messaging_mode=os.getenv("MESSAGING_MODE", "mock"),
        max_autonomous_amount=int(os.getenv("MAX_AUTONOMOUS_AMOUNT", "10000")),
        require_human_approval=os.getenv("REQUIRE_HUMAN_APPROVAL", "true").lower() == "true",
        max_retries=int(os.getenv("MAX_RETRIES", "2")),
        judge_mode=os.getenv("JUDGE_MODE", "false").lower() == "true",
        judge_demo_token=os.getenv("JUDGE_DEMO_TOKEN", ""),
        judge_allow_sandbox_writes=os.getenv("JUDGE_ALLOW_SANDBOX_WRITES", "false").lower() == "true",
        public_demo_base_url=os.getenv("PUBLIC_DEMO_BASE_URL", ""),
    )
