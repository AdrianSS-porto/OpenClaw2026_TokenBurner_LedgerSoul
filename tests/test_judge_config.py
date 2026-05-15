"""Judge mode configuration tests."""

from __future__ import annotations

from ledgersoul.agent.config import load_config


def test_judge_config_defaults_are_safe(monkeypatch) -> None:
    for key in [
        "JUDGE_MODE",
        "JUDGE_DEMO_TOKEN",
        "JUDGE_ALLOW_SANDBOX_WRITES",
        "PUBLIC_DEMO_BASE_URL",
    ]:
        monkeypatch.delenv(key, raising=False)

    config = load_config()

    assert config.judge_mode is False
    assert config.judge_demo_token == ""
    assert config.judge_allow_sandbox_writes is False
    assert config.public_demo_base_url == ""


def test_judge_config_reads_env(monkeypatch) -> None:
    monkeypatch.setenv("JUDGE_MODE", "true")
    monkeypatch.setenv("JUDGE_DEMO_TOKEN", "demo-token")
    monkeypatch.setenv("JUDGE_ALLOW_SANDBOX_WRITES", "true")
    monkeypatch.setenv("PUBLIC_DEMO_BASE_URL", "https://demo.example.test")

    config = load_config()

    assert config.judge_mode is True
    assert config.judge_demo_token == "demo-token"
    assert config.judge_allow_sandbox_writes is True
    assert config.public_demo_base_url == "https://demo.example.test"
