"""Shared pytest fixtures: every test gets isolated tmp state/trace dirs."""

from __future__ import annotations

from pathlib import Path

import pytest

from ledgersoul.agent.config import AgentConfig
from ledgersoul.agent.runtime import AgentRuntime


@pytest.fixture()
def isolated_dirs(tmp_path: Path) -> tuple[Path, Path]:
    state = tmp_path / "state"
    traces = tmp_path / "traces"
    state.mkdir()
    traces.mkdir()
    return state, traces


@pytest.fixture()
def config(isolated_dirs: tuple[Path, Path]) -> AgentConfig:
    state, traces = isolated_dirs
    return AgentConfig(
        agent_mode="demo",
        port=8000,
        state_dir=str(state),
        trace_dir=str(traces),
        payment_provider="mock",
        payment_api_mode="mock",
        payment_api_key="",
        doku_api_key="",
        doku_client_id="",
        doku_authorization="",
        doku_mcp_url="https://api-sandbox.doku.com/doku-mcp-server/mcp",
        messaging_mode="mock",
        max_autonomous_amount=10000,
        require_human_approval=True,
        max_retries=2,
        judge_mode=False,
        judge_demo_token="",
        judge_allow_sandbox_writes=False,
        public_demo_base_url="",
    )


@pytest.fixture()
def judge_config(config: AgentConfig) -> AgentConfig:
    config.judge_mode = True
    config.judge_demo_token = "judge-token"
    config.judge_allow_sandbox_writes = False
    config.payment_provider = "doku"
    config.payment_api_mode = "sandbox"
    return config


@pytest.fixture()
def runtime(config: AgentConfig) -> AgentRuntime:
    return AgentRuntime(config)


@pytest.fixture()
def base_failed_event() -> dict:
    return {
        "event_id": "evt_payment_failed_test_1",
        "type": "payment.failed",
        "timestamp": "2026-05-15T10:00:00Z",
        "amount": 4900,
        "currency": "USD",
        "customer_id": "cus_test",
        "payment_id": "pay_test",
        "reason": "insufficient_funds",
    }
