"""Trace writer for LedgerSoul runs."""

from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from typing import Any


def _safe(s: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", s) or "event"


def write_trace(trace_dir: str, event_id: str, trace: dict[str, Any]) -> str:
    """Write `trace` to `traces/<event_id>-<timestamp>.json` and return the path."""
    os.makedirs(trace_dir, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    name = f"{_safe(event_id)}-{ts}.json"
    path = os.path.join(trace_dir, name)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(trace, f, ensure_ascii=False, indent=2, default=str)
    return path
