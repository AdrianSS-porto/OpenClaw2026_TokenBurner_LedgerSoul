"""Run one explicit DOKU MCP case from examples/mcp_cases.

This script can create sandbox objects when the selected case uses a write tool.
Use only with sandbox credentials unless you intentionally point DOKU_MCP_URL at production.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from ledgersoul.agent.config import load_config
from ledgersoul.tools.doku_mcp import call_doku_mcp_tool, doku_mcp_config_status


def main() -> None:
    parser = argparse.ArgumentParser(description="Run an explicit DOKU MCP sandbox case")
    parser.add_argument("case", help="Path to a JSON case under examples/mcp_cases")
    parser.add_argument(
        "--execute-write",
        action="store_true",
        help="Required for cases marked sandbox_write because they create remote sandbox objects",
    )
    args = parser.parse_args()

    case_path = Path(args.case)
    case = json.loads(case_path.read_text(encoding="utf-8"))
    if case.get("risk") == "sandbox_write" and not args.execute_write:
        raise SystemExit(
            "Refusing to execute sandbox_write case without --execute-write. "
            "This protects against accidental remote object creation."
        )

    config = load_config()
    status = doku_mcp_config_status(config)
    if not status["configured"]:
        raise SystemExit(f"DOKU MCP is not configured: missing {status['missing']}")

    result = call_doku_mcp_tool(config, case["tool_name"], case["tool_request"])
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
