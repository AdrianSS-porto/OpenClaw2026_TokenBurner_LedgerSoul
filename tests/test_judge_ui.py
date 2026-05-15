"""Judge UI smoke tests."""

from __future__ import annotations

from fastapi.testclient import TestClient

from ledgersoul.server.api import create_app


def test_judge_page_contains_no_prompt_or_command_interface(judge_config) -> None:
    client = TestClient(create_app(judge_config))

    response = client.get("/judge")

    assert response.status_code == 200
    html = response.text
    assert "LedgerSoul Judge Demo" in html
    assert "Run Transaction Lookup" in html
    assert "Run DOKU Payment Methods" in html
    assert "textarea" not in html.lower()
    assert "shell" not in html.lower()
    assert "command" not in html.lower()
    assert "/agent/run" not in html
