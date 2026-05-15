"""Judge mode route exposure tests."""

from __future__ import annotations

from fastapi.testclient import TestClient

from ledgersoul.server.api import create_app


def test_judge_mode_blocks_operational_endpoints(judge_config) -> None:
    client = TestClient(create_app(judge_config))

    assert client.post("/agent/run", json={}).status_code == 404
    assert client.get("/state").status_code == 404
    assert client.get("/traces").status_code == 404
    assert client.get("/doku/mcp/tools?live=true").status_code == 404
    assert client.get("/docs").status_code == 404
    assert client.get("/redoc").status_code == 404
    assert client.get("/openapi.json").status_code == 404


def test_judge_mode_keeps_judge_and_health_routes(judge_config) -> None:
    client = TestClient(create_app(judge_config))

    assert client.get("/health").status_code == 200
    assert client.get("/judge").status_code == 200


def test_non_judge_mode_keeps_agent_run_available(config) -> None:
    client = TestClient(create_app(config))

    assert client.post("/agent/run", json={}).status_code != 404
