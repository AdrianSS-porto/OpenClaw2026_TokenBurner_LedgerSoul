# LedgerSoul

> Team **TokenBurner** · OpenClaw Agenthon 2026 · Track: **Best Payment Use Case**
> An autonomous payment-operations agent for DOKU merchants.

LedgerSoul handles the firefight that happens *after* a payment event lands — failed payments, refund requests, suspicious charges, duplicate webhooks — without humans in the loop, but with a full audit trail. It is built on the live **DOKU MCP Server** sandbox.

## What LedgerSoul Is

A **multi-agent system** with one deterministic verification spine:

```
Event ──► Reasoning Agent  ──► Planner Agent ──► Executor Agent ──► Verifier Agent ──► Audit
         (LLM, classify +     (rules + policy)   (TOOL_REGISTRY +    (deterministic       (JSON trace +
          extract intent)                         DOKU MCP)           checks · ok/fail)    audit_log.jsonl)
```

Every event ends in **exactly one** terminal status:

```
completed  ·  escalated  ·  duplicate  ·  blocked  ·  failed_verification  ·  error
```

Always with a JSON trace.

## Why It Fits the Rubric

| Criterion | How LedgerSoul scores |
|---|---|
| **Use Case Clarity & Impact** | Real DOKU merchant pain: 24/7 ops firefight. Recovery cycles drop from hours to minutes. |
| **Creativity & Originality** | Deterministic agent lifecycle + LLM reasoning + Judge Mode locked browser demo. Not a chatbot. Not a Zapier flow. |
| **Autonomy & Agent Behaviour** | 12-stage autonomous loop. LLM-based reasoning. Dynamic tool selection through `TOOL_REGISTRY`. Idempotency, policy escalation, and `failed_verification` for edge cases. |
| **Technical Execution** | Multi-agent architecture · 60+ tests passing · ruff clean · type hints · explicit MCP integration · zero-secret commits. |
| **Real-World Deployability** | Reproducible install. Docker + Uvicorn. Sandbox-first DOKU integration. Judge Mode for safe public demos. |

## Pain Points Solved

- **Failed payments** drop silently → autonomous recovery within minutes.
- **Suspicious charges** pile up in inboxes → consistent triage path with risk scoring.
- **Refund requests** get approved on gut feel → policy-driven escalation with audit trail.
- **Duplicate webhooks** corrupt reconciliation → idempotency log per `event_id`.
- **No audit trail** today → JSON trace + append-only `audit_log.jsonl` for every run.

## Quickstart (Reproducible)

```bash
# 1. Clone and install
git clone https://github.com/<you>/OpenClaw2026_TokenBurner_LedgerSoul.git
cd OpenClaw2026_TokenBurner_LedgerSoul
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# 2. Configure environment (no secrets in repo)
cp .env.example .env
# Fill DOKU sandbox credentials in .env (see DOKU MCP section below)

# 3. Run tests + lint (proves correctness)
pytest -q
ruff check .

# 4. Run an end-to-end scenario locally
./scripts/reset_state.sh
python -m ledgersoul.demo.run_scenario examples/scenarios/payment_failed.json
python -m ledgersoul.demo.run_scenario examples/scenarios/transaction_lookup.json

# 5. Inspect the audit trail
ls traces/
cat state/audit_log.jsonl | tail -1
```

## Run the Server

```bash
uvicorn ledgersoul.server.api:app --host 127.0.0.1 --port 8000
```

Then in another terminal:

```bash
# Health check
curl http://localhost:8000/health

# Run the recovery scenario through the runtime
curl -X POST http://localhost:8000/agent/run \
     -H 'Content-Type: application/json' \
     -d @examples/scenarios/payment_failed.json | jq

# DOKU MCP config status (no secrets returned)
curl http://localhost:8000/doku/mcp/status

# DOKU MCP live tool listing (read-only)
curl 'http://localhost:8000/doku/mcp/tools?live=true'
```

## Judge Mode — Locked Browser Demo

LedgerSoul ships a **safe public demo surface** so judges can run pre-approved DOKU workflows without server access, code editing, or arbitrary tool calls.

```bash
# .env additions
JUDGE_MODE=true
JUDGE_DEMO_TOKEN=<random-demo-token>
JUDGE_ALLOW_SANDBOX_WRITES=false
PAYMENT_PROVIDER=doku
PAYMENT_API_MODE=sandbox

uvicorn ledgersoul.server.api:app --host 127.0.0.1 --port 8000
```

Then open `http://localhost:8000/judge` and paste the demo token.

The judge UI exposes two MVP workflows — both go through the full 12-stage runtime and write redacted traces:

- **Run Transaction Lookup** → `get_transaction_by_invoice_number` + `write_audit_log`
- **Run DOKU Payment Methods** → `call_doku_mcp_tool(get_merchant_payment_methods)` + `write_audit_log`

Judge Mode **blocks** these in the same process: `/agent/run`, `/state`, `/traces`, `/doku/mcp/tools`, `/docs`, `/redoc`, `/openapi.json`.

## DOKU MCP Sandbox Setup

LedgerSoul talks to the DOKU MCP Server via HTTP JSON-RPC, exactly as documented at https://developers.doku.com/accept-payments/doku-mcp-server.

```bash
# .env (use your own DOKU sandbox credentials)
PAYMENT_PROVIDER=doku
PAYMENT_API_MODE=sandbox
DOKU_MCP_URL=https://api-sandbox.doku.com/doku-mcp-server/mcp
DOKU_CLIENT_ID=<your DOKU Brand / Client Id>
DOKU_API_KEY=<your DOKU Active Secret Key>
# Optional: precomputed Authorization. If unset, LedgerSoul derives it.
# DOKU_AUTHORIZATION=Basic <base64(secret_key + ":")>
```

LedgerSoul auto-builds the `Authorization: Basic <base64(secret:)>` header and sends both `Client-Id` and `Authorization` on every JSON-RPC request, plus the `MCP-Protocol-Version` header.

## Architecture

```
src/ledgersoul/
├── agent/
│   ├── reasoner.py       # LLM Reasoning Agent (multi-agent reasoning layer)
│   ├── planner.py        # Planner Agent (deterministic plan + risk)
│   ├── executor.py       # Executor Agent (TOOL_REGISTRY dispatch)
│   ├── verifier.py       # Verifier Agent (deterministic checks)
│   ├── policies.py       # Amount thresholds + escalation policy
│   ├── runtime.py        # 12-stage orchestration loop
│   ├── tool_registry.py  # Single allowlist for every tool the agent can call
│   ├── profile.py        # Loads soul.md / agent.md as runtime contract
│   └── config.py         # Env-driven configuration
├── tools/
│   ├── payments.py       # Mock + lookup tools
│   ├── messaging.py      # Customer message drafting
│   ├── audit.py          # write_audit_log
│   └── doku_mcp.py       # DOKU MCP HTTP JSON-RPC client
├── judge/
│   ├── workflows.py      # Workflow allowlist for judges
│   ├── security.py       # Token auth + recursive redaction
│   └── trace_view.py     # Safe trace summarizer
└── server/
    ├── api.py            # FastAPI app + route guard
    ├── judge.py          # /judge router (browser UI + APIs)
    └── static/judge.html # Browser demo
```

### The 12-Stage Autonomous Loop

```
01 boot      02 observe   03 validate    04 idempotency
05 interpret 06 plan      07 policy      08 act
09 verify    10 remember  11 reflect     12 stop / escalate
```

Every stage is recorded in the run trace.

## Tools (Explicit Registry)

Every agent action goes through `src/ledgersoul/agent/tool_registry.py`. The registry is the single source of truth.

| Tool | Class | Purpose |
|---|---|---|
| `get_transaction_by_invoice_number` | read | Look up a payment by invoice id |
| `create_recovery_link` | write | Recover a failed payment |
| `draft_customer_message` | draft | Compose customer notification text |
| `create_approval_request` | escalation | File a human-approval ticket |
| `list_doku_mcp_tools` | read | Initialize DOKU MCP and list remote tools |
| `call_doku_mcp_tool` | dispatch | Workflow-scoped DOKU MCP tool dispatch |
| `write_audit_log` | audit | Append to `state/audit_log.jsonl` |

The Reasoning Agent classifies the event; the Planner picks tools from this registry — no arbitrary tool execution paths exist.

## Evals

```
01  Failed Payment Recovery       → completed
02  High-Value Refund             → escalated (over threshold)
03  Duplicate Webhook             → duplicate (idempotency)
04  Suspicious Payment            → escalated (risk)
05  Unknown Event                 → escalated (fallback)
06  Transaction Lookup            → completed (DOKU sandbox reconciliation)
07  Judge Route Lockdown          → ops endpoints return 404 in Judge Mode
08  Judge Transaction Lookup      → completed (full deterministic lifecycle)
09  Judge DOKU Payment Methods    → completed (read-only MCP + redaction)
```

All passing — see `pytest -q`.

## AI Tools / Models Used

| Component | Tool / Model |
|---|---|
| Reasoning Agent | Anthropic Claude (via 9router OpenAI-compatible endpoint) — pluggable |
| Tool dispatch | DOKU MCP Server (sandbox), MCP protocol `2025-06-18` |
| Server framework | FastAPI + Uvicorn |
| HTTP client | httpx |
| Tests | pytest |
| Lint | ruff |
| Build assistant | Hermes Agent (this submission was built collaboratively with Hermes Agent during the 12-hour competition window) |

## Submission Files

- `soul.md` — agent identity / values / refusals
- `agent.md` — operating contract (loaded at runtime, hashed in every trace)
- `lifecycle.md` — 12-stage definition
- `guardrails.md` — autonomy limits
- `tools.md` — tool registry documentation
- `architecture.md` — system architecture
- `evals.md` — eval definitions and expected outcomes
- `demo.md` — demo scenarios
- `deploy.md` — deployment guide
- `OpenClaw2026_TokenBurner_LedgerSoul.pdf` — 5-slide pitch deck (root)

## License

MIT.
