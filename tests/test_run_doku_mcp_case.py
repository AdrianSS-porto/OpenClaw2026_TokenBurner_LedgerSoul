"""Tests for DOKU MCP case runner safety behavior."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

_SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "run_doku_mcp_case.py"
_SPEC = importlib.util.spec_from_file_location("run_doku_mcp_case", _SCRIPT_PATH)
assert _SPEC and _SPEC.loader
run_doku_mcp_case = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(run_doku_mcp_case)


def test_run_doku_mcp_case_refuses_write_case_without_flag(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    case_path = tmp_path / "write_case.json"
    case_path.write_text(
        json.dumps({"tool_name": "create_qris_payment", "tool_request": "create", "risk": "sandbox_write"}),
        encoding="utf-8",
    )
    monkeypatch.setattr("sys.argv", ["run_doku_mcp_case.py", str(case_path)])

    with pytest.raises(SystemExit, match="Refusing to execute sandbox_write"):
        run_doku_mcp_case.main()


def test_run_doku_mcp_case_executes_read_case(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
    config,
    capsys,
) -> None:
    case_path = tmp_path / "read_case.json"
    case_path.write_text(
        json.dumps({
            "tool_name": "get_merchant_payment_methods",
            "tool_request": "list methods",
            "risk": "read",
        }),
        encoding="utf-8",
    )
    cfg = type(config)(
        **{
            **config.__dict__,
            "doku_client_id": "BRN-test",
            "doku_api_key": "secret-test",
        }
    )
    monkeypatch.setattr("sys.argv", ["run_doku_mcp_case.py", str(case_path)])
    monkeypatch.setattr(run_doku_mcp_case, "load_config", lambda: cfg)
    monkeypatch.setattr(
        run_doku_mcp_case,
        "call_doku_mcp_tool",
        lambda config, tool_name, tool_request: {"result": {"tool": tool_name, "request": tool_request}},
    )

    run_doku_mcp_case.main()

    output = json.loads(capsys.readouterr().out)
    assert output == {
        "result": {"tool": "get_merchant_payment_methods", "request": "list methods"}
    }
