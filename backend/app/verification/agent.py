"""The Verification Agent's pure core (docs/AEGIS_IMPLEMENTATION_PLAN.md
Section 26).

``verify`` takes the fully-extracted ``VerificationInputs`` (the service does
every DB read and the workspace re-apply check) and runs the deterministic
pipeline: evaluate the seven criteria, build the plan-alignment breakdown,
aggregate an overall verdict + resulting state + confidence, and generate the
explainability trace. No AI, no I/O.
"""

from __future__ import annotations

from app.verification import criteria as criteria_mod
from app.verification._criterion import VerificationComputation, VerificationInputs
from app.verification.aggregate import aggregate
from app.verification.alignment import plan_alignment
from app.verification.trace import build_trace


def verify(inp: VerificationInputs) -> VerificationComputation:
    outcomes = criteria_mod.evaluate_all(inp)
    alignment = plan_alignment(inp)
    verdict, resulting_state, confidence = aggregate(outcomes)
    trace = build_trace(inp, outcomes)
    return VerificationComputation(
        criteria=outcomes,
        alignment=alignment.model_dump(),
        trace=trace.model_dump(),
        verdict=verdict,
        resulting_state=resulting_state,
        confidence=confidence.model_dump(),
    )
