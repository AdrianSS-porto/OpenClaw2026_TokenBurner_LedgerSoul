"""Mock payment and transaction tools."""

from __future__ import annotations

from typing import Any


def check_payment_status(payment_id: str | None) -> dict[str, Any]:
    return {
        "payment_id": payment_id,
        "status": "failed",
        "source": "mock",
    }


def create_recovery_link(
    payment_id: str | None,
    customer_id: str | None,
    amount: int | None,
) -> dict[str, Any]:
    return {
        "payment_id": payment_id,
        "customer_id": customer_id,
        "amount": amount,
        "url": f"https://mock-payments.local/recover/{payment_id or 'unknown'}",
        "source": "mock",
    }


def get_transaction_by_invoice_number(invoice_number: str | None) -> dict[str, Any]:
    """Return a deterministic transaction record for invoice reconciliation demos."""
    invoice = invoice_number or "unknown"
    return {
        "invoice_number": invoice,
        "transaction_status": "paid",
        "amount": 20000,
        "currency": "IDR",
        "payment_method": "DOKU Sandbox Checkout",
        "customer_name": "Test Buyer",
        "source": "mock_transaction_registry",
    }
