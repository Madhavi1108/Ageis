"""Aggregate the per-criterion outcomes into an overall verdict, the resulting
task state, and a confidence label (docs/AEGIS_IMPLEMENTATION_PLAN.md
Section 26, step 3).

* any mandatory ``FAIL``                    -> ``NOT_VERIFIED`` -> ``FAILED``
* all mandatory ``PASS`` + score gate ``PASS`` -> ``VERIFIED``   -> ``COMPLETED``
* all mandatory ``PASS`` but a mandatory ``UNKNOWN`` or the score gate not
  ``PASS``                                 -> ``PARTIAL``     -> ``AWAITING_APPROVAL``

``VERIFIED`` requires every mandatory criterion to pass -- code being generated
is never sufficient.
"""

from __future__ import annotations

from aegis.schemas.common import Confidence

from app.models.task import TaskState
from app.verification._criterion import CriterionOutcome


def aggregate(criteria: list[CriterionOutcome]) -> tuple[str, str, Confidence]:
    mandatory = [c for c in criteria if c.mandatory]
    advisory = [c for c in criteria if not c.mandatory]

    if any(c.verdict == "FAIL" for c in mandatory):
        return (
            "NOT_VERIFIED",
            TaskState.FAILED.value,
            Confidence(value=1.0, basis="FACT"),
        )

    mandatory_unknown = [c for c in mandatory if c.verdict == "UNKNOWN"]
    gate_not_pass = [c for c in advisory if c.verdict != "PASS"]
    if mandatory_unknown or gate_not_pass:
        return (
            "PARTIAL",
            TaskState.AWAITING_APPROVAL.value,
            Confidence(value=0.5, basis="INFERENCE"),
        )

    return (
        "VERIFIED",
        TaskState.COMPLETED.value,
        Confidence(value=1.0, basis="FACT"),
    )


def failed_criteria_names(criteria: list[CriterionOutcome]) -> list[str]:
    return [c.name for c in criteria if c.verdict == "FAIL"]
