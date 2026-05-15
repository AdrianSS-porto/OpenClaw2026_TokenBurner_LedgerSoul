"""JSON/JSONL persistence for LedgerSoul state."""

from __future__ import annotations

import json
import os
from typing import Any


class AgentMemory:
    """File-backed memory using JSONL append logs and JSON state.

    State files (under `state_dir`):
        processed_events.jsonl  — terminal status per event_id
        audit_log.jsonl         — explicit audit entries
        memory.jsonl            — episodic notes
        pending_approvals.jsonl — outstanding human approvals
    """

    PROCESSED = "processed_events.jsonl"
    AUDIT = "audit_log.jsonl"
    MEMORY = "memory.jsonl"
    APPROVALS = "pending_approvals.jsonl"

    def __init__(self, state_dir: str) -> None:
        self.state_dir = state_dir
        os.makedirs(state_dir, exist_ok=True)

    # ---- internal helpers ----

    def _path(self, name: str) -> str:
        return os.path.join(self.state_dir, name)

    def _append_jsonl(self, name: str, entry: dict[str, Any]) -> None:
        path = self._path(name)
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def _read_jsonl(self, name: str) -> list[dict[str, Any]]:
        path = self._path(name)
        if not os.path.exists(path):
            return []
        out: list[dict[str, Any]] = []
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    out.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        return out

    # ---- idempotency ----

    def is_processed(self, event_id: str) -> bool:
        for entry in self._read_jsonl(self.PROCESSED):
            if entry.get("event_id") == event_id:
                return True
        return False

    def mark_processed(self, event_id: str, status: str) -> None:
        self._append_jsonl(self.PROCESSED, {"event_id": event_id, "status": status})

    # ---- append helpers ----

    def append_audit(self, entry: dict[str, Any]) -> None:
        self._append_jsonl(self.AUDIT, entry)

    def append_memory(self, entry: dict[str, Any]) -> None:
        self._append_jsonl(self.MEMORY, entry)

    def append_pending_approval(self, entry: dict[str, Any]) -> None:
        self._append_jsonl(self.APPROVALS, entry)

    # ---- inspection ----

    def get_state_summary(self) -> dict[str, Any]:
        processed = self._read_jsonl(self.PROCESSED)
        audits = self._read_jsonl(self.AUDIT)
        approvals = self._read_jsonl(self.APPROVALS)
        memories = self._read_jsonl(self.MEMORY)
        return {
            "processed_count": len(processed),
            "audit_count": len(audits),
            "pending_approvals_count": len(approvals),
            "memory_count": len(memories),
            "last_processed": processed[-5:],
            "pending_approvals": approvals[-5:],
        }

    def has_approval_for(self, event_id: str) -> bool:
        for entry in self._read_jsonl(self.APPROVALS):
            if entry.get("event_id") == event_id:
                return True
        return False
