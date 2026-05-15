"""AgentRuntime: orchestrates the full lifecycle for a single event."""

from __future__ import annotations

from typing import Any

from pydantic import ValidationError

from ledgersoul.agent.config import AgentConfig
from ledgersoul.agent.executor import execute_plan
from ledgersoul.agent.memory import AgentMemory
from ledgersoul.agent.models import (
    AgentEvent,
    AgentPlan,
    AgentRunResult,
    PlanStep,
    RunStatus,
    ToolResult,
    VerificationResult,
)
from ledgersoul.agent.planner import create_plan, duplicate_plan
from ledgersoul.agent.policies import apply_policy
from ledgersoul.agent.profile import load_agent_profile
from ledgersoul.agent.reasoner import reason_about
from ledgersoul.agent.reflection import reflect
from ledgersoul.agent.trace import write_trace
from ledgersoul.agent.verifier import verify_run


def _empty_plan(reason: str) -> AgentPlan:
    return AgentPlan(
        goal="No-op",
        event_classification="error",
        risk_level="unknown",
        requires_human=False,
        steps=[PlanStep(name="error", tool=None, reason=reason)],
    )


class AgentRuntime:
    def __init__(self, config: AgentConfig) -> None:
        self.config = config
        self.memory = AgentMemory(config.state_dir)

    def run(self, event_data: dict[str, Any]) -> AgentRunResult:
        # 1. Validate
        try:
            event = AgentEvent.model_validate(event_data)
        except ValidationError as exc:
            return self._finalize_error(
                event_id=str(event_data.get("event_id", "unknown")),
                error_reason=f"validation_error:{exc.errors()[0].get('msg', 'invalid')}",
                raw_event=event_data,
            )

        try:
            # 2. Idempotency check
            if self.memory.is_processed(event.event_id):
                return self._run_duplicate(event)

            # 3. Reason (LLM Reasoning Agent — deterministic fallback)
            reasoning = reason_about(event, self.config)

            # 4. Plan (Planner Agent — deterministic source of truth)
            plan = create_plan(event, self.config)

            # 5. Apply policy
            plan = apply_policy(event, plan, self.config, self.memory)

            # 6. Execute
            tool_results = execute_plan(event, plan, self.config, self.memory)

            # 7. Verify
            verification = verify_run(event, plan, tool_results)

            # 8. Reflect
            reflection = reflect(event, plan, tool_results, verification)

            # 9. Status
            status = self._terminal_status(plan, verification)

            # 10. Memory + audit
            self.memory.append_memory({
                "event_id": event.event_id,
                "status": status,
                "classification": plan.event_classification,
            })

            # 11. Mark processed
            self.memory.mark_processed(event.event_id, status)

            # 12. Trace
            trace = self._build_trace(
                event, plan, tool_results, verification, reflection, status,
                reasoning=reasoning.to_dict(),
            )
            trace_path = write_trace(self.config.trace_dir, event.event_id, trace)

            return AgentRunResult(
                event_id=event.event_id,
                status=status,
                plan=plan,
                tool_results=tool_results,
                verification=verification,
                reflection=reflection,
                trace_path=trace_path,
            )
        except Exception as exc:  # pragma: no cover - defensive
            return self._finalize_error(
                event_id=event.event_id,
                error_reason=f"runtime_exception:{type(exc).__name__}:{exc}",
                raw_event=event_data,
            )

    # ---- helpers ----

    def _run_duplicate(self, event: AgentEvent) -> AgentRunResult:
        plan = duplicate_plan(event)
        tool_results = execute_plan(event, plan, self.config, self.memory)
        verification = verify_run(event, plan, tool_results)
        reflection = reflect(event, plan, tool_results, verification)
        status: RunStatus = "duplicate" if verification.ok else "failed_verification"

        # Append memory but DO NOT re-mark processed (it already is).
        self.memory.append_memory({
            "event_id": event.event_id,
            "status": status,
            "classification": "duplicate_event",
        })

        trace = self._build_trace(event, plan, tool_results, verification, reflection, status)
        trace_path = write_trace(self.config.trace_dir, event.event_id, trace)

        return AgentRunResult(
            event_id=event.event_id,
            status=status,
            plan=plan,
            tool_results=tool_results,
            verification=verification,
            reflection=reflection,
            trace_path=trace_path,
        )

    def _terminal_status(self, plan: AgentPlan, verification: VerificationResult) -> RunStatus:
        if not verification.ok:
            return "failed_verification"
        if plan.requires_human:
            return "escalated"
        if plan.event_classification == "duplicate_event":
            return "duplicate"
        return "completed"

    def _build_trace(
        self,
        event: AgentEvent,
        plan: AgentPlan,
        tool_results: list[ToolResult],
        verification: VerificationResult,
        reflection: dict[str, Any],
        status: RunStatus,
        reasoning: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        trace = {
            "status": status,
            "agent_profile": load_agent_profile(include_content=False),
            "event": event.model_dump(),
            "plan": plan.model_dump(),
            "tool_results": [r.model_dump() for r in tool_results],
            "verification": verification.model_dump(),
            "reflection": reflection,
        }
        if reasoning is not None:
            trace["reasoning"] = reasoning
        return trace

    def _finalize_error(
        self,
        event_id: str,
        error_reason: str,
        raw_event: dict[str, Any],
    ) -> AgentRunResult:
        plan = _empty_plan(error_reason)
        verification = VerificationResult(ok=False, reason=error_reason, evidence={})
        reflection = {
            "event_id": event_id,
            "outcome": "error",
            "confidence": 0.0,
            "human_required": True,
            "summary": f"Runtime error: {error_reason}",
            "tools_used": [],
            "next_step": "Operator must inspect trace and raw event.",
        }
        # Best-effort audit + memory + trace; never raise.
        try:
            placeholder_event = AgentEvent(event_id=event_id, type="error")
            self.memory.append_audit({
                "event_id": event_id,
                "event_type": "error",
                "action": "runtime_error",
                "result": {"reason": error_reason, "raw_event": raw_event},
            })
            self.memory.append_memory({
                "event_id": event_id,
                "status": "error",
                "classification": "error",
            })
            self.memory.mark_processed(event_id, "error")
            trace = {
                "status": "error",
                "agent_profile": load_agent_profile(include_content=False),
                "event": placeholder_event.model_dump(),
                "raw_event": raw_event,
                "plan": plan.model_dump(),
                "tool_results": [],
                "verification": verification.model_dump(),
                "reflection": reflection,
            }
            trace_path = write_trace(self.config.trace_dir, event_id, trace)
        except Exception:  # pragma: no cover - defensive
            trace_path = None

        return AgentRunResult(
            event_id=event_id,
            status="error",
            plan=plan,
            tool_results=[],
            verification=verification,
            reflection=reflection,
            trace_path=trace_path,
        )
