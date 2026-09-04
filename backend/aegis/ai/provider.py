"""AIProvider abstraction. See docs/AI_AGENT_DESIGN.md Section 3,
docs/DECISIONS/ADR-0005, ADR-0019 (model routing -- not exercised at this
scale; Phase 1 makes one planning call and, if needed, up to two repair
calls, all at a single tier).

MockProvider is the default everywhere in this repository (deterministic, no
network, no spend). ClaudeProvider is real but gated behind RUN_LIVE_AI=1 and
an API key -- it is not exercised by this session (no key configured) but the
interface is genuine, not a stub with a different shape.
"""

from __future__ import annotations

import os
from typing import Any, Protocol

from pydantic import BaseModel

from aegis.ai.schema_guard import validate_with_repair


class AIProvider(Protocol):
    name: str

    def complete(
        self,
        *,
        template: str,
        variables: dict[str, Any],
        schema: type[BaseModel],
        tier: str = "frontier",
        timeout_s: float = 30.0,
        max_tokens: int = 2000,
        temperature: float = 0.0,
    ) -> BaseModel: ...


class MockProvider:
    """Deterministic, canned-by-(template, task_key) responses.

    When no canned entry exists, falls back to a generic low-confidence
    rule-based response (docs/AI_AGENT_DESIGN.md Section 3: "absence of a
    real provider still yields a working, lower-confidence pipeline"). This
    is the honest path exercised by the "unfixable" fixture -- it is not a
    special case, it is simply what happens when nothing was registered.
    """

    name = "mock"

    def __init__(self) -> None:
        self._responses: dict[tuple[str, str], dict[str, Any]] = {}

    def register(self, template: str, task_key: str, raw: dict[str, Any]) -> None:
        self._responses[(template, task_key)] = raw

    def complete(
        self,
        *,
        template: str,
        variables: dict[str, Any],
        schema: type[BaseModel],
        tier: str = "frontier",
        timeout_s: float = 30.0,
        max_tokens: int = 2000,
        temperature: float = 0.0,
    ) -> BaseModel:
        task_key = variables.get("task_key", "")
        raw = self._responses.get((template, task_key))
        if raw is None:
            raw = _fallback_response(template, variables)
        return validate_with_repair(raw, schema, repair_fn=None)


def _fallback_response(template: str, variables: dict[str, Any]) -> dict[str, Any]:
    if template == "planning":
        candidates: list[str] = variables.get("candidate_files", [])
        target = candidates[0] if candidates else None
        return {
            "problem_interpretation": "UNKNOWN -- no matching engineering knowledge available",
            "assumptions": [],
            "files_to_inspect": candidates,
            "files_to_modify": [target] if target else [],
            "symbols_to_modify": [],
            "dependencies": [],
            "steps": [
                {
                    "id": "s1",
                    "description": "attempt a best-effort automated fix; low confidence",
                    "test_intent": "re-run the existing failing tests",
                    "evidence_refs": [],
                }
            ],
            "test_strategy": {"approach": "rely on existing repository tests"},
            "expected_behavior": "UNKNOWN",
            "regression_risks": ["fix may be ineffective; no verified root cause"],
            "rollback_strategy": "revert the workspace to the original snapshot",
            "source": "RULE_BASED_FALLBACK",
            "confidence": {"value": 0.2, "basis": "UNKNOWN"},
            "evidence": [],
        }
    if template in ("implementation", "repair"):
        target = variables.get("target_file")
        anchor = variables.get("target_file_head", "")
        plan_step_id = variables.get("plan_step_id", "s1")
        if not target or not anchor:
            return {"edit_ops": []}
        return {
            "edit_ops": [
                {
                    "path": target,
                    "op": "insert",
                    "anchor": anchor,
                    "old": None,
                    "new": "# AEGIS: automated fix attempted (low confidence, unverified)\n",
                    "plan_step_id": plan_step_id,
                    "rationale": "rule-based fallback: no verified fix available for this issue",
                    "evidence": [],
                }
            ]
        }
    raise ValueError(f"MockProvider has no fallback for template {template!r}")


class ClaudeProvider:
    """A real provider, gated behind RUN_LIVE_AI=1 + ANTHROPIC_API_KEY. Not
    exercised in this session. See docs/COST_MODEL.md for the model tiers."""

    name = "claude"

    def __init__(self) -> None:
        if os.environ.get("RUN_LIVE_AI") != "1":
            raise RuntimeError(
                "ClaudeProvider requires RUN_LIVE_AI=1 (opt-in for live model calls)."
            )
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError("ClaudeProvider requires ANTHROPIC_API_KEY.")
        try:
            import anthropic  # type: ignore
        except ImportError as exc:
            raise RuntimeError(
                "ClaudeProvider requires the 'anthropic' package: pip install 'aegis[live-ai]'"
            ) from exc
        self._client = anthropic.Anthropic(api_key=api_key)

    def complete(
        self,
        *,
        template: str,
        variables: dict[str, Any],
        schema: type[BaseModel],
        tier: str = "frontier",
        timeout_s: float = 30.0,
        max_tokens: int = 2000,
        temperature: float = 0.0,
    ) -> BaseModel:
        from aegis.ai.prompts import render_planning_prompt

        if template != "planning":
            raise NotImplementedError(
                f"ClaudeProvider: template {template!r} not wired yet"
            )
        prompt = render_planning_prompt(
            task_text=variables.get("task_text", ""),
            candidates=variables.get("candidate_files", []),
        )
        import json

        resp = self._client.messages.create(
            model=os.environ.get("AEGIS_MODEL", "claude-sonnet-5"),
            max_tokens=max_tokens,
            temperature=temperature,
            messages=[{"role": "user", "content": prompt}],
        )
        text = "".join(block.text for block in resp.content if hasattr(block, "text"))
        raw = json.loads(text)
        return validate_with_repair(raw, schema, repair_fn=None)


def get_provider(name: str) -> AIProvider:
    if name == "mock":
        return MockProvider()
    if name == "claude":
        return ClaudeProvider()
    raise ValueError(f"unknown provider {name!r}")
