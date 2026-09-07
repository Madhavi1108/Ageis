"""Internal value objects for the verification layer.

``CriterionOutcome`` is what each evaluator in ``criteria.py`` returns before
projection into the ``app/schemas/verification.py`` ``CriterionResult`` shape.
``VerificationInputs`` is the fully-extracted, DB-free bundle the service hands
to ``agent.verify`` -- keeping the pure logic testable without a session.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from aegis.schemas.common import Evidence

# PASS  -- the criterion is satisfied.
# FAIL  -- the criterion is violated (a mandatory FAIL => NOT_VERIFIED).
# UNKNOWN -- the input is absent or the sandbox could not run it; never a
#            silent FAIL. A mandatory UNKNOWN => PARTIAL (human review).
Verdict = str  # "PASS" | "FAIL" | "UNKNOWN"


@dataclass
class CriterionOutcome:
    name: str
    verdict: Verdict
    mandatory: bool
    detail: str = ""
    evidence: list[Evidence] = field(default_factory=list)


@dataclass
class VerificationInputs:
    task_id: str
    implementation_version: int
    snapshot_id: str

    # -- plan / alignment -------------------------------------------------- #
    expected_behavior: str
    problem_interpretation: str
    rollback_strategy: str
    plan_steps: list[dict]          # [{id, description, test_intent, ...}]
    traceability: dict              # {plan_step_id: [touched paths]}
    scope_violations: list[str]
    touched_files: list[str]
    allowed_scope: list[str]
    candidate_paths: list[str]      # mapping candidates, for the trace

    # -- acceptance / suite --------------------------------------------------- #
    has_issue_tests: bool
    execution_outcome: str | None   # "PASS" | "FAIL" | ... | "PARTIALLY_SUPPORTED" | None
    execution_command: str | None
    execution_id: str | None
    execution_results: list[dict]   # [{test_id, outcome}]
    targeted_test_ids: list[str]

    regression_present: bool
    regression_mode: str | None     # "smart" | "full" | None
    regression_new_failures: list[str]
    regression_subset_justification: str | None
    regression_full_suite_count: int
    regression_results: list[dict]

    # -- patch re-application ------------------------------------------------ #
    reapplies: bool | None          # None when there were no edit-ops to replay

    # -- review ----------------------------------------------------------- #
    review_present: bool
    review_blocking: bool
    review_blocking_findings: list[str]

    # -- score gate ----------------------------------------------------- #
    pcs_value: int | None
    crs_value: int | None
    pcs_min: int
    crs_max: int


@dataclass
class VerificationComputation:
    criteria: list[CriterionOutcome]
    alignment: dict                 # PlanAlignment.model_dump()
    trace: dict                     # ExplainabilityTrace.model_dump()
    verdict: str                    # VERIFIED | NOT_VERIFIED | PARTIAL
    resulting_state: str            # COMPLETED | AWAITING_APPROVAL | FAILED
    confidence: dict                # Confidence.model_dump()
