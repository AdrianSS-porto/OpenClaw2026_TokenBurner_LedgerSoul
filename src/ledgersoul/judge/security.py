"""Security helpers for LedgerSoul Judge Mode."""

from __future__ import annotations

import re
import secrets
from typing import Any

from fastapi import HTTPException

from ledgersoul.agent.config import AgentConfig

SENSITIVE_KEY_PARTS = (
    "authorization",
    "client-id",
    "client_id",
    "doku_client_id",
    "api_key",
    "secret",
    "token",
    "password",
    "credential",
)

SENSITIVE_VALUE_PATTERNS = (
    re.compile(r'Basic\s+[^\s,;"\'}]+', re.IGNORECASE),
    re.compile(r'Bearer\s+[^\s,;"\'}]+', re.IGNORECASE),
    re.compile(r"SK-[A-Za-z0-9._:-]+"),
    re.compile(r"doku_key_sandbox_[A-Za-z0-9._:-]+"),
    re.compile(r"BRN-[A-Za-z0-9._:-]+"),
)


def require_judge_token(authorization: str | None, config: AgentConfig) -> None:
    """Require the configured demo bearer token for judge API endpoints."""
    if not config.judge_demo_token:
        raise HTTPException(status_code=500, detail="Judge demo token is not configured")
    expected = f"Bearer {config.judge_demo_token}"
    if not authorization or not secrets.compare_digest(authorization, expected):
        raise HTTPException(status_code=401, detail="Invalid judge demo token")


def _is_sensitive_key(key: object) -> bool:
    normalized = str(key).lower().replace("_", "-")
    return any(part.replace("_", "-") in normalized for part in SENSITIVE_KEY_PARTS)


def _redact_string(value: str) -> str:
    redacted = value
    for pattern in SENSITIVE_VALUE_PATTERNS:
        redacted = pattern.sub(lambda match: match.group(0).split()[0] + " [REDACTED]" if " " in match.group(0) else "[REDACTED]", redacted)
    return redacted


def redact_sensitive(value: Any, *, _parent_key: object | None = None) -> Any:
    """Recursively redact credentials and credential-like values from JSON-like data."""
    if _parent_key is not None and _is_sensitive_key(_parent_key):
        return "[REDACTED]"
    if isinstance(value, dict):
        return {key: redact_sensitive(item, _parent_key=key) for key, item in value.items()}
    if isinstance(value, list):
        return [redact_sensitive(item) for item in value]
    if isinstance(value, tuple):
        return tuple(redact_sensitive(item) for item in value)
    if isinstance(value, str):
        return _redact_string(value)
    return value
