"""Plan-vs-implementation alignment breakdown
(docs/AEGIS_IMPLEMENTATION_PLAN.md Section 26, step 2).

Ports the ``plan_alignment`` dict the walking-skeleton
``aegis/verification/agent.py`` produced, expanded to the
``docs/DATA_MODEL.md`` Section 2.4 shape: which steps were implemented, and
which touched files fell outside the plan's declared scope.
"""

from __future__ import annotations

from app.schemas.verification import PlanAlignment
from app.verification._criterion import VerificationInputs


def plan_alignment(inp: VerificationInputs) -> PlanAlignment:
    step_ids = [s["id"] for s in inp.plan_steps if s.get("id")]
    implemented = {sid for sid, paths in (inp.traceability or {}).items() if paths}
    unimplemented = sorted(sid for sid in step_ids if sid not in implemented)
    unplanned = sorted(set(inp.touched_files) - set(inp.allowed_scope))
    return PlanAlignment(
        steps_total=len(step_ids),
        steps_implemented=len(step_ids) - len(unimplemented),
        unimplemented_steps=unimplemented,
        unplanned_files=unplanned,
        files_touched=sorted(inp.touched_files),
    )
