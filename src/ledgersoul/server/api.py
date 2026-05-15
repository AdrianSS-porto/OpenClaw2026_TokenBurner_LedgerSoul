"""FastAPI service for LedgerSoul."""

from __future__ import annotations

import json
import os
import re
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from ledgersoul.agent.config import AgentConfig, load_config
from ledgersoul.agent.profile import load_agent_profile
from ledgersoul.agent.runtime import AgentRuntime
from ledgersoul.server.judge import create_judge_router
from ledgersoul.tools.doku_mcp import doku_mcp_config_status, list_doku_mcp_tools

JUDGE_ALLOWED_PREFIXES = ("/judge", "/health")


def _first_present(*values: Any) -> Any:
    for value in values:
        if value not in (None, ""):
            return value
    return None


def _safe_event_token(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_-]+", "_", value).strip("_")[:80] or "unknown"


def doku_webhook_to_agent_event(payload: dict[str, Any]) -> dict[str, Any]:
    """Convert a DOKU notification into a LedgerSoul transaction check event.

    DOKU payloads vary by product. The hook intentionally extracts only stable
    reconciliation fields, then lets the agent check DOKU for the current state.
    """
    order = payload.get("order") if isinstance(payload.get("order"), dict) else {}
    transaction = payload.get("transaction") if isinstance(payload.get("transaction"), dict) else {}
    customer = payload.get("customer") if isinstance(payload.get("customer"), dict) else {}
    va_data = payload.get("virtualAccountData") if isinstance(payload.get("virtualAccountData"), dict) else {}

    invoice_number = _first_present(
        payload.get("invoice_number"),
        payload.get("invoiceNumber"),
        payload.get("trxId"),
        order.get("invoice_number"),
        order.get("invoiceNumber"),
        transaction.get("invoice_number"),
        transaction.get("invoiceNumber"),
        va_data.get("trxId"),
    )
    if not invoice_number:
        raise ValueError("DOKU webhook payload missing invoice number")

    status = str(_first_present(payload.get("status"), transaction.get("status"), payload.get("transactionStatus"), "received"))
    amount = _first_present(payload.get("amount"), order.get("amount"), transaction.get("amount"))
    try:
        amount_int = int(float(amount)) if amount is not None else None
    except (TypeError, ValueError):
        amount_int = None

    invoice = str(invoice_number)
    return {
        "event_id": f"doku_hook_{_safe_event_token(invoice)}_{_safe_event_token(status)}",
        "type": "transaction.lookup_requested",
        "amount": amount_int,
        "currency": str(_first_present(payload.get("currency"), order.get("currency"), "IDR")),
        "reason": "doku_webhook_received",
        "metadata": {
            "source": "doku_webhook",
            "provider": "doku",
            "invoice_number": invoice,
            "webhook_status": status,
            "customer_name": _first_present(customer.get("name"), payload.get("customer_name")),
        },
    }


def create_app(config: AgentConfig | None = None) -> FastAPI:
    """Create the FastAPI app, optionally locked down for judge-mode demos."""
    active_config = config or load_config()
    runtime = AgentRuntime(active_config)
    app = FastAPI(
        title="LedgerSoul",
        version="0.1.0",
        docs_url=None if active_config.judge_mode else "/docs",
        redoc_url=None if active_config.judge_mode else "/redoc",
        openapi_url=None if active_config.judge_mode else "/openapi.json",
    )

    @app.middleware("http")
    async def judge_mode_guard(request: Request, call_next):  # type: ignore[no-untyped-def]
        if active_config.judge_mode:
            path = request.url.path
            if not path.startswith(JUDGE_ALLOWED_PREFIXES):
                return JSONResponse({"detail": "not found"}, status_code=404)
        return await call_next(request)

    @app.get("/health")
    def health() -> dict[str, Any]:
        return {"ok": True, "service": "ledgersoul", "mode": active_config.agent_mode}

    @app.get("/agent/profile")
    def agent_profile(include_content: bool = True) -> dict[str, Any]:
        """Expose the loaded markdown contract used to define LedgerSoul."""
        return load_agent_profile(include_content=include_content)

    @app.get("/doku/mcp/status")
    def doku_mcp_status() -> dict[str, Any]:
        """Return redacted DOKU MCP configuration status without making a network call."""
        return doku_mcp_config_status(active_config)

    @app.get("/doku/mcp/tools")
    def doku_mcp_tools(live: bool = False) -> dict[str, Any]:
        """List DOKU MCP tools when live=true; otherwise return safe config status only."""
        status = doku_mcp_config_status(active_config)
        if not live:
            return {
                **status,
                "live": False,
                "note": "Pass ?live=true to initialize DOKU MCP and list remote tools.",
            }
        try:
            return {**status, "live": True, **list_doku_mcp_tools(active_config)}
        except Exception as exc:
            raise HTTPException(status_code=502, detail=f"DOKU MCP connection failed: {exc}") from exc

    @app.post("/agent/run")
    def run_agent(event: dict[str, Any]) -> JSONResponse:
        if not isinstance(event, dict):
            raise HTTPException(status_code=400, detail="event must be a JSON object")
        result = runtime.run(event)
        return JSONResponse(result.model_dump())

    @app.post("/webhooks/payment")
    def webhook_payment(event: dict[str, Any]) -> JSONResponse:
        if not isinstance(event, dict):
            raise HTTPException(status_code=400, detail="event must be a JSON object")
        result = runtime.run(event)
        return JSONResponse(result.model_dump())

    @app.post("/webhooks/doku")
    def webhook_doku(payload: dict[str, Any]) -> JSONResponse:
        if not isinstance(payload, dict):
            raise HTTPException(status_code=400, detail="payload must be a JSON object")
        try:
            event = doku_webhook_to_agent_event(payload)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        result = runtime.run(event)
        return JSONResponse(result.model_dump())

    @app.get("/state")
    def state_summary() -> dict[str, Any]:
        return runtime.memory.get_state_summary()

    @app.get("/traces")
    def list_traces(limit: int = 50) -> dict[str, Any]:
        trace_dir = active_config.trace_dir
        if not os.path.isdir(trace_dir):
            return {"traces": []}
        files = []
        for name in sorted(os.listdir(trace_dir)):
            if not name.endswith(".json"):
                continue
            path = os.path.join(trace_dir, name)
            try:
                stat = os.stat(path)
                files.append({"name": name, "path": path, "size": stat.st_size, "mtime": stat.st_mtime})
            except OSError:
                continue
        files.sort(key=lambda x: x["mtime"], reverse=True)
        return {"traces": files[:limit]}

    @app.get("/traces/{name}")
    def read_trace(name: str) -> JSONResponse:
        if "/" in name or ".." in name:
            raise HTTPException(status_code=400, detail="invalid trace name")
        path = os.path.join(active_config.trace_dir, name)
        if not os.path.exists(path):
            raise HTTPException(status_code=404, detail="trace not found")
        with open(path, "r", encoding="utf-8") as f:
            return JSONResponse(json.load(f))

    app.include_router(create_judge_router(active_config, runtime))
    return app


app = create_app()
