import type {
  CodeGraphSummary,
  EngineeringMemoryOut,
  EngineeringPlan,
  FailureAnalysis,
  GitContext,
  ImpactAnalysis,
  ImplementationResult,
  IssueCodeMapping,
  JobList,
  MemoryHit,
  PatchConfidence,
  PatchRiskAssessment,
  PullRequestOut,
  RegressionResult,
  RepairResult,
  RepositoryHealthProfile,
  RepositoryRef,
  ReviewReport,
  SubgraphResult,
  Task,
  TaskList,
  TaskTimeline,
  TestExecution,
  TestGeneration,
  VerificationResult,
} from "../../types/api";

export const REPO_ID = "repo_1";
export const TASK_ID = "task_1";
export const SNAPSHOT_ID = "snap_1";

const now = "2026-09-08T10:00:00Z";

export const repository: RepositoryRef = {
  id: REPO_ID,
  source_type: "LOCAL",
  url_or_path: "/repos/acceptance",
  default_branch: "main",
  name: "acceptance",
  owner: null,
  created_at: now,
  updated_at: now,
};

export const repoHealth: RepositoryHealthProfile = {
  repository_id: REPO_ID,
  snapshot_id: SNAPSHOT_ID,
  value: 72,
  classification: "MEDIUM",
  subscores: [
    { name: "maintainability", normalized: 0.7, weight: 0.3, contribution: 0.21, basis: "INFERENCE", raw: null },
    { name: "ci_presence", normalized: 1, weight: 0.1, contribution: 0.1, basis: "FACT", raw: 1 },
  ],
  risky_modules: [
    { path: "invoice.py", score: 0.8, centrality: 0.6, complexity: 0.5, churn: null, inverse_coverage: null },
  ],
  scope: "repository",
  model_version: "rhp-v1.0.0",
  created_at: now,
};

export const gitContext: GitContext = {
  available: true,
  repository_id: REPO_ID,
  commit_count: 2,
  commits: [
    {
      sha: "abc1234def",
      message: "fix: cap discount",
      author_email_hash: "h1",
      authored_at: now,
      insertions: 3,
      deletions: 1,
      files_changed: ["invoice.py"],
      is_related_fix: true,
    },
  ],
  churn: [],
  related_fixes: [],
};

export function makeTask(overrides: Partial<Task> = {}): Task {
  return {
    id: TASK_ID,
    repository_id: REPO_ID,
    issue_id: null,
    snapshot_id: SNAPSHOT_ID,
    task_type: "BUG",
    title: "Discount not capped at 0.5",
    description: "calculate_total allows discount > 0.5",
    constraints: null,
    priority: "NORMAL",
    allowed_paths: ["invoice.py"],
    idempotency_key: "idem_1",
    state: "COMPLETED",
    terminal_reason: null,
    created_by: "tester",
    created_at: now,
    updated_at: now,
    ...overrides,
  };
}

export const taskList: TaskList = {
  items: [makeTask()],
  limit: 25,
  offset: 0,
  total: 1,
};

export function makeTimeline(states: string[], taskState = "COMPLETED"): TaskTimeline {
  return {
    task_id: TASK_ID,
    state: taskState,
    entries: states.map((state, i) => ({
      kind: "STEP" as const,
      seq: i + 1,
      state,
      at: now,
      exited_at: now,
      duration_ms: 1200,
      error: null,
      detail: null,
      input_ref: i === 0 ? null : `ref_${i}`,
      output_ref: `ref_${i + 1}`,
    })),
  };
}

export const fullTimeline = makeTimeline([
  "INGESTING",
  "ANALYZING",
  "PLANNING",
  "PLAN_VALIDATION",
  "IMPLEMENTING",
  "GENERATING_TESTS",
  "EXECUTING_TESTS",
  "REGRESSION_TESTING",
  "REVIEWING",
  "VERIFYING",
]);

export const jobList: JobList = {
  items: [
    {
      id: "job_1",
      task_id: TASK_ID,
      type: "RUN_TASK",
      state: "SUCCEEDED",
      progress: 1,
      attempts: 1,
      max_attempts: 3,
      idempotency_key: "run:task_1",
      dedupe_key: "run:task_1",
      last_checkpoint: { stage: "verify" },
      worker_id: "w1",
      queued_at: now,
      started_at: now,
      finished_at: now,
      error: null,
      created_at: now,
    },
  ],
  limit: 25,
  offset: 0,
  total: 1,
};

export const mapping: IssueCodeMapping = {
  task_id: TASK_ID,
  snapshot_id: SNAPSHOT_ID,
  candidates: [
    {
      path: "invoice.py",
      symbols: ["calculate_total"],
      score: 0.91,
      confidence: 0.88,
      labels: ["FACT"],
      evidence: [{ kind: "symbol", ref: "invoice.calculate_total", detail: "named in the issue" }],
    },
  ],
  related_tests: ["test_invoice.py::test_total"],
  dependencies: [],
  semantic_available: false,
  overall_confidence: 0.82,
  model_version: "map-v1",
  created_at: now,
};

export const impact: ImpactAnalysis = {
  task_id: TASK_ID,
  snapshot_id: SNAPSHOT_ID,
  changed_set: { files: ["invoice.py"], symbols: ["calculate_total"] },
  blast_radius: { invoice: ["billing.py"] },
  callers: [{ symbol: "calculate_total", callers: [{ ref: "billing.run", hop: 1, edge_confidence: "RESOLVED" }] }],
  related_tests: ["test_invoice.py::test_total"],
  public_api_touched: [],
  config_refs: [],
  db_refs: [],
  regression_areas: [{ path: "billing.py", score: 0.4, reason: "calls the changed symbol" }],
  risk_signal_bundle: {},
  report: "Impact: invoice.py::calculate_total; 1 related test.",
  created_at: now,
};

export const plan: EngineeringPlan = {
  task_id: TASK_ID,
  snapshot_id: SNAPSHOT_ID,
  version: 1,
  problem_interpretation: "Discount must be capped at 0.5.",
  expected_behavior: "calculate_total clamps discount to 0.5.",
  assumptions: ["discount is a fraction"],
  files_to_inspect: ["invoice.py"],
  files_to_modify: ["invoice.py"],
  symbols_to_modify: ["calculate_total"],
  dependencies: [],
  regression_risks: ["billing totals"],
  rollback_strategy: "revert the one-line change",
  test_strategy: {},
  steps: [
    { id: "s1", description: "Clamp discount to 0.5 in calculate_total", test_intent: "discount > 0.5 is capped", evidence_refs: [] },
  ],
  evidence: [{ kind: "symbol", ref: "invoice.calculate_total", detail: "target symbol" }],
  confidence: { value: 0.8, basis: "INFERENCE" },
  source: "AI",
  validation: { verdict: "APPROVED", reasons: ["in scope"], checked: { scope: true } },
  created_at: now,
};

export const implementation: ImplementationResult = {
  task_id: TASK_ID,
  snapshot_id: SNAPSHOT_ID,
  version: 1,
  edit_ops: [
    {
      path: "invoice.py",
      op: "replace",
      anchor: "discount = min(discount, 1.0)",
      old: "discount = min(discount, 1.0)",
      new: "discount = min(discount, 0.5)",
      plan_step_id: "s1",
      rationale: "cap discount at 0.5 per the issue",
      evidence: [{ kind: "line_range", ref: "invoice.py:12-12", detail: "the clamp line" }],
    },
  ],
  scope_violations: [],
  traceability: { s1: ["invoice.py"] },
  source: "AI",
  patch: {
    diff_text: [
      "diff --git a/invoice.py b/invoice.py",
      "index 1111111..2222222 100644",
      "--- a/invoice.py",
      "+++ b/invoice.py",
      "@@ -9,7 +9,7 @@ def calculate_total(items, discount):",
      "     subtotal = sum(i.price for i in items)",
      "-    discount = min(discount, 1.0)",
      "+    discount = min(discount, 0.5)",
      "     return subtotal * (1 - discount)",
      "",
    ].join("\n"),
    touched_paths: ["invoice.py"],
    diff_size: 220,
  },
  created_at: now,
};

export const tests: TestGeneration = {
  task_id: TASK_ID,
  snapshot_id: SNAPSHOT_ID,
  implementation_id: "impl_1",
  version: 1,
  test_cases: [
    {
      name: "test_discount_capped",
      path: "test_invoice_boundary.py",
      target_symbol: "invoice.calculate_total",
      kind: "BOUNDARY",
      rationale: "discount above 0.5 must be clamped",
      code: "def test_discount_capped(): ...",
      evidence: [],
      status: "GENERATED",
      invalid_reason: null,
      created_at: now,
    },
  ],
  targeted_set: ["invoice.calculate_total"],
  policy_gaps: [],
  created_at: now,
};

export const executions: TestExecution[] = [
  {
    id: "exec_1",
    task_id: TASK_ID,
    snapshot_id: SNAPSHOT_ID,
    implementation_id: "impl_1",
    version: 1,
    command: "pytest -q test_invoice_boundary.py",
    exit_code: 0,
    outcome: "PASS",
    reason: null,
    results: [{ test_id: "test_invoice_boundary.py::test_discount_capped", outcome: "PASS" }],
    duration_ms: 900,
    stdout_artifact_id: "a1",
    stderr_artifact_id: null,
    created_at: now,
  },
];

export const failures: FailureAnalysis = {
  task_id: TASK_ID,
  execution_id: "exec_0",
  failures: [
    {
      test_name: "test_invoice.py::test_total",
      failure_type: "ASSERTION",
      exception_type: "AssertionError",
      message: "assert 40 == 50",
      frames: [{ file: "invoice.py", lineno: 12, symbol_id: "invoice.calculate_total", in_diff: true, code_slice: null }],
      chained: false,
    },
  ],
  facts: ["1 test failing"],
  inferences: ["most-implicated symbol: calculate_total"],
  classification: {},
  evidence: {},
  created_at: now,
};

export const repairs: RepairResult = {
  task_id: TASK_ID,
  investigation_execution_id: "exec_0",
  outcome: "REPAIRED",
  attempts: [
    {
      iteration: 1,
      hypothesis: "clamp uses 1.0 instead of 0.5",
      edit_ops: [],
      diff_size: 40,
      failing_before: 1,
      failing_after: 0,
      regression_failures: 0,
      outcome: "GREEN",
      score: [0, 0],
      targeted_execution_id: "exec_1",
      created_at: now,
    },
  ],
  best_iteration: 1,
  final_edit_ops: [],
  safe_stop: null,
  created_at: now,
};

export const regression: RegressionResult = {
  plan: {
    task_id: TASK_ID,
    snapshot_id: SNAPSHOT_ID,
    changed_files: ["invoice.py"],
    changed_symbols: ["calculate_total"],
    tests: [
      { test_id: "test_invoice.py::test_total", path: "test_invoice.py", classification: "TARGETED", rationale: "covers the changed symbol", covers_symbol: "calculate_total", hops: 0 },
    ],
    selection: { pre_verification: ["test_invoice.py::test_total"] },
    full_suite_count: 5,
    mode: "smart",
    subset_justification: "smart subset around the impact set",
    subset_risk_note: null,
    created_at: now,
  },
  executed: true,
  execution_id: "exec_2",
  baseline_execution_id: null,
  new_failures: [],
  reason: null,
};

export const review: ReviewReport = {
  task_id: TASK_ID,
  implementation_version: 1,
  findings: [
    {
      source: "AI",
      category: "CORRECTNESS",
      severity: "LOW",
      file: "invoice.py",
      line_start: 12,
      line_end: 12,
      description: "Consider documenting the 0.5 cap.",
      recommendation: "Add a comment.",
      evidence: [],
      confidence: { value: 0.5, basis: "INFERENCE" },
      status: "OPEN",
    },
  ],
  counts_by_severity: { LOW: 1 },
  counts_by_category: { CORRECTNESS: 1 },
  blocking: false,
  static_tools_run: ["ruff"],
  policy_gaps: [],
  created_at: now,
};

export const risk: PatchRiskAssessment = {
  task_id: TASK_ID,
  implementation_version: 1,
  value: 28,
  classification: "LOW",
  crs_raw: 0.28,
  per_signal_contributions: [
    { name: "blast_radius", normalized: 0.2, weight: 0.4, contribution: 0.08, basis: "FACT", raw: 1 },
  ],
  overall_confidence: 0.7,
  task_risk_profile: { ...repoHealth, scope: "task" },
  evidence_refs: [],
  model_version: "crs-v1",
  created_at: now,
};

export const confidence: PatchConfidence = {
  task_id: TASK_ID,
  implementation_version: 1,
  value: 74,
  classification: "MEDIUM",
  pcs_raw: 0.74,
  security_gate: 1,
  hard_gate: [],
  per_signal_contributions: [
    { name: "tests_pass", normalized: 1, weight: 0.5, contribution: 0.5, basis: "FACT", raw: 1 },
  ],
  overall_confidence: 0.66,
  evidence_refs: [],
  model_version: "pcs-v1",
  created_at: now,
};

export function makeVerification(overrides: Partial<VerificationResult> = {}): VerificationResult {
  return {
    task_id: TASK_ID,
    implementation_version: 1,
    verdict: "VERIFIED",
    criteria: [
      { name: "acceptance_tests", verdict: "PASS", mandatory: true, detail: "all pass", evidence: [] },
      { name: "scope_clean", verdict: "PASS", mandatory: true, detail: "no violations", evidence: [] },
    ],
    plan_alignment: {
      steps_total: 1,
      steps_implemented: 1,
      unimplemented_steps: [],
      unplanned_files: [],
      files_touched: ["invoice.py"],
    },
    trace: {
      why_file: ["invoice.py holds calculate_total"],
      why_change: "cap discount at 0.5",
      why_test: ["boundary test for discount > 0.5"],
      why_safe: "one-line clamp, covered by tests",
    },
    trace_artifact_id: null,
    replay_fidelity: 1,
    confidence: { value: 0.8, basis: "INFERENCE" },
    resulting_state: "COMPLETED",
    decision: null,
    model_version: "verify-v1",
    created_at: now,
    ...overrides,
  };
}

export const pr: PullRequestOut = {
  id: "pr_1",
  task_id: TASK_ID,
  title: "Cap discount at 0.5 in calculate_total",
  branch: "aegis/task-1",
  mode: "LOCAL_ARTIFACT",
  state: "DRAFTED",
  github_url: null,
  github_number: null,
  commit_sha: "abc1234def0",
  body_artifact_id: "pr_body_1",
  failure_reason: null,
  created_at: now,
};

export const memoryList: EngineeringMemoryOut[] = [
  {
    id: "mem_1",
    repository_id: REPO_ID,
    task_id: TASK_ID,
    issue_text_sanitized: "Discount not capped at 0.5",
    touched_symbols: ["calculate_total"],
    touched_files: ["invoice.py"],
    failure_signatures: ["AssertionError in test_total"],
    fix_summary: "clamp discount to 0.5",
    plan_ref: {},
    patch_ref: null,
    review_summary: {},
    verification_verdict: "VERIFIED",
    outcome: "COMPLETED",
    embedding_ref: null,
    created_at: now,
  },
];

export const memoryHits: MemoryHit[] = [
  {
    task_id: "task_0",
    repository_id: REPO_ID,
    outcome: "COMPLETED",
    verification_verdict: "VERIFIED",
    issue_summary: "cap a fractional value",
    fix_summary: "used min() with the ceiling",
    touched_symbols: ["calculate_total"],
    touched_files: ["invoice.py"],
    similarity: 0.73,
    same_repository: true,
    label: "historical — verify",
    provenance: "task_0 · invoice.py",
    created_at: now,
  },
];

export const graphSummary: CodeGraphSummary = {
  snapshot_id: SNAPSHOT_ID,
  node_count: 3,
  edge_count: 2,
  nodes_by_type: { function: 2, file: 1 },
  edges_by_type: { CALLS: 1, CONTAINS: 1 },
  unresolved_call_count: 0,
  graph_artifact_id: "g1",
};

export const subgraph: SubgraphResult = {
  center: { id: "n_invoice", node_type: "file", ref: "invoice.py", label: "invoice.py" },
  hops: 1,
  nodes: [
    { id: "n_calc", node_type: "function", ref: "invoice.calculate_total", label: "calculate_total" },
    { id: "n_billing", node_type: "function", ref: "billing.run", label: "run" },
  ],
  edges: [
    {
      id: "e1",
      edge_type: "CONTAINS",
      source: { id: "n_invoice", node_type: "file", ref: "invoice.py", label: "invoice.py" },
      target: { id: "n_calc", node_type: "function", ref: "invoice.calculate_total", label: "calculate_total" },
      confidence: null,
    },
    {
      id: "e2",
      edge_type: "CALLS",
      source: { id: "n_billing", node_type: "function", ref: "billing.run", label: "run" },
      target: { id: "n_calc", node_type: "function", ref: "invoice.calculate_total", label: "calculate_total" },
      confidence: "RESOLVED",
    },
  ],
};
