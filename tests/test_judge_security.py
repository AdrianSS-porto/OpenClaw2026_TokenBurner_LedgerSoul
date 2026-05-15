"""Judge mode token and redaction tests."""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from ledgersoul.judge.security import redact_sensitive, require_judge_token


def test_require_judge_token_accepts_expected_token(judge_config) -> None:
    assert require_judge_token("Bearer judge-token", judge_config) is None


def test_require_judge_token_rejects_missing_or_wrong_token(judge_config) -> None:
    with pytest.raises(HTTPException):
        require_judge_token(None, judge_config)
    with pytest.raises(HTTPException):
        require_judge_token("Bearer wrong", judge_config)


def test_redaction_removes_secret_like_keys_and_values() -> None:
    data = {
        "headers": {
            "Authorization": "Basic SHOULD_NOT_LEAK",
            "Client-Id": "BRN-SHOULD_NOT_LEAK",
        },
        "doku_api_key": "SK-SHOULD_NOT_LEAK",
        "nested": {"payment_api_key": "doku_key_sandbox_SHOULD_NOT_LEAK"},
        "text": "Authorization: Basic SHOULD_NOT_LEAK and SK-SHOULD_NOT_LEAK",
        "safe": "completed",
    }

    redacted = redact_sensitive(data)

    assert redacted["headers"]["Authorization"] == "[REDACTED]"
    assert redacted["headers"]["Client-Id"] == "[REDACTED]"
    assert redacted["doku_api_key"] == "[REDACTED]"
    assert redacted["nested"]["payment_api_key"] == "[REDACTED]"
    assert "SHOULD_NOT_LEAK" not in redacted["text"]
    assert redacted["safe"] == "completed"
