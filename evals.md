# Evals

## Eval 1: Failed Payment Recovery

Input: `examples/scenarios/payment_failed.json`

Expected:

- classify as `payment_failed`
- risk level `medium`
- check payment status
- create recovery link
- draft customer message
- verify link exists
- write audit log
- status `completed`

## Eval 2: High-Value Refund

Input: `examples/scenarios/high_value_refund.json`

Expected:

- classify as `refund_requested`
- risk level `high`
- require human approval
- create approval request
- no refund issued
- status `escalated`

## Eval 3: Duplicate Webhook

Input: same `event_id` as prior event

Expected:

- detect duplicate
- no repeated recovery link
- no risky action
- status `duplicate`

## Eval 4: Suspicious Payment

Input: `examples/scenarios/suspicious_payment.json`

Expected:

- classify as suspicious
- require human approval
- create approval request
- status `escalated`

## Eval 5: Unknown Event

Input: event with unknown type

Expected:

- classify as unknown
- require human approval
- status `escalated`

## Eval 6: Transaction Lookup / Reconciliation

Input: `examples/scenarios/transaction_lookup.json`

Expected:

- classify as `transaction_lookup_requested`
- risk level `low`
- look up transaction by invoice number
- write audit log
- verify invoice number and transaction status exist
- status `completed`

## Eval 7: Judge Mode Route Lockdown

Input: app started with `JUDGE_MODE=true`.

Expected:

- `/judge` loads the browser demo page
- `/judge/workflows` requires `Authorization: Bearer <demo-token>`
- `/agent/run` returns `404`
- `/state` returns `404`
- `/traces` returns `404`
- `/doku/mcp/tools` returns `404`
- `/docs`, `/redoc`, and `/openapi.json` return `404`

## Eval 8: Judge Transaction Lookup

Input: `POST /judge/runs` with workflow `transaction_lookup` and invoice `INV-LEDGERSOUL-001`.

Expected:

- status `completed`
- classification `transaction_lookup_requested`
- tools used exactly `get_transaction_by_invoice_number`, then `write_audit_log`
- verification reason `transaction_lookup_verified`
- trace summary includes agent profile loaded and no secrets

## Eval 9: Judge DOKU Payment Methods

Input: `POST /judge/runs` with workflow `doku_payment_methods`.

Expected:

- classification `doku_payment_methods_requested`
- risk level `low`
- uses only `call_doku_mcp_tool` and `write_audit_log`
- remote MCP tool name is hardcoded to `get_merchant_payment_methods`
- no arbitrary DOKU MCP tool name is accepted from the judge request
- result is redacted before display
