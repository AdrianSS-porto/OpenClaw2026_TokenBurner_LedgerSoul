"""Demo runner: load a scenario file and execute one full agent run."""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from ledgersoul.agent.config import load_config
from ledgersoul.agent.runtime import AgentRuntime


def _summarize(result: Any) -> dict[str, Any]:
    data = result.model_dump()
    return {
        "event_id": data["event_id"],
        "status": data["status"],
        "classification": data["plan"]["event_classification"],
        "risk_level": data["plan"]["risk_level"],
        "requires_human": data["plan"]["requires_human"],
        "tools_used": [r["tool"] for r in data["tool_results"]],
        "verification_ok": data["verification"]["ok"],
        "verification_reason": data["verification"]["reason"],
        "trace_path": data.get("trace_path"),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run a single LedgerSoul scenario.")
    parser.add_argument("scenario", help="Path to scenario JSON file")
    parser.add_argument("--full", action="store_true", help="Print full result JSON")
    args = parser.parse_args(argv)

    with open(args.scenario, "r", encoding="utf-8") as f:
        event = json.load(f)

    runtime = AgentRuntime(load_config())
    result = runtime.run(event)

    payload = result.model_dump() if args.full else _summarize(result)
    print(json.dumps(payload, indent=2, ensure_ascii=False, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
