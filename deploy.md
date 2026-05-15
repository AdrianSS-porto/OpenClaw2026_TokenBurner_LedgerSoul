# Deploy

This guide deploys LedgerSoul on a fresh Linux VPS using Docker Compose.

## Requirements

- Ubuntu 22.04+ or similar.
- Outbound internet for image and dependency download.
- 1 vCPU, 1 GB RAM minimum.

## Install Prerequisites

```bash
sudo apt update
sudo apt install -y git curl python3 python3-venv python3-pip docker.io docker-compose-plugin
sudo systemctl enable --now docker
```

## Clone and Configure

```bash
git clone <REPO_URL>
cd <REPO_NAME>
cp .env.example .env
```

Edit `.env` if you want to change `PORT`, `MAX_AUTONOMOUS_AMOUNT`, or runtime mode. Defaults are safe for the MVP.

For DOKU MCP sandbox, set these local-only values in `.env`:

```bash
PAYMENT_PROVIDER=doku
PAYMENT_API_MODE=sandbox
DOKU_MCP_URL=https://api-sandbox.doku.com/doku-mcp-server/mcp
DOKU_CLIENT_ID=<your DOKU Brand/Client ID>
DOKU_API_KEY=<your DOKU API key>
# or DOKU_AUTHORIZATION=Basic <base64(api_key:)>
```

DOKU requires the `Authorization` token to be generated from the API key plus a trailing colon (`api_key:`) before Base64 encoding.

## Judge Mode Public Demo

For a hackathon judging link, set these local-only environment values:

```bash
JUDGE_MODE=true
JUDGE_DEMO_TOKEN=<random-demo-token-not-a-doku-secret>
JUDGE_ALLOW_SANDBOX_WRITES=false
PUBLIC_DEMO_BASE_URL=<optional public https URL>
PAYMENT_PROVIDER=doku
PAYMENT_API_MODE=sandbox
DOKU_MCP_URL=https://api-sandbox.doku.com/doku-mcp-server/mcp
DOKU_CLIENT_ID=[REDACTED]
DOKU_API_KEY=[REDACTED]
```

Give judges only:

- the public `/judge` URL
- the demo token

Do not give judges SSH, local filesystem access, Hermes/Telegram access, DOKU credentials, or any admin/debug endpoint.

Fast hackathon exposure options:

```bash
cloudflared tunnel --url http://127.0.0.1:8000
# or
ngrok http 8000
```

The reverse proxy or tunnel should expose only the LedgerSoul HTTP app port. `JUDGE_MODE=true` hides `/agent/run`, `/state`, `/traces`, `/doku/mcp/tools`, `/docs`, `/redoc`, and `/openapi.json`.

## Bring Up the Service

```bash
docker compose up -d --build
```

## Verify Health

```bash
curl http://localhost:8000/health
curl http://localhost:8000/doku/mcp/status
```

Expected:

```json
{"ok": true, "service": "ledgersoul", "mode": "demo"}
```

## Smoke Test a Scenario

```bash
curl -X POST http://localhost:8000/agent/run \
  -H "Content-Type: application/json" \
  -d @examples/scenarios/payment_failed.json
```

## Persistence

`./state` and `./traces` are mounted as Docker volumes. Stopping and recreating the container preserves prior runs.

## Logs

```bash
docker compose logs -f agent
```

## Updating

```bash
git pull
docker compose up -d --build
```

## Tearing Down

```bash
docker compose down
```

To wipe state and traces:

```bash
./scripts/reset_state.sh
```

## Hardening (post-MVP)

- Put a reverse proxy (Caddy or nginx) in front for TLS.
- Restrict `/webhooks/payment` to trusted source IPs.
- Set `PAYMENT_WEBHOOK_SECRET` and validate signatures.
- Switch to a non-root container user.
