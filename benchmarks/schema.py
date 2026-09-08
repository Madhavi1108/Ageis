"""Benchmark task + result schemas (docs/EVAL_HARNESS.md Section 2).

``BenchmarkTask`` is the on-disk task contract (SWE-bench-Lite style, cut to what
the curated deterministic set needs). ``TaskRun`` is the raw signal bundle the
runner captures for one task; ``BenchmarkResult`` wraps a whole dataset run with
provenance so a report is reproducible.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field

TaskType = Literal["BUG", "FEATURE", "REFACTOR"]
Difficulty = Literal["EASY", "MEDIUM", "HARD"]
VerificationLabel = Literal["CORRECT", "INCORRECT"]


class EditSpec(BaseModel):
    """One anchored edit, mirrored into an ``app`` EditOp by the runner."""

    file: str
    op: Literal["replace", "create", "insert"] = "replace"
    find: str | None = None
    replace: str | None = None
    prepend: str | None = None  # inserted once at the top of the file (replace op)


class FileSpec(BaseModel):
    path: str
    content: str


class MockSpec(BaseModel):
    """Everything needed to synthesize the canned ``MockProvider`` answers for a
    task (planning / implementation / test_synthesis / rca / repair). Compact on
    disk; expanded to full AI-schema dicts in ``benchmarks.runner``."""

    #: the correct fix (the implementation edit, or the repair edit when
    #: ``incomplete_fix`` is set)
    fix: EditSpec | None = None
    #: a deliberately wrong first implementation -> the bounded repair loop runs;
    #: ``fix`` then becomes the repair proposal
    incomplete_fix: EditSpec | None = None
    #: an ineffective repair proposal -> the loop stalls -> SAFE_STOP
    dead_repair: EditSpec | None = None
    #: brand-new files the implementation creates (FEATURE tasks)
    create: list[FileSpec] = Field(default_factory=list)
    #: extra edits stacked onto the implementation (wire a new module in, etc.)
    extra_edits: list[EditSpec] = Field(default_factory=list)
    #: a planted defect appended to the implementation (seeded-defect set)
    defect: EditSpec | None = None
    #: the generated test file(s) (test_synthesis output)
    generated_tests: list[FileSpec] = Field(default_factory=list)


class BenchmarkTask(BaseModel):
    id: str
    dataset: str = ""  # filled in by the loader
    repo_dir: str  # relative to the tasks.yaml file
    problem_statement: str
    task_type: TaskType = "BUG"
    difficulty: Difficulty = "EASY"

    gold_files: list[str]
    files_to_modify: list[str] = Field(default_factory=list)  # defaults to gold_files
    symbols_to_modify: list[str] = Field(default_factory=list)
    allowed_paths: list[str] | None = None

    test_cmd: str | None = None
    fail_to_pass: list[str] = Field(default_factory=list)
    pass_to_pass: list[str] = Field(default_factory=list)

    mock: MockSpec = Field(default_factory=MockSpec)

    # dataset-specific labels
    verification_label: VerificationLabel | None = None
    seeded_defect_kind: str | None = None
    seeded_regression: bool = False  # the canned fix breaks a pass_to_pass test on purpose
    expect_repair_outcome: Literal["REPAIRED", "SAFE_STOP"] | None = None

    @property
    def effective_files_to_modify(self) -> list[str]:
        return self.files_to_modify or list(self.gold_files)


# --------------------------------------------------------------------------- #
# Results
# --------------------------------------------------------------------------- #


class TestEval(BaseModel):
    """fail_to_pass / pass_to_pass evaluation of the final patched workspace."""

    fail_to_pass: dict[str, bool] = Field(default_factory=dict)
    pass_to_pass: dict[str, bool] = Field(default_factory=dict)

    @property
    def verified_fixed(self) -> bool:
        return (
            bool(self.fail_to_pass)
            and all(self.fail_to_pass.values())
            and all(self.pass_to_pass.values())
        )

    @property
    def broke_a_pass_to_pass(self) -> bool:
        return any(not ok for ok in self.pass_to_pass.values())


class AICall(BaseModel):
    template: str
    tier: str
    input_tokens: int
    output_tokens: int


class TaskRun(BaseModel):
    task_id: str
    dataset: str
    task_type: TaskType
    error: str | None = None

    terminal_state: str | None = None
    wall_clock_ms: int = 0

    # localization (metric #1)
    predicted_files: list[str] = Field(default_factory=list)
    gold_files: list[str] = Field(default_factory=list)

    # plan / implementation (metrics #2, #8)
    plan_steps_total: int = 0
    plan_steps_implemented: int = 0
    changed_files: list[str] = Field(default_factory=list)
    unplanned_files: list[str] = Field(default_factory=list)
    scope_violation: bool = False
    scope_violation_justified: bool = False

    # tests (metrics #3, #4)
    tests_generated: int = 0
    tests_valid: int = 0
    test_results: list[str] = Field(default_factory=list)  # per result outcome strings
    real_execution: bool = False

    # repair (metrics #5, #11)
    entered_repair: bool = False
    repair_outcome: str | None = None  # REPAIRED | SAFE_STOP
    repair_iterations: int = 0

    # regression (metric #6)
    is_seeded_regression: bool = False
    regression_flagged: bool = False

    # review (metric #9)
    seeded_defect_kind: str | None = None
    review_flagged_defect: bool = False
    review_findings: list[str] = Field(default_factory=list)

    # scoring (calibration check)
    pcs_value: int | None = None
    pcs_classification: str | None = None
    crs_value: int | None = None
    crs_classification: str | None = None

    # verification (metrics #7, #10, #12, #16)
    verification_verdict: str | None = None  # final verdict (after any benchmark sign-off)
    pipeline_verdict: str | None = None  # the pipeline's own verdict, before benchmark sign-off
    verification_label: VerificationLabel | None = None
    replay_fidelity: float | None = None
    patch_generated: bool = False

    # cost (metric #13)
    ai_calls: list[AICall] = Field(default_factory=list)

    # fail_to_pass / pass_to_pass in the final workspace
    test_eval: TestEval = Field(default_factory=TestEval)

    # reference agents (metric #15)
    reference_outcomes: dict[str, bool] = Field(default_factory=dict)  # agent -> verified_fixed


class BenchmarkResult(BaseModel):
    dataset: str
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    provider: str = "mock"
    sandbox_mode: str = "fake"
    dataset_digest: str = ""
    aegis_git_head: str | None = None
    runs: list[TaskRun] = Field(default_factory=list)
