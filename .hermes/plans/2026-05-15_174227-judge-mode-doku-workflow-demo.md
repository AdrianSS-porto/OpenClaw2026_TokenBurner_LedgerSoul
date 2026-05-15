# Judge Mode DOKU Workflow Demo Implementation Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** Build a browser-only LedgerSoul “Judge Mode” so hackathon judges can run pre-approved DOKU workflows and inspect redacted traces, without shell access, coding/chat access, arbitrary tool access, or secret exposure.

**Architecture:** Add a locked FastAPI judge surface under `/judge/*` with a tiny allowlisted workflow registry. Judge requests are converted into deterministic LedgerSoul events, executed through the existing planner/executor/verifier/runtime path, and tools still resolve only through `TOOL_REGISTRY`. When `JUDGE_MODE=true`, block all non-judge operational endpoints from the public app.

**Tech Stack:** FastAPI, Pydantic, existing LedgerSoul runtime, existing DOKU MCP helper, vanilla HTML/CSS/JS for the judge UI, pytest/TestClient, ruff.

---

## Current Context

LedgerSoul already has:

- `src/ledgersoul/server/api.py` with `/health`, `/agent/profile`, `/agent/run`, `/doku/mcp/status`, `/doku/mcp/tools`, `/state`, and trace endpoints.
- `src/ledgersoul/agent/runtime.py` with validation, idempotency, planning, policy, execution, verification, reflection, memory, and trace writing.
- `src/ledgersoul/agent/tool_registry.py` with explicit `TOOL_REGISTRY` including:
  - `get_transaction_by_invoice_number`
  - `write_audit_log`
  - `list_doku_mcp_tools`
  - `call_doku_mcp_tool`
- `src/ledgersoul/tools/doku_mcp.py` with DOKU MCP JSON-RPC helpers.
- `examples/scenarios/transaction_lookup.json` proving the deterministic transaction lookup flow.
- Tests currently passing with `pytest -q` and `ruff check .`.

## Non-Negotiable Security Requirements

Judge Mode must **not** expose:

- shell/server command execution
- arbitrary event submission to `/agent/run`
- arbitrary DOKU MCP tool calling
- arbitrary `tool_name` or `toolRequest` fields
- FastAPI `/docs`, `/redoc`, or `/openapi.json` in public judge mode
- raw `/traces`, `/state`, or debug/admin endpoints
- DOKU credentials, client/brand ID, authorization header, base64 header value, API/secret keys, or `.env` values
- any “ask the agent to code” or free-form prompt interface

Judge Mode may expose only:

- a static/browser UI at `/judge`
- token-protected workflow list/run/trace endpoints under `/judge/*`
- safe `/health` if desired

## MVP Workflow Set

Implement this allowlist first:

1. `transaction_lookup`
   - Risk: `read_only`
   - Inputs: `invoice_number`
   - Event type: `transaction.lookup_requested`
   - Expected tools:
     - `get_transaction_by_invoice_number`
     - `write_audit_log`
   - Purpose: shows full autonomous lifecycle and trace using deterministic data.

2. `doku_payment_methods`
   - Risk: `read_only`
   - Inputs: none
   - Event type: `doku.payment_methods_requested`
   - Expected tools:
     - `call_doku_mcp_tool`
     - `write_audit_log`
   - Remote DOKU MCP tool: `get_merchant_payment_methods`
   - Purpose: safely proves live DOKU MCP connectivity without creating payment objects.

3. `sandbox_payment_link` — optional, disabled by default
   - Risk: `sandbox_write`
   - Inputs: `invoice_number`, `amount`, `currency`, optional `customer_name`
   - Event type: `doku.sandbox_payment_link_requested`
   - Expected tools:
     - `call_doku_mcp_tool`
     - `write_audit_log`
   - Remote DOKU MCP tool: `create_doku_customer_form_payment_link`
   - Requires both:
     - `JUDGE_ALLOW_SANDBOX_WRITES=true`
     - request confirmation string: `CREATE_SANDBOX_OBJECT`

For the first hackathon build, ship workflows 1 and 2. Add workflow 3 only if time remains.

---

## Task 1: Add Judge Mode Configuration

**Objective:** Add environment-driven config values for judge mode, demo auth, route hiding, and sandbox-write guardrails.

**Files:**

- Modify: `src/ledgersoul/agent/config.py`
- Modify: `.env.example`
- Test: `tests/test_judge_config.py`

**Step 1: Write failing config tests**

Create `tests/test_judge_config.py`:

```python
from ledgersoul.agent.config import load_config


def test_judge_config_defaults_are_safe(monkeypatch):
    for key in [
        "JUDGE_MODE",
        "JUDGE_DEMO_TOKEN",
        "JUDGE_ALLOW_SANDBOX_WRITES",
        "PUBLIC_DEMO_BASE_URL",
    ]:
        monkeypatch.delenv(key, raising=False)

    config = load_config()

    assert config.judge_mode is False
    assert config.judge_demo_token == ""
    assert config.judge_allow_sandbox_writes is False
    assert config.public_demo_base_url == ""


def test_judge_config_reads_env(monkeypatch):
    monkeypatch.setenv("JUDGE_MODE", "true")
    monkeypatch.setenv("JUDGE_DEMO_TOKEN", "demo-token")
    monkeypatch.setenv("JUDGE_ALLOW_SANDBOX_WRITES", "true")
    monkeypatch.setenv("PUBLIC_DEMO_BASE_URL", "https://demo.example.com")

    config = load_config()

    assert config.judge_mode is True
    assert config.judge_demo_token == "demo-token"
    assert config.judge_allow_sandbox_writes is True
    assert config.public_demo_base_url == "https://demo.example.com"
```

Run:

```bash
. .venv/bin/activate && pytest tests/test_judge_config.py -q
```

Expected: fail because fields do not exist yet.

**Step 2: Update config dataclass**

Add fields to `AgentConfig`:

```python
judge_mode: bool
judge_demo_token: str
judge_allow_sandbox_writes: bool
public_demo_base_url: str
```

Add in `load_config()`:

```python
judge_mode=os.getenv("JUDGE_MODE", "false").lower() == "true",
judge_demo_token=os.getenv("JUDGE_DEMO_TOKEN", ""),
judge_allow_sandbox_writes=os.getenv("JUDGE_ALLOW_SANDBOX_WRITES", "false").lower() == "true",
public_demo_base_url=os.getenv("PUBLIC_DEMO_BASE_URL", ""),
```

**Step 3: Update `.env.example`**

Add non-secret examples only:

```bash
# Judge demo mode. Use a random non-DOKU token for public demos.
JUDGE_MODE=false
JUDGE_DEMO_TOKEN=
JUDGE_ALLOW_SANDBOX_WRITES=false
PUBLIC_DEMO_BASE_URL=
```

Do not include real credentials.

**Step 4: Verify**

Run:

```bash
. .venv/bin/activate && pytest tests/test_judge_config.py -q && ruff check .
```

Expected: pass.

---

## Task 2: Refactor FastAPI App Creation and Block Non-Judge Routes in Judge Mode

**Objective:** Make the app testable with injected config and ensure public judge deployments cannot reach `/agent/run`, `/doku/mcp/tools`, `/state`, or `/traces`.

**Files:**

- Modify: `src/ledgersoul/server/api.py`
- Test: `tests/test_judge_route_guard.py`

**Step 1: Write failing route-guard tests**

Create `tests/test_judge_route_guard.py`:

```python
from fastapi.testclient import TestClient

from ledgersoul.agent.config import AgentConfig
from ledgersoul.server.api import create_app


def _config(tmp_path, *, judge_mode=True, token="judge-token"):
    return AgentConfig(
        agent_mode="demo",
        port=8000,
        state_dir=str(tmp_path / "state"),
        trace_dir=str(tmp_path / "traces"),
        payment_provider="mock",
        payment_api_mode="sandbox",
        payment_api_key="",
        doku_api_key="",
        doku_client_id="",
        doku_authorization="",
        doku_mcp_url="https://api-sandbox.doku.com/doku-mcp-server/mcp",
        messaging_mode="mock",
        max_autonomous_amount=10000,
        require_human_approval=True,
        max_retries=2,
        judge_mode=judge_mode,
        judge_demo_token=token,
        judge_allow_sandbox_writes=False,
        public_demo_base_url="",
    )


def test_judge_mode_blocks_operational_endpoints(tmp_path):
    client = TestClient(create_app(_config(tmp_path, judge_mode=True)))

    assert client.post("/agent/run", json={}).status_code == 404
    assert client.get("/state").status_code == 404
    assert client.get("/traces").status_code == 404
    assert client.get("/doku/mcp/tools?live=true").status_code == 404


def test_judge_mode_keeps_judge_and_health_routes(tmp_path):
    client = TestClient(create_app(_config(tmp_path, judge_mode=True)))

    assert client.get("/health").status_code == 200
    assert client.get("/judge").status_code == 200
```

Run:

```bash
. .venv/bin/activate && pytest tests/test_judge_route_guard.py -q
```

Expected: fail until `create_app()` and route guard exist.

**Step 2: Add app factory**

Refactor `src/ledgersoul/server/api.py` to expose:

```python
def create_app(config: AgentConfig | None = None) -> FastAPI:
    config = config or load_config()
    runtime = AgentRuntime(config)
    app = FastAPI(
        title="LedgerSoul",
        version="0.1.0",
        docs_url=None if config.judge_mode else "/docs",
        redoc_url=None if config.judge_mode else "/redoc",
        openapi_url=None if config.judge_mode else "/openapi.json",
    )
    # register middleware and routes here
    return app


app = create_app()
```

Keep backwards compatibility so existing tests importing `from ledgersoul.server.api import app` still work.

**Step 3: Add judge-mode route guard**

Inside `create_app()`, before routes or after app creation:

```python
JUDGE_ALLOWED_PREFIXES = ("/judge", "/health")

@app.middleware("http")
async def judge_mode_guard(request, call_next):
    if config.judge_mode:
        path = request.url.path
        if not path.startswith(JUDGE_ALLOWED_PREFIXES):
            return JSONResponse({"detail": "not found"}, status_code=404)
    return await call_next(request)
```

**Step 4: Verify existing API still works when not in judge mode**

Add a small test or extend existing tests:

```python
def test_non_judge_mode_keeps_agent_run_available(tmp_path):
    client = TestClient(create_app(_config(tmp_path, judge_mode=False)))
    assert client.post("/agent/run", json={}).status_code != 404
```

Run:

```bash
. .venv/bin/activate && pytest tests/test_judge_route_guard.py tests/test_agent_profile.py -q && ruff check .
```

Expected: pass.

---

## Task 3: Add Judge Auth, Redaction, and Timeline Utilities

**Objective:** Protect judge API endpoints with a demo token and ensure returned traces never reveal secrets.

**Files:**

- Create: `src/ledgersoul/judge/__init__.py`
- Create: `src/ledgersoul/judge/security.py`
- Create: `src/ledgersoul/judge/trace_view.py`
- Test: `tests/test_judge_security.py`
- Test: `tests/test_judge_trace_view.py`

**Step 1: Write failing auth/redaction tests**

`tests/test_judge_security.py`:

```python
import pytest
from fastapi import HTTPException

from ledgersoul.agent.config import AgentConfig
from ledgersoul.judge.security import require_judge_token, redact_sensitive


def test_require_judge_token_accepts_expected_token(tmp_path):
    config = AgentConfig(... same safe fixture values ..., judge_mode=True, judge_demo_token="abc")
    assert require_judge_token("Bearer abc", config) is None


def test_require_judge_token_rejects_missing_or_wrong_token(tmp_path):
    config = AgentConfig(... same safe fixture values ..., judge_mode=True, judge_demo_token="abc")
    with pytest.raises(HTTPException):
        require_judge_token(None, config)
    with pytest.raises(HTTPException):
        require_judge_token("Bearer wrong", config)


def test_redaction_removes_secret_like_values():
    data = {
        "headers": {"Authorization": "Basic SHOULD_NOT_LEAK", "Client-Id": "BRN-SHOULD_NOT_LEAK"},
        "doku_api_key": "SK-SHOULD_NOT_LEAK",
        "nested": {"payment_api_key": "doku_key_sandbox_SHOULD_NOT_LEAK"},
        "safe": "completed",
    }

    redacted = redact_sensitive(data)

    assert redacted["headers"]["Authorization"] == "[REDACTED]"
    assert redacted["headers"]["Client-Id"] == "[REDACTED]"
    assert redacted["doku_api_key"] == "[REDACTED]"
    assert redacted["nested"]["payment_api_key"] == "[REDACTED]"
    assert redacted["safe"] == "completed"
```

Use a local helper to avoid repeating the full `AgentConfig` in the final test file.

`tests/test_judge_trace_view.py`:

```python
from ledgersoul.judge.trace_view import build_timeline, summarize_trace


def test_build_timeline_explains_agent_lifecycle():
    trace = {
        "status": "completed",
        "agent_profile": {"loaded": True, "documents": {"agent.md": {"exists": True}}},
        "plan": {"goal": "Reconcile transaction", "event_classification": "transaction_lookup_requested", "risk_level": "low"},
        "tool_results": [{"tool": "get_transaction_by_invoice_number", "ok": True, "result": {}}],
        "verification": {"ok": True, "reason": "transaction_lookup_verified"},
    }

    timeline = build_timeline(trace)

    assert timeline[0]["label"] == "Agent contract loaded"
    assert any(step["label"] == "Tool executed" for step in timeline)
    assert timeline[-1]["label"] == "Final status"


def test_summarize_trace_returns_safe_judge_payload():
    trace = {
        "status": "completed",
        "event": {"event_id": "evt_1"},
        "plan": {"event_classification": "transaction_lookup_requested", "risk_level": "low"},
        "tool_results": [{"tool": "write_audit_log", "ok": True, "result": {"Authorization": "Basic leak"}}],
        "verification": {"ok": True, "reason": "ok"},
    }

    summary = summarize_trace(trace)

    assert summary["status"] == "completed"
    assert summary["tools_used"] == ["write_audit_log"]
    assert summary["redacted_trace"]["tool_results"][0]["result"]["Authorization"] == "[REDACTED]"
```

**Step 2: Implement `security.py`**

Core behavior:

```python
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


def require_judge_token(authorization: str | None, config: AgentConfig) -> None:
    if not config.judge_demo_token:
        raise HTTPException(status_code=500, detail="Judge demo token is not configured")
    if authorization != f"Bearer {config.judge_demo_token}":
        raise HTTPException(status_code=401, detail="Invalid judge demo token")


def redact_sensitive(value):
    # recursively redact dict/list values when key is sensitive
```

**Step 3: Implement `trace_view.py`**

Core functions:

```python
def build_timeline(trace: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {"label": "Agent contract loaded", "ok": trace.get("agent_profile", {}).get("loaded") is True},
        {"label": "Event classified", "detail": trace.get("plan", {}).get("event_classification")},
        {"label": "Plan selected", "detail": trace.get("plan", {}).get("goal")},
        *tool timeline entries*,
        {"label": "Verification", "ok": trace.get("verification", {}).get("ok"), "detail": trace.get("verification", {}).get("reason")},
        {"label": "Final status", "detail": trace.get("status")},
    ]


def summarize_trace(trace: dict[str, Any]) -> dict[str, Any]:
    redacted = redact_sensitive(trace)
    return {
        "status": redacted.get("status"),
        "classification": redacted.get("plan", {}).get("event_classification"),
        "risk_level": redacted.get("plan", {}).get("risk_level"),
        "tools_used": [r.get("tool") for r in redacted.get("tool_results", [])],
        "verification": redacted.get("verification"),
        "timeline": build_timeline(redacted),
        "redacted_trace": redacted,
    }
```

**Step 4: Verify**

Run:

```bash
. .venv/bin/activate && pytest tests/test_judge_security.py tests/test_judge_trace_view.py -q && ruff check .
```

Expected: pass.

---

## Task 4: Add Tiny Judge Workflow Registry

**Objective:** Add the allowlist that maps judge-selectable workflows to fixed event factories and expected tools.

**Files:**

- Create: `src/ledgersoul/judge/workflows.py`
- Test: `tests/test_judge_workflows.py`

**Step 1: Write failing registry tests**

Create `tests/test_judge_workflows.py`:

```python
import pytest

from ledgersoul.judge.workflows import JUDGE_WORKFLOWS, build_event_for_workflow, validate_workflow_inputs


def test_registry_contains_only_expected_mvp_workflows():
    assert set(JUDGE_WORKFLOWS) >= {"transaction_lookup", "doku_payment_methods"}
    assert JUDGE_WORKFLOWS["transaction_lookup"].risk == "read_only"
    assert JUDGE_WORKFLOWS["doku_payment_methods"].risk == "read_only"


def test_transaction_lookup_builds_safe_event():
    event = build_event_for_workflow(
        "transaction_lookup",
        {"invoice_number": "INV-LEDGERSOUL-001", "ignored": "not allowed"},
    )

    assert event["type"] == "transaction.lookup_requested"
    assert event["event_id"].startswith("judge_transaction_lookup_")
    assert event["metadata"]["invoice_number"] == "INV-LEDGERSOUL-001"
    assert "ignored" not in event["metadata"]


def test_payment_methods_builds_safe_doku_event():
    event = build_event_for_workflow("doku_payment_methods", {})

    assert event["type"] == "doku.payment_methods_requested"
    assert event["metadata"]["doku_tool"] == "get_merchant_payment_methods"


def test_unknown_workflow_is_rejected():
    with pytest.raises(ValueError):
        validate_workflow_inputs("not_allowed", {})
```

**Step 2: Implement registry**

Use a small dataclass:

```python
from dataclasses import dataclass
from typing import Any, Literal
from uuid import uuid4

JudgeRisk = Literal["read_only", "sandbox_write"]

@dataclass(frozen=True)
class JudgeWorkflow:
    id: str
    label: str
    description: str
    risk: JudgeRisk
    allowed_inputs: tuple[str, ...]
    expected_tools: tuple[str, ...]
    requires_confirmation: bool = False
```

Registry:

```python
JUDGE_WORKFLOWS = {
    "transaction_lookup": JudgeWorkflow(
        id="transaction_lookup",
        label="Transaction lookup by invoice number",
        description="Reconcile a known invoice and show LedgerSoul's full lifecycle trace.",
        risk="read_only",
        allowed_inputs=("invoice_number",),
        expected_tools=("get_transaction_by_invoice_number", "write_audit_log"),
    ),
    "doku_payment_methods": JudgeWorkflow(
        id="doku_payment_methods",
        label="DOKU payment methods",
        description="Call the DOKU MCP sandbox read-only payment-methods tool.",
        risk="read_only",
        allowed_inputs=(),
        expected_tools=("call_doku_mcp_tool", "write_audit_log"),
    ),
}
```

Event builder:

```python
def build_event_for_workflow(workflow_id: str, inputs: dict[str, Any]) -> dict[str, Any]:
    workflow = JUDGE_WORKFLOWS[workflow_id]
    safe_inputs = {k: inputs[k] for k in workflow.allowed_inputs if k in inputs}
    event_id = f"judge_{workflow_id}_{uuid4().hex[:12]}"

    if workflow_id == "transaction_lookup":
        invoice = str(safe_inputs.get("invoice_number") or "INV-LEDGERSOUL-001")
        return {
            "event_id": event_id,
            "type": "transaction.lookup_requested",
            "amount": 20000,
            "currency": "IDR",
            "metadata": {"invoice_number": invoice, "source": "judge_mode"},
        }

    if workflow_id == "doku_payment_methods":
        return {
            "event_id": event_id,
            "type": "doku.payment_methods_requested",
            "metadata": {
                "source": "judge_mode",
                "doku_tool": "get_merchant_payment_methods",
                "tool_request": "List merchant payment methods available in DOKU sandbox.",
            },
        }

    raise ValueError(f"Unsupported judge workflow: {workflow_id}")
```

**Step 3: Verify**

Run:

```bash
. .venv/bin/activate && pytest tests/test_judge_workflows.py -q && ruff check .
```

Expected: pass.

---

## Task 5: Add Runtime Support for Read-Only DOKU Payment Methods Workflow

**Objective:** Let the judge workflow run through the real LedgerSoul runtime and explicit `TOOL_REGISTRY`, not around it.

**Files:**

- Modify: `src/ledgersoul/agent/planner.py`
- Modify: `src/ledgersoul/agent/executor.py`
- Modify: `src/ledgersoul/agent/verifier.py`
- Test: `tests/test_judge_doku_payment_methods_runtime.py`

**Step 1: Write failing runtime tests**

Create `tests/test_judge_doku_payment_methods_runtime.py`:

```python
from ledgersoul.agent.models import AgentEvent
from ledgersoul.agent.planner import create_plan


def test_doku_payment_methods_plans_read_only_tool(config):
    event = AgentEvent.model_validate({
        "event_id": "evt_doku_payment_methods",
        "type": "doku.payment_methods_requested",
        "metadata": {
            "doku_tool": "get_merchant_payment_methods",
            "tool_request": "List merchant payment methods available in DOKU sandbox.",
        },
    })

    plan = create_plan(event, config)

    assert plan.event_classification == "doku_payment_methods_requested"
    assert plan.risk_level == "low"
    assert plan.requires_human is False
    assert [step.tool for step in plan.steps] == ["call_doku_mcp_tool", "write_audit_log"]
```

For executor/verifier, avoid live DOKU in normal tests. Monkeypatch the registered tool or the executor safe path so no network call occurs. Preferred: monkeypatch `ledgersoul.agent.executor.get_tool` for this test.

```python
def test_doku_payment_methods_runtime_uses_registry_and_verifies(runtime, monkeypatch):
    calls = []

    def fake_get_tool(name):
        calls.append(name)
        if name == "call_doku_mcp_tool":
            return lambda **kwargs: {"result": {"content": [{"type": "text", "text": "VIRTUAL_ACCOUNT"}]}}
        if name == "write_audit_log":
            return lambda **kwargs: {"audit_written": True}
        raise AssertionError(name)

    monkeypatch.setattr("ledgersoul.agent.executor.get_tool", fake_get_tool)

    result = runtime.run({
        "event_id": "evt_doku_payment_methods",
        "type": "doku.payment_methods_requested",
        "metadata": {
            "doku_tool": "get_merchant_payment_methods",
            "tool_request": "List merchant payment methods available in DOKU sandbox.",
        },
    })

    assert result.status == "completed"
    assert result.verification.ok is True
    assert result.verification.reason == "doku_payment_methods_verified"
    assert calls == ["call_doku_mcp_tool", "write_audit_log"]
```

**Step 2: Update planner**

Add classification:

```python
"doku.payment_methods_requested": "doku_payment_methods_requested",
```

Risk:

```python
if classification == "doku_payment_methods_requested":
    return "low"
```

Plan:

```python
if classification == "doku_payment_methods_requested":
    return AgentPlan(
        goal="List DOKU sandbox payment methods",
        event_classification=classification,
        risk_level=risk,
        requires_human=False,
        steps=[
            PlanStep(
                name="call_doku_mcp_tool",
                tool="call_doku_mcp_tool",
                reason="Call the allowlisted DOKU MCP read-only payment-methods tool",
            ),
            PlanStep(
                name="write_audit_log",
                tool="write_audit_log",
                reason="Persist the DOKU payment-methods lookup result",
            ),
        ],
    )
```

**Step 3: Update executor**

Add branch before record-only fallback:

```python
if plan.event_classification == "doku_payment_methods_requested":
    doku = _safe_call(
        "call_doku_mcp_tool",
        config=config,
        tool_name="get_merchant_payment_methods",
        tool_request="List merchant payment methods available in DOKU sandbox.",
    )
    results.append(doku)
    results.append(
        _safe_call(
            "write_audit_log",
            memory=memory,
            event=event,
            action="doku_payment_methods_listed",
            result={"doku_payment_methods": doku.result},
        )
    )
    return results
```

Important: do not accept `tool_name` from judge/user input. Hardcode the allowlisted remote tool in the executor branch.

**Step 4: Update verifier**

Add verification rule:

```python
if plan.event_classification == "doku_payment_methods_requested":
    doku_result = next((r for r in tool_results if r.tool == "call_doku_mcp_tool"), None)
    audit = next((r for r in tool_results if r.tool == "write_audit_log"), None)
    if not doku_result or not doku_result.ok:
        return VerificationResult(ok=False, reason="doku_payment_methods_missing", evidence={})
    if not audit or not audit.ok:
        return VerificationResult(ok=False, reason="audit_log_missing", evidence={})
    return VerificationResult(
        ok=True,
        reason="doku_payment_methods_verified",
        evidence={"tool": "get_merchant_payment_methods"},
    )
```

**Step 5: Verify**

Run:

```bash
. .venv/bin/activate && pytest tests/test_judge_doku_payment_methods_runtime.py -q && ruff check .
```

Expected: pass.

---

## Task 6: Add Judge API Router

**Objective:** Add token-protected workflow endpoints under `/judge/*` that run only the tiny workflow registry.

**Files:**

- Create: `src/ledgersoul/server/judge.py`
- Modify: `src/ledgersoul/server/api.py`
- Test: `tests/test_judge_api.py`

**Step 1: Write failing API tests**

Create `tests/test_judge_api.py`:

```python
from fastapi.testclient import TestClient

from ledgersoul.server.api import create_app


def test_judge_workflows_requires_token(judge_config):
    client = TestClient(create_app(judge_config))

    assert client.get("/judge/workflows").status_code == 401
    assert client.get("/judge/workflows", headers={"Authorization": "Bearer judge-token"}).status_code == 200


def test_judge_run_transaction_lookup(judge_config):
    client = TestClient(create_app(judge_config))

    response = client.post(
        "/judge/runs",
        headers={"Authorization": "Bearer judge-token"},
        json={"workflow": "transaction_lookup", "inputs": {"invoice_number": "INV-LEDGERSOUL-001"}},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "completed"
    assert body["classification"] == "transaction_lookup_requested"
    assert body["tools_used"] == ["get_transaction_by_invoice_number", "write_audit_log"]
    assert body["verification"]["ok"] is True
    assert "trace_name" in body


def test_judge_rejects_unknown_workflow(judge_config):
    client = TestClient(create_app(judge_config))

    response = client.post(
        "/judge/runs",
        headers={"Authorization": "Bearer judge-token"},
        json={"workflow": "call_any_tool", "inputs": {"tool_name": "anything"}},
    )

    assert response.status_code == 400


def test_judge_trace_endpoint_returns_redacted_trace(judge_config):
    client = TestClient(create_app(judge_config))
    run = client.post(
        "/judge/runs",
        headers={"Authorization": "Bearer judge-token"},
        json={"workflow": "transaction_lookup", "inputs": {"invoice_number": "INV-LEDGERSOUL-001"}},
    ).json()

    trace = client.get(
        f"/judge/runs/{run['trace_name']}/trace",
        headers={"Authorization": "Bearer judge-token"},
    )

    assert trace.status_code == 200
    body = trace.json()
    assert body["status"] == "completed"
    assert "redacted_trace" in body
```

Add `judge_config` fixture to `tests/conftest.py` with isolated `tmp_path` and `judge_demo_token="judge-token"`.

**Step 2: Define schemas**

In `src/ledgersoul/server/judge.py`:

```python
class JudgeRunRequest(BaseModel):
    workflow: str
    inputs: dict[str, Any] = Field(default_factory=dict)
    confirmation: str | None = None
```

**Step 3: Define router factory**

Use a router factory so tests can inject runtime/config:

```python
def create_judge_router(config: AgentConfig, runtime: AgentRuntime) -> APIRouter:
    router = APIRouter(prefix="/judge", tags=["judge"])

    @router.get("", response_class=HTMLResponse)
    def judge_page():
        return HTMLResponse(_load_judge_html())

    @router.get("/workflows")
    def workflows(authorization: str | None = Header(default=None)):
        require_judge_token(authorization, config)
        return {"workflows": [serialize workflow metadata only]}

    @router.post("/runs")
    def run_judge_workflow(request: JudgeRunRequest, authorization: str | None = Header(default=None)):
        require_judge_token(authorization, config)
        workflow = JUDGE_WORKFLOWS.get(request.workflow)
        if not workflow:
            raise HTTPException(status_code=400, detail="Unknown judge workflow")
        if workflow.risk == "sandbox_write":
            if not config.judge_allow_sandbox_writes or request.confirmation != "CREATE_SANDBOX_OBJECT":
                raise HTTPException(status_code=403, detail="Sandbox-write workflow is disabled or unconfirmed")
        event = build_event_for_workflow(request.workflow, request.inputs)
        result = runtime.run(event)
        trace = _load_trace(result.trace_path)
        summary = summarize_trace(trace)
        summary["event_id"] = result.event_id
        summary["trace_name"] = os.path.basename(result.trace_path) if result.trace_path else None
        return summary

    @router.get("/runs/{trace_name}/trace")
    def read_judge_trace(trace_name: str, authorization: str | None = Header(default=None)):
        require_judge_token(authorization, config)
        # reject '/', '..', non-json names
        # load only from config.trace_dir
        return summarize_trace(trace)

    return router
```

**Step 4: Register router**

In `create_app()`:

```python
from ledgersoul.server.judge import create_judge_router

app.include_router(create_judge_router(config, runtime))
```

**Step 5: Verify**

Run:

```bash
. .venv/bin/activate && pytest tests/test_judge_api.py tests/test_judge_route_guard.py -q && ruff check .
```

Expected: pass.

---

## Task 7: Add Vanilla Judge UI

**Objective:** Provide a clean browser interface where judges can run allowlisted workflows and inspect lifecycle traces.

**Files:**

- Create: `src/ledgersoul/server/static/judge.html`
- Modify: `src/ledgersoul/server/judge.py`
- Test: `tests/test_judge_ui.py`

**Step 1: Write failing UI smoke test**

Create `tests/test_judge_ui.py`:

```python
from fastapi.testclient import TestClient

from ledgersoul.server.api import create_app


def test_judge_page_contains_no_prompt_or_command_interface(judge_config):
    client = TestClient(create_app(judge_config))

    response = client.get("/judge")

    assert response.status_code == 200
    html = response.text
    assert "LedgerSoul Judge Demo" in html
    assert "Run Transaction Lookup" in html
    assert "Run DOKU Payment Methods" in html
    assert "textarea" not in html.lower()
    assert "shell" not in html.lower()
    assert "command" not in html.lower()
```

**Step 2: Build HTML page**

The UI should include:

- Token input stored only in browser memory/localStorage.
- Agent proof cards:
  - `Agent profile loaded`
  - `agent.md loaded`
  - `DOKU mode: sandbox`
  - `Tool execution: explicit registry only`
- Buttons:
  - `Run Transaction Lookup`
  - `Run DOKU Payment Methods`
- Result panels:
  - status
  - classification
  - risk
  - tools used
  - verification reason
- Timeline list.
- Redacted trace JSON viewer.

Do **not** include:

- free-form prompt textarea
- arbitrary JSON event editor
- arbitrary tool-name input
- terminal/command wording
- server logs

**Step 3: Minimal JS behavior**

Use only fixed API calls:

```javascript
async function runWorkflow(workflow, inputs = {}) {
  const token = document.getElementById("token").value;
  const response = await fetch("/judge/runs", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "Authorization": `Bearer ${token}`,
    },
    body: JSON.stringify({ workflow, inputs }),
  });
  const body = await response.json();
  renderResult(body);
}
```

For transaction lookup, the only editable field should be invoice number, defaulted to:

```text
INV-LEDGERSOUL-001
```

For DOKU payment methods, no user input should be accepted.

**Step 4: Verify**

Run:

```bash
. .venv/bin/activate && pytest tests/test_judge_ui.py -q && ruff check .
```

Expected: pass.

---

## Task 8: Optional Sandbox Payment Link Workflow

**Objective:** Add a sandbox-write workflow only if the demo needs to show payment-link creation. Keep it disabled by default.

**Files:**

- Modify: `src/ledgersoul/judge/workflows.py`
- Modify: `src/ledgersoul/agent/planner.py`
- Modify: `src/ledgersoul/agent/executor.py`
- Modify: `src/ledgersoul/agent/verifier.py`
- Modify: `src/ledgersoul/server/static/judge.html`
- Test: `tests/test_judge_sandbox_write_guard.py`

**Rules:**

- `JUDGE_ALLOW_SANDBOX_WRITES=false` by default.
- API returns `403` unless enabled and confirmation string is present.
- UI requires checkbox text:

```text
I understand this creates a DOKU sandbox object.
```

- Never run this workflow in normal tests with live DOKU credentials.
- Unit tests must monkeypatch the DOKU tool call.

**Acceptance Criteria:**

- Without env enablement: request returns `403`.
- With env enablement but no confirmation: request returns `403`.
- With env enablement and confirmation: runtime uses only:
  - `call_doku_mcp_tool`
  - `write_audit_log`
- Verification failure maps to `failed_verification`.

---

## Task 9: Update Documentation for Demo Handoff

**Objective:** Give judges and hackathon organizers a clear “how to test” path without exposing operations.

**Files:**

- Modify: `README.md`
- Modify: `demo.md`
- Modify: `deploy.md`
- Modify: `guardrails.md`
- Modify: `evals.md`
- Modify: `tools.md`

**Add to `demo.md`:**

```markdown
## Judge Mode Demo

Judge Mode exposes only `/judge` and token-protected `/judge/*` endpoints.
It does not expose shell access, arbitrary agent prompts, arbitrary tool calls, raw traces, state, or FastAPI docs.

Recommended judge flow:
1. Open the public `/judge` URL.
2. Enter the provided demo token.
3. Click **Run Transaction Lookup**.
4. Inspect status, tools, verification, and trace timeline.
5. Click **Run DOKU Payment Methods** to run the read-only DOKU MCP workflow.
```

**Add to `deploy.md`:**

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

Document deployment options:

- Cloudflare Tunnel or ngrok for fast hackathon demos.
- Render/Railway/Fly.io for hosted public demos.
- Reverse proxy must expose only the app HTTP port, not SSH or any local admin ports.

**Add to `guardrails.md`:**

- Judge Mode route guard.
- Token auth.
- Workflow allowlist.
- Redaction.
- Sandbox-only DOKU mode.
- No free-form prompt or command execution.

**Add to `evals.md`:**

- Judge Mode Eval 1: unauthenticated `/judge/workflows` rejected.
- Judge Mode Eval 2: `/agent/run` hidden in judge mode.
- Judge Mode Eval 3: transaction lookup completes and trace is redacted.
- Judge Mode Eval 4: DOKU payment methods uses only allowlisted MCP tool.

---

## Task 10: End-to-End Verification Script and Demo Smoke Test

**Objective:** Prove Judge Mode works from the same interface a judge will use.

**Files:**

- Create: `scripts/smoke_judge_mode.py`
- Test: `tests/test_smoke_judge_mode_script.py` if time allows

**Script behavior:**

- Reads `JUDGE_DEMO_TOKEN` from env.
- Calls `/health`.
- Calls `/judge/workflows` with token.
- Runs `transaction_lookup`.
- Optionally runs `doku_payment_methods` only if `--live-doku` is passed.
- Prints a safe summary only.
- Never prints secrets.

**Command:**

```bash
. .venv/bin/activate && python scripts/smoke_judge_mode.py --base-url http://127.0.0.1:8000
```

**Expected safe output:**

```text
health: ok
workflows: transaction_lookup, doku_payment_methods
transaction_lookup: completed, verification=transaction_lookup_verified
trace: redacted=true
```

Do not make live DOKU calls in default smoke tests.

---

## Task 11: Final Full Verification

**Objective:** Confirm the implementation is judge-ready.

Run from `/home/ubuntu/ledgersoul`:

```bash
. .venv/bin/activate && pytest -q && ruff check .
```

Expected:

```text
passed
All checks passed!
```

Then run local Judge Mode smoke:

```bash
JUDGE_MODE=true \
JUDGE_DEMO_TOKEN=judge-local-token \
JUDGE_ALLOW_SANDBOX_WRITES=false \
. .venv/bin/activate && uvicorn ledgersoul.server.api:app --host 127.0.0.1 --port 8000
```

In a second terminal/session:

```bash
curl -s http://127.0.0.1:8000/health
curl -s http://127.0.0.1:8000/agent/run
curl -s -H 'Authorization: Bearer judge-local-token' http://127.0.0.1:8000/judge/workflows
curl -s -X POST http://127.0.0.1:8000/judge/runs \
  -H 'Authorization: Bearer judge-local-token' \
  -H 'Content-Type: application/json' \
  -d '{"workflow":"transaction_lookup","inputs":{"invoice_number":"INV-LEDGERSOUL-001"}}'
```

Expected:

- `/health`: `200`
- `/agent/run` in judge mode: `404`
- `/judge/workflows` with token: `200`
- transaction lookup run: `status=completed`, `verification.ok=true`, no secrets

For live DOKU read-only smoke, only run after confirming local sandbox env is configured:

```bash
curl -s -X POST http://127.0.0.1:8000/judge/runs \
  -H 'Authorization: Bearer judge-local-token' \
  -H 'Content-Type: application/json' \
  -d '{"workflow":"doku_payment_methods","inputs":{}}'
```

Expected:

- Uses only `call_doku_mcp_tool` and `write_audit_log`.
- Status is `completed` if DOKU sandbox responds.
- Status is `failed_verification` or `error` if DOKU sandbox/network/config fails.
- No secrets appear in response or trace viewer.

---

## Deployment Plan

### Fastest Hackathon Deployment

1. Run LedgerSoul locally/VM with:

```bash
JUDGE_MODE=true
JUDGE_DEMO_TOKEN=<random-demo-token>
JUDGE_ALLOW_SANDBOX_WRITES=false
PAYMENT_PROVIDER=doku
PAYMENT_API_MODE=sandbox
DOKU_MCP_URL=https://api-sandbox.doku.com/doku-mcp-server/mcp
DOKU_CLIENT_ID=[REDACTED]
DOKU_API_KEY=[REDACTED]
```

2. Start FastAPI:

```bash
. .venv/bin/activate && uvicorn ledgersoul.server.api:app --host 127.0.0.1 --port 8000
```

3. Expose only HTTP with Cloudflare Tunnel or ngrok:

```bash
cloudflared tunnel --url http://127.0.0.1:8000
```

or:

```bash
ngrok http 8000
```

4. Give judges:

- public `/judge` URL
- demo token only

Do **not** give:

- SSH access
- terminal access
- Hermes/Telegram access
- DOKU credentials
- server admin URLs

### Hosted Deployment

Use Render/Railway/Fly.io/Cloud Run with environment variables. Keep `JUDGE_MODE=true`, `JUDGE_ALLOW_SANDBOX_WRITES=false` unless explicitly demoing sandbox object creation.

---

## Acceptance Criteria

Judge Mode is complete when:

- `GET /judge` loads a browser demo page.
- Judge can run `transaction_lookup` from the page.
- Judge can run `doku_payment_methods` from the page when DOKU sandbox env is configured.
- Judge sees:
  - status
  - classification
  - risk
  - tools used
  - verification reason
  - timeline
  - redacted trace
- `agent.md` loaded status is visible in the trace/timeline.
- All runtime tool execution still goes through `TOOL_REGISTRY`.
- `/agent/run`, `/state`, `/traces`, `/doku/mcp/tools`, `/docs`, `/redoc`, and `/openapi.json` are unavailable in `JUDGE_MODE=true`.
- Unknown workflows are rejected.
- Sandbox-write workflows are disabled by default.
- No secrets appear in API responses, HTML, trace viewer, tests, docs, or summaries.
- `pytest -q` passes.
- `ruff check .` passes.

## Risks and Tradeoffs

- **Live DOKU network dependency:** DOKU payment methods can fail if sandbox/network is down. Mitigation: keep deterministic transaction lookup as the primary judging workflow and label live DOKU as sandbox read-only.
- **Global FastAPI app refactor:** Moving to `create_app()` touches route registration. Mitigation: keep `app = create_app()` for backwards compatibility and test existing profile/runtime endpoints.
- **Trace redaction gaps:** New DOKU responses may include unexpected fields. Mitigation: redact recursively by sensitive key names and token-like values.
- **Public endpoint leakage:** Existing endpoints are useful locally but unsafe publicly. Mitigation: middleware blocks all non-judge prefixes when `JUDGE_MODE=true`.
- **Sandbox-write demo:** Creating a payment link may be compelling but adds risk/noise. Mitigation: ship disabled by default; require explicit env + confirmation.

## Open Questions

1. Should the public demo include the optional `sandbox_payment_link` workflow, or keep the hackathon demo read-only?
2. Should the demo token be shared with all judges, or should each judge get a separate token?
3. Should transaction lookup use deterministic mock data only, or should a separate optional workflow call DOKU MCP `get_transaction_by_invoice_number` live when a known sandbox invoice exists?

Recommendation for fast hackathon build: ship read-only workflows only first, then add sandbox payment link only if judges specifically ask to create a payment object.
