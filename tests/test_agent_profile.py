"""Tests proving LedgerSoul loads its markdown agent contract."""

from __future__ import annotations

import json

from fastapi.testclient import TestClient

from ledgersoul.agent.profile import REQUIRED_PROFILE_DOCS, load_agent_profile
from ledgersoul.agent.runtime import AgentRuntime
from ledgersoul.server.api import app


def test_load_agent_profile_reads_agent_md_and_required_docs() -> None:
    profile = load_agent_profile()

    assert profile["loaded"] is True
    assert set(profile["documents"]) == set(REQUIRED_PROFILE_DOCS)
    assert profile["documents"]["agent.md"]["exists"] is True
    assert "LedgerSoul is an autonomous payment-operations agent" in profile["documents"]["agent.md"]["content"]
    assert profile["documents"]["soul.md"]["exists"] is True
    assert profile["summary"]["mission"] == "autonomous payment-operations agent"


def test_agent_profile_endpoint_exposes_loaded_agent_contract() -> None:
    client = TestClient(app)

    response = client.get("/agent/profile")

    assert response.status_code == 200
    body = response.json()
    assert body["loaded"] is True
    assert body["documents"]["agent.md"]["exists"] is True
    assert "Runtime Loop" in body["documents"]["agent.md"]["content"]


def test_runtime_trace_includes_loaded_agent_profile_reference(runtime: AgentRuntime, base_failed_event: dict) -> None:
    result = runtime.run(base_failed_event)

    assert result.trace_path is not None
    with open(result.trace_path, "r", encoding="utf-8") as f:
        trace = json.load(f)

    assert trace["agent_profile"]["loaded"] is True
    assert trace["agent_profile"]["documents"]["agent.md"]["exists"] is True
    assert trace["agent_profile"]["documents"]["agent.md"]["sha256"]
    assert trace["agent_profile"]["summary"]["mission"] == "autonomous payment-operations agent"
