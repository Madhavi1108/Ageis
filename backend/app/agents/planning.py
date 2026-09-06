"""Planning agent (docs/AI_AGENT_DESIGN.md Section 2, docs/AEGIS_IMPLEMENTATION_PLAN.md
Section 17).

Pure functions over already-loaded inputs -- the service (app/services/planning.py)
does the DB / provider wiring. Three pieces:

* ``propose_plan``      -- ask the configured provider to fill the EngineeringPlan
                           schema from the mapping + impact evidence.
* ``build_fallback_plan`` -- the deterministic rule-based plan used when no model
                           is configured (``source=RULE_BASED_FALLBACK``, LOW confidence).
* ``validate_plan``     -- the rules engine that blocks a bad plan before any code
                           is written.
"""

from __future__ import annotations

from typing import Any

from app.ai.provider import AIProvider
from app.ai.routing import tier_for
from app.schemas.plan import EngineeringPlanAI, PlanValidation

_PLANNING_TEMPLATE = "planning"


def _impact_summary(impact: dict) -> str:
    changed = impact.get("changed_set", {})
    callers = [
        c["ref"]
        for entry in impact.get("callers", [])
        for c in entry.get("callers", [])
    ]
    regions = [a["path"] for a in impact.get("regression_areas", [])]
    return (
        f"changed_files={changed.get('files', [])}; "
        f"changed_symbols={changed.get('symbols', [])}; "
        f"callers={sorted(set(callers))}; "
        f"regression_areas={regions}"
    )


def propose_plan(
    *,
    task_key: str,
    task_text: str,
    candidate_files: list[str],
    candidate_symbols: list[str],
    impact: dict,
    provider: AIProvider,
    timeout_s: float,
    max_tokens: int,
) -> EngineeringPlanAI:
    variables: dict[str, Any] = {
        "task_key": task_key,
        "task_text": task_text,
        "candidate_files": "\n".join(candidate_files) or "(none)",
        "candidate_symbols": "\n".join(candidate_symbols) or "(none)",
        "impact_summary": _impact_summary(impact),
        "memory_hits": "(none -- engineering memory lands in Phase 20)",
        # list forms for the MockProvider rule-based fallback (not templated)
        "candidate_files_list": candidate_files,
        "candidate_symbols_list": candidate_symbols,
    }
    result = provider.complete(
        template=_PLANNING_TEMPLATE,
        variables=variables,
        schema=EngineeringPlanAI,
        tier=tier_for("planning"),
        timeout_s=timeout_s,
        max_tokens=max_tokens,
    )
    assert isinstance(result, EngineeringPlanAI)
    return result


def build_fallback_plan(
    *, candidate_files: list[str], candidate_symbols: list[str]
) -> EngineeringPlanAI:
    target = candidate_files[0] if candidate_files else None
    return EngineeringPlanAI.model_validate(
        {
            "problem_interpretation": "UNKNOWN -- no engineering-planning model configured",
            "assumptions": [],
            "files_to_inspect": list(candidate_files),
            "files_to_modify": [target] if target else [],
            "symbols_to_modify": list(candidate_symbols),
            "dependencies": [],
            "steps": [
                {
                    "id": "s1",
                    "description": "best-effort automated fix at the top localisation candidate",
                    "test_intent": "re-run the task's existing failing tests and confirm they pass",
                    "evidence_refs": [],
                }
            ],
            "test_strategy": {"approach": "rely on the repository's existing tests"},
            "expected_behavior": "UNKNOWN",
            "regression_risks": ["no verified root cause; the fix may be ineffective"],
            "rollback_strategy": "revert the workspace to the original snapshot",
            "source": "RULE_BASED_FALLBACK",
            "confidence": {"value": 0.2, "basis": "UNKNOWN"},
            "evidence": [],
        }
    )


def validate_plan(
    plan: EngineeringPlanAI,
    *,
    snapshot_paths: set[str],
    allowed_scope: set[str],
) -> PlanValidation:
    """Verdict from six checks (docs/AI_AGENT_DESIGN.md Section 7 ``checked`` keys):

    * ``schema``              -- always True here (Pydantic already enforced it).
    * ``files_exist``         -- every referenced path is in the snapshot.
    * ``scope_subset``        -- ``files_to_modify`` ⊆ mapping ∪ impact ∪ allowlist.
    * ``steps_have_tests``    -- every step has a non-empty ``test_intent``.
    * ``rollback_present``    -- ``rollback_strategy`` is non-empty.
    * ``assumptions_nonempty``-- soft; recorded, never blocks.

    REJECTED on a hard failure (scope escape, empty modify-set, missing file);
    REVISE on a soft gap (step without a test intent, no rollback); else APPROVED.
    """
    reasons: list[str] = []
    checked: dict[str, bool] = {"schema": True}

    referenced = set(plan.files_to_inspect) | set(plan.files_to_modify)
    missing = sorted(p for p in referenced if p not in snapshot_paths)
    checked["files_exist"] = not missing
    if missing:
        reasons.append(f"referenced files not in the snapshot: {missing}")

    escapes = sorted(p for p in plan.files_to_modify if p not in allowed_scope)
    checked["scope_subset"] = not escapes
    if escapes:
        reasons.append(
            f"files_to_modify outside mapping/impact/allowlist scope: {escapes}"
        )

    empty_modify = not plan.files_to_modify
    if empty_modify:
        reasons.append("plan proposes no files to modify")

    steps_without_intent = [s.id for s in plan.steps if not s.test_intent.strip()]
    checked["steps_have_tests"] = not steps_without_intent
    if steps_without_intent:
        reasons.append(f"steps missing a test_intent: {steps_without_intent}")

    checked["rollback_present"] = bool(plan.rollback_strategy.strip())
    if not checked["rollback_present"]:
        reasons.append("no rollback_strategy provided")

    checked["assumptions_nonempty"] = bool(plan.assumptions)

    hard_fail = bool(missing) or bool(escapes) or empty_modify
    if hard_fail:
        verdict = "REJECTED"
    elif reasons:
        verdict = "REVISE"
    else:
        verdict = "APPROVED"

    return PlanValidation(verdict=verdict, reasons=reasons, checked=checked)
