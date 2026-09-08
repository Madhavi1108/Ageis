// Mirror of backend/app/orchestration/orchestrator.py (STAGE_ORDER, _STATE_RANK)
// and backend/app/models/task.py (TaskState). Keep in sync by hand — the
// pipeline view derives per-stage status from these.

import type { StageKey } from "../services/queryKeys";

export const TASK_STATES = [
  "PENDING",
  "QUEUED",
  "INGESTING",
  "ANALYZING",
  "PLANNING",
  "PLAN_VALIDATION",
  "IMPLEMENTING",
  "GENERATING_TESTS",
  "EXECUTING_TESTS",
  "INVESTIGATING",
  "REPAIRING",
  "REGRESSION_TESTING",
  "REVIEWING",
  "VERIFYING",
  "AWAITING_APPROVAL",
  "COMPLETED",
  "FAILED",
  "CANCELLED",
  "PARTIALLY_SUPPORTED",
] as const;

export type TaskStateName = (typeof TASK_STATES)[number];

export const TERMINAL_STATES: ReadonlySet<string> = new Set([
  "COMPLETED",
  "FAILED",
  "CANCELLED",
  "PARTIALLY_SUPPORTED",
]);

export const TERMINAL_SUCCESS: ReadonlySet<string> = new Set(["COMPLETED"]);

/** orchestrator._STATE_RANK — linear "how far has the task progressed" rank. */
export const STATE_RANK: Record<string, number> = {
  PENDING: 0,
  QUEUED: 1,
  INGESTING: 2,
  ANALYZING: 3,
  PLANNING: 4,
  PLAN_VALIDATION: 5,
  IMPLEMENTING: 6,
  GENERATING_TESTS: 7,
  EXECUTING_TESTS: 8,
  INVESTIGATING: 8,
  REPAIRING: 8,
  REGRESSION_TESTING: 9,
  REVIEWING: 10,
  VERIFYING: 11,
  AWAITING_APPROVAL: 12,
  COMPLETED: 99,
};

export type StageId =
  | "ingest"
  | "analyze"
  | "plan"
  | "validate"
  | "implement"
  | "generate_tests"
  | "execute"
  | "investigate"
  | "repair"
  | "execute_retry"
  | "regression"
  | "review"
  | "verify";

export interface StageDef {
  id: StageId;
  label: string;
  /** the TaskState this stage occupies */
  state: TaskStateName;
  /** shown only when a matching timeline STEP exists (debug branch) */
  conditional?: boolean;
  /** the task sub-route + stage query key this stage's panel reads */
  route?: string;
  stageKey?: StageKey;
}

// orchestrator.STAGE_ORDER
export const STAGES: StageDef[] = [
  { id: "ingest", label: "Ingest", state: "INGESTING" },
  { id: "analyze", label: "Analyze", state: "ANALYZING", route: "impact", stageKey: "impact" },
  { id: "plan", label: "Plan", state: "PLANNING", route: "plan", stageKey: "plan" },
  { id: "validate", label: "Validate plan", state: "PLAN_VALIDATION", route: "plan", stageKey: "plan" },
  { id: "implement", label: "Implement", state: "IMPLEMENTING", route: "changes", stageKey: "changes" },
  {
    id: "generate_tests",
    label: "Generate tests",
    state: "GENERATING_TESTS",
    route: "tests",
    stageKey: "tests",
  },
  { id: "execute", label: "Run tests", state: "EXECUTING_TESTS", route: "tests", stageKey: "executions" },
  {
    id: "investigate",
    label: "Investigate failure",
    state: "INVESTIGATING",
    conditional: true,
    route: "debugging",
    stageKey: "failures",
  },
  {
    id: "repair",
    label: "Repair",
    state: "REPAIRING",
    conditional: true,
    route: "debugging",
    stageKey: "repairs",
  },
  {
    id: "execute_retry",
    label: "Re-run tests",
    state: "EXECUTING_TESTS",
    conditional: true,
    route: "tests",
    stageKey: "executions",
  },
  {
    id: "regression",
    label: "Regression",
    state: "REGRESSION_TESTING",
    route: "debugging",
    stageKey: "regression",
  },
  { id: "review", label: "Review", state: "REVIEWING", route: "review", stageKey: "review" },
  {
    id: "verify",
    label: "Verify",
    state: "VERIFYING",
    route: "verification",
    stageKey: "verification",
  },
];

export type StageStatus = "pending" | "active" | "done" | "failed" | "skipped";
