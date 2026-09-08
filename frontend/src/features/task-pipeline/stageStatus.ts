import type { TimelineEntry } from "../../types/api";
import {
  STAGES,
  STATE_RANK,
  TERMINAL_STATES,
  TERMINAL_SUCCESS,
  type StageDef,
  type StageId,
  type StageStatus,
} from "../../types/pipeline";

export interface StageView {
  def: StageDef;
  status: StageStatus;
  attempts: number;
  startedAt: string | null;
  endedAt: string | null;
  durationMs: number | null;
  error: Record<string, unknown> | null;
  note: string | null;
}

interface Input {
  taskState: string;
  terminalReason?: string | null;
  entries: TimelineEntry[];
}

function stepEntries(entries: TimelineEntry[]): TimelineEntry[] {
  return entries
    .filter((e) => e.kind === "STEP")
    .slice()
    .sort((a, b) => {
      if (a.seq != null && b.seq != null) return a.seq - b.seq;
      return new Date(a.at).getTime() - new Date(b.at).getTime();
    });
}

/**
 * Split the two EXECUTING_TESTS occurrences: the first is `execute`, a later one
 * (after an INVESTIGATING/REPAIRING step) is `execute_retry`.
 */
function bucketByStage(steps: TimelineEntry[]): Map<StageId, TimelineEntry[]> {
  const out = new Map<StageId, TimelineEntry[]>();
  const push = (id: StageId, e: TimelineEntry) => {
    const arr = out.get(id) ?? [];
    arr.push(e);
    out.set(id, arr);
  };
  let sawDebug = false;
  for (const e of steps) {
    if (e.state === "INVESTIGATING") {
      sawDebug = true;
      push("investigate", e);
      continue;
    }
    if (e.state === "REPAIRING") {
      sawDebug = true;
      push("repair", e);
      continue;
    }
    if (e.state === "EXECUTING_TESTS") {
      push(sawDebug ? "execute_retry" : "execute", e);
      continue;
    }
    const def = STAGES.find((s) => s.state === e.state && s.id !== "investigate" && s.id !== "repair");
    if (def) push(def.id, e);
  }
  return out;
}

export function computeStageViews(input: Input): StageView[] {
  const steps = stepEntries(input.entries);
  const buckets = bucketByStage(steps);
  const taskRank = TERMINAL_SUCCESS.has(input.taskState)
    ? 999
    : (STATE_RANK[input.taskState] ?? 0);
  const isFailed = input.taskState === "FAILED";
  const isCancelled = input.taskState === "CANCELLED";
  const isPartial = input.taskState === "PARTIALLY_SUPPORTED";
  const lastStepState = steps.length ? steps[steps.length - 1].state : null;

  const views: StageView[] = [];
  for (const def of STAGES) {
    const mine = buckets.get(def.id) ?? [];
    const hasSteps = mine.length > 0;

    // conditional (debug branch) stages: only render if they actually ran or
    // are running now.
    if (def.conditional && !hasSteps && input.taskState !== def.state) continue;

    const last = hasSteps ? mine[mine.length - 1] : null;
    const stageRank = STATE_RANK[def.state] ?? 0;
    const openStep = mine.find((e) => !e.exited_at) ?? null;

    let status: StageStatus = "pending";
    let note: string | null = null;
    let error: Record<string, unknown> | null = null;

    if (input.taskState === def.state && !TERMINAL_STATES.has(input.taskState)) {
      status = "active";
    } else if (openStep) {
      status = "active";
    } else if (isFailed && lastStepState === def.state) {
      status = "failed";
      error = (last?.error as Record<string, unknown> | null) ?? null;
      note = input.terminalReason ?? null;
    } else if (hasSteps && last?.exited_at) {
      status = "done";
    } else if (TERMINAL_SUCCESS.has(input.taskState)) {
      status = "done";
    } else if (taskRank > stageRank) {
      // resume / fast-forward: the task is already past this stage
      status = "done";
    } else if (isPartial) {
      status = hasSteps ? "done" : "skipped";
      if (!hasSteps) note = "pipeline stopped — environment only partially supported";
    } else if (isCancelled) {
      status = hasSteps ? "done" : "skipped";
      if (!hasSteps) note = "task cancelled before this stage";
    } else {
      status = "pending";
    }

    if (isCancelled && status === "active") {
      status = "skipped";
      note = input.terminalReason ?? "cancelled mid-stage";
    }

    const durationMs = mine.reduce((sum, e) => sum + (e.duration_ms ?? 0), 0);
    views.push({
      def,
      status,
      attempts: mine.length,
      startedAt: mine[0]?.at ?? null,
      endedAt: last?.exited_at ?? null,
      durationMs: durationMs > 0 ? durationMs : null,
      error,
      note,
    });
  }
  return views;
}
