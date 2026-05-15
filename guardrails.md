# Guardrails

These rules constrain what LedgerSoul may do autonomously.

## Amount Thresholds

- `MAX_AUTONOMOUS_AMOUNT` (default `10000`, in minor units): any action involving a higher amount must escalate.
- High-value refunds always escalate when `REQUIRE_HUMAN_APPROVAL=true`.

## Human Approval

Approval is required when:

- amount exceeds threshold,
- event type is `refund.requested` or `payment.suspicious`,
- event type is unknown,
- verifier fails repeatedly.

## Idempotency

- Every event has an `event_id`.
- `processed_events.jsonl` records terminal status per `event_id`.
- Duplicate events return status `duplicate` without calling payment tools.

## Webhook Validation

- In MVP, webhooks are accepted from trusted local sources only.
- Live mode must validate `PAYMENT_WEBHOOK_SECRET` before accepting.

## Retry Limits

- `MAX_RETRIES` controls retry attempts on transient errors.
- Repeated failure escalates rather than loops.

## No Fabricated Results

- The agent must never invent a payment status, link, or audit entry.
- All tool outputs are recorded as-returned in traces.

## Audit Logging

- `write_audit_log` is invoked as an explicit tool.
- Every terminal status appends an audit entry.

## Mock vs Live Mode

- `PAYMENT_API_MODE=mock` and `MESSAGING_MODE=mock` are MVP defaults.
- Live mode is a stretch goal and is gated behind explicit env flags.

## Judge Mode Public Demo Guardrails

When `JUDGE_MODE=true`, LedgerSoul exposes only the judge demo surface and health check:

- `GET /judge` browser demo page
- token-protected `/judge/workflows`
- token-protected `/judge/runs`
- token-protected `/judge/runs/{trace_name}/trace`
- `GET /health`

Judge Mode blocks operational and introspection endpoints including `/agent/run`, `/state`, `/traces`, `/doku/mcp/tools`, `/docs`, `/redoc`, and `/openapi.json`.

Judge Mode uses a tiny workflow allowlist. Judges may run only pre-approved workflows such as `transaction_lookup` and `doku_payment_methods`; they cannot submit arbitrary events, choose arbitrary tools, or pass arbitrary DOKU MCP tool names.

All Judge Mode traces are redacted before display. DOKU client IDs, authorization headers, API keys, secret keys, tokens, and credential-like values must never appear in the public UI or judge API responses.

`JUDGE_ALLOW_SANDBOX_WRITES=false` is the default. Sandbox-write workflows must stay disabled unless intentionally enabled for a supervised demo.

## Dangerous Tool Classification

| Tool | Class |
|---|---|
| `check_payment_status` | read |
| `draft_customer_message` | draft |
| `create_recovery_link` | write (mock) |
| `create_approval_request` | write |
| `write_audit_log` | write |
| any future refund tool | dangerous |

Dangerous tools must never run without policy clearance.

## Threat Model (short)

- **Duplicate webhooks** — mitigated by idempotency check before planning.
- **Forged webhooks** — mitigated by webhook secret validation in live mode.
- **Fabricated payment state** — mitigated by deterministic mock tools and trace-of-record discipline.
- **Unsafe refunds** — mitigated by escalation thresholds and approval requests.
- **Missing audit logs** — mitigated by explicit `write_audit_log` tool invocation on every terminal status.
