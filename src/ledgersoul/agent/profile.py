"""Load LedgerSoul's markdown agent contract documents."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

REQUIRED_PROFILE_DOCS = (
    "soul.md",
    "agent.md",
    "lifecycle.md",
    "guardrails.md",
    "tools.md",
    "architecture.md",
    "demo.md",
    "deploy.md",
    "evals.md",
    "README.md",
)


def project_root() -> Path:
    """Return the repository/workspace root for the installed package."""
    return Path(__file__).resolve().parents[3]


def _document_entry(root: Path, name: str, include_content: bool) -> dict[str, Any]:
    path = root / name
    if not path.exists():
        return {
            "exists": False,
            "path": str(path),
            "sha256": None,
            "bytes": 0,
            "content": "" if include_content else None,
        }

    content = path.read_text(encoding="utf-8")
    entry: dict[str, Any] = {
        "exists": True,
        "path": str(path),
        "sha256": hashlib.sha256(content.encode("utf-8")).hexdigest(),
        "bytes": len(content.encode("utf-8")),
    }
    if include_content:
        entry["content"] = content
    return entry


def load_agent_profile(include_content: bool = True) -> dict[str, Any]:
    """Load the markdown files that define and verify the LedgerSoul agent."""
    root = project_root()
    documents = {
        name: _document_entry(root, name, include_content=include_content)
        for name in REQUIRED_PROFILE_DOCS
    }
    missing = [name for name, doc in documents.items() if not doc["exists"]]
    agent_doc = documents["agent.md"]
    soul_doc = documents["soul.md"]
    return {
        "loaded": not missing,
        "root": str(root),
        "required_documents": list(REQUIRED_PROFILE_DOCS),
        "missing": missing,
        "summary": {
            "name": "LedgerSoul",
            "mission": "autonomous payment-operations agent",
            "agent_md_loaded": bool(agent_doc["exists"]),
            "soul_md_loaded": bool(soul_doc["exists"]),
            "document_count": len(documents) - len(missing),
        },
        "documents": documents,
    }
