"""Judge-mode FastAPI routes."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Header, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from ledgersoul.agent.config import AgentConfig
from ledgersoul.agent.runtime import AgentRuntime
from ledgersoul.judge.security import require_judge_token
from ledgersoul.judge.trace_view import summarize_trace
from ledgersoul.judge.workflows import JUDGE_WORKFLOWS, build_event_for_workflow


class JudgeRunRequest(BaseModel):
    workflow: str
    inputs: dict[str, Any] = Field(default_factory=dict)
    confirmation: str | None = None


def _load_judge_html() -> str:
    path = Path(__file__).parent / "static" / "judge.html"
    return path.read_text(encoding="utf-8")


def _trace_name_from_path(trace_path: str | None) -> str | None:
    if not trace_path:
        return None
    return os.path.basename(trace_path)


def _load_trace(trace_path: str | None) -> dict[str, Any]:
    if not trace_path:
        raise HTTPException(status_code=500, detail="Trace was not written")
    with open(trace_path, "r", encoding="utf-8") as f:
        return json.load(f)


def _safe_trace_path(trace_dir: str, trace_name: str) -> str:
    if "/" in trace_name or ".." in trace_name or not trace_name.endswith(".json"):
        raise HTTPException(status_code=400, detail="Invalid trace name")
    path = os.path.abspath(os.path.join(trace_dir, trace_name))
    trace_root = os.path.abspath(trace_dir)
    if not path.startswith(trace_root + os.sep):
        raise HTTPException(status_code=400, detail="Invalid trace name")
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Trace not found")
    return path


def create_judge_router(config: AgentConfig, runtime: AgentRuntime) -> APIRouter:
    """Create token-protected judge demo routes."""
    router = APIRouter(prefix="/judge", tags=["judge"])

    @router.get("", response_class=HTMLResponse)
    def judge_page() -> HTMLResponse:
        return HTMLResponse(_load_judge_html())

    @router.get("/workflows")
    def workflows(authorization: str | None = Header(default=None)) -> dict[str, Any]:
        require_judge_token(authorization, config)
        return {
            "judge_mode": config.judge_mode,
            "workflows": [workflow.to_public_dict() for workflow in JUDGE_WORKFLOWS.values()],
        }

    @router.post("/runs")
    def run_judge_workflow(
        request: JudgeRunRequest,
        authorization: str | None = Header(default=None),
    ) -> dict[str, Any]:
        require_judge_token(authorization, config)
        workflow = JUDGE_WORKFLOWS.get(request.workflow)
        if workflow is None:
            raise HTTPException(status_code=400, detail="Unknown judge workflow")
        if workflow.risk == "sandbox_write":
            if not config.judge_allow_sandbox_writes or request.confirmation != "CREATE_SANDBOX_OBJECT":
                raise HTTPException(status_code=403, detail="Sandbox-write workflow is disabled or unconfirmed")

        try:
            event = build_event_for_workflow(request.workflow, request.inputs)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        result = runtime.run(event)
        trace = _load_trace(result.trace_path)
        summary = summarize_trace(trace)
        summary["event_id"] = result.event_id
        summary["trace_name"] = _trace_name_from_path(result.trace_path)
        return summary

    @router.get("/runs/{trace_name}/trace")
    def read_judge_trace(
        trace_name: str,
        authorization: str | None = Header(default=None),
    ) -> dict[str, Any]:
        require_judge_token(authorization, config)
        trace_path = _safe_trace_path(config.trace_dir, trace_name)
        trace = _load_trace(trace_path)
        summary = summarize_trace(trace)
        summary["trace_name"] = trace_name
        return summary

    return router
