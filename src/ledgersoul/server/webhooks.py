"""Webhook helpers (placeholder for live-mode signature validation)."""

from __future__ import annotations

import hashlib
import hmac


def verify_webhook_signature(payload: bytes, signature: str, secret: str) -> bool:
    """Constant-time HMAC-SHA256 verification.

    MVP only references this for documentation; the API accepts events directly.
    Live mode should call this before invoking the runtime.
    """
    if not secret:
        return False
    expected = hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)
