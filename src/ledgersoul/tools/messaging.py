"""Mock messaging tool."""

from __future__ import annotations

from typing import Any

from ledgersoul.agent.models import AgentEvent


def draft_customer_message(
    event: AgentEvent,
    recovery_link: str | None = None,
) -> dict[str, Any]:
    if recovery_link:
        message = (
            f"Hi customer {event.customer_id or 'there'}, we noticed your payment did "
            f"not complete. You can retry here: {recovery_link}"
        )
    else:
        message = (
            f"Hi customer {event.customer_id or 'there'}, we noticed an issue with your "
            f"payment and our team is reviewing it."
        )
    return {
        "channel": "mock",
        "message": message,
        "sent": False,
    }
