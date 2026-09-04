"""Planning Agent (reduced). See docs/AI_AGENT_DESIGN.md Section 2 and
docs/AEGIS_IMPLEMENTATION_PLAN.md Phase 9 (Engineering Planning + Plan
Validation). Phase 1 makes exactly one planning call -- no repair-round
re-planning beyond schema_guard's single repair round.
"""

from __future__ import annotations

from aegis.ai.provider import AIProvider
from aegis.repository.ingest import Snapshot
from aegis.schemas.plan import EngineeringPlan, PlanValidation


def propose_plan(
    *, task_key: str, task_text: str, candidate_files: list[str], provider: AIProvider
) -> EngineeringPlan:
    variables = {
        "task_key": task_key,
        "task_text": task_text,
        "candidate_files": candidate_files,
    }
    result = provider.complete(
        template="planning", variables=variables, schema=EngineeringPlan
    )
    assert isinstance(result, EngineeringPlan)  # provider.complete is schema-typed
    return result


def validate_plan(plan: EngineeringPlan, snapshot: Snapshot) -> PlanValidation:
    """Reduced plan validation: schema (already enforced), files exist in the
    snapshot, every step has a test intent, and a rollback strategy is
    present. Full validation (scope-subset against mapping/impact evidence)
    is Phase 9's complete version.
    """
    reasons: list[str] = []
    checked = {
        "files_exist": True,
        "steps_have_tests": True,
        "rollback_present": bool(plan.rollback_strategy.strip()),
        "assumptions_nonempty": True,  # allowed empty for a well-scoped fix; not a hard rule here
    }

    known_paths = {f.path for f in snapshot.files}
    missing = [p for p in plan.files_to_modify if p not in known_paths]
    if missing:
        checked["files_exist"] = False
        reasons.append(f"files_to_modify not in repository: {missing}")

    if not plan.files_to_modify:
        reasons.append("plan proposes no files to modify")

    steps_without_intent = [s.id for s in plan.steps if not s.test_intent.strip()]
    if steps_without_intent:
        checked["steps_have_tests"] = False
        reasons.append(f"steps missing a test_intent: {steps_without_intent}")

    if not checked["rollback_present"]:
        reasons.append("no rollback_strategy provided")

    if reasons:
        verdict = "REJECTED" if not plan.files_to_modify else "REVISE"
    else:
        verdict = "APPROVED"

    return PlanValidation(verdict=verdict, reasons=reasons, checked=checked)
