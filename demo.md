# Demo

This demo runs the full agent lifecycle deterministically with mock tools. No API keys are required.

## Local Demo

```bash
cp .env.example .env
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
./scripts/reset_state.sh
./scripts/run_demo.sh
```

Expected output:

- one trace per scenario under `traces/`
- audit entries in `state/audit_log.jsonl`
- pending approvals in `state/pending_approvals.jsonl` for escalated events
- terminal summary printed for each scenario

## Docker Demo

```bash
cp .env.example .env
docker compose up --build
curl http://localhost:8000/health
curl -X POST http://localhost:8000/agent/run \
  -H "Content-Type: application/json" \
  -d @examples/scenarios/payment_failed.json
```

## Scenarios Walked Through

| Scenario | Expected status |
|---|---|
| `payment_failed.json` | `completed` |
| `payment_recovered.json` | `completed` |
| `high_value_refund.json` | `escalated` |
| `duplicate_webhook.json` | `duplicate` |
| `suspicious_payment.json` | `escalated` |
| `api_failure.json` | `escalated` or `failed_verification` |
| `transaction_lookup.json` | `completed` |

## Judge Mode Demo

Judge Mode exposes a browser-only demo at `/judge` plus token-protected `/judge/*` endpoints. It is intended for hackathon judges who should be able to run DOKU workflows and inspect traces without access to server administration, arbitrary event submission, arbitrary MCP tool calls, or secrets.

Enable locally or in a public demo deployment with:

```bash
JUDGE_MODE=true
JUDGE_DEMO_TOKEN=<random-demo-token-not-a-doku-secret>
JUDGE_ALLOW_SANDBOX_WRITES=false
PAYMENT_PROVIDER=doku
PAYMENT_API_MODE=sandbox
DOKU_MCP_URL=https://api-sandbox.doku.com/doku-mcp-server/mcp
DOKU_CLIENT_ID=[REDACTED]
DOKU_API_KEY=[REDACTED]
```

Recommended judge flow:

1. Open the public `/judge` URL.
2. Enter the provided demo token.
3. Click **Run Transaction Lookup** for a deterministic full-lifecycle trace.
4. Click **Run DOKU Payment Methods** for a read-only DOKU MCP sandbox workflow.
5. Inspect status, classification, risk level, tools used, verification reason, timeline, and redacted trace.

In `JUDGE_MODE=true`, the app hides operational endpoints such as `/agent/run`, `/state`, `/traces`, `/doku/mcp/tools`, `/docs`, `/redoc`, and `/openapi.json`.

## Inspecting Outputs

```bash
ls traces/
cat state/audit_log.jsonl
cat state/processed_events.jsonl
cat state/pending_approvals.jsonl
```

## Resetting

```bash
./scripts/reset_state.sh
```
