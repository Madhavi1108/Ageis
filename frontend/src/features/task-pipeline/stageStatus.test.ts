import { describe, expect, it } from "vitest";

import type { TimelineEntry } from "../../types/api";
import { computeStageViews } from "./stageStatus";

function step(state: string, seq: number, open = false): TimelineEntry {
  return {
    kind: "STEP",
    seq,
    state,
    at: "2026-09-08T10:00:00Z",
    exited_at: open ? null : "2026-09-08T10:01:00Z",
    duration_ms: open ? null : 1000,
    error: null,
    detail: null,
    input_ref: null,
    output_ref: null,
  };
}

const LINEAR = [
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
];

function views(taskState: string, states: string[], opts: { terminalReason?: string } = {}) {
  return computeStageViews({
    taskState,
    terminalReason: opts.terminalReason ?? null,
    entries: states.map((s, i) => step(s, i + 1)),
  });
}

describe("computeStageViews", () => {
  it("marks every non-conditional stage done on a clean COMPLETED run", () => {
    const v = views("COMPLETED", LINEAR);
    const byId = Object.fromEntries(v.map((x) => [x.def.id, x.status]));
    expect(byId.ingest).toBe("done");
    expect(byId.verify).toBe("done");
    // conditional debug stages never ran -> not rendered
    expect(byId.investigate).toBeUndefined();
    expect(byId.repair).toBeUndefined();
  });

  it("marks the current stage active and later stages pending mid-run", () => {
    const v = views("IMPLEMENTING", ["INGESTING", "ANALYZING", "PLANNING", "PLAN_VALIDATION"]);
    const byId = Object.fromEntries(v.map((x) => [x.def.id, x.status]));
    expect(byId.validate).toBe("done");
    expect(byId.implement).toBe("active");
    expect(byId.review).toBe("pending");
  });

  it("marks the failing stage failed on FAILED", () => {
    const v = computeStageViews({
      taskState: "FAILED",
      terminalReason: "sandbox unavailable",
      entries: [step("INGESTING", 1), step("ANALYZING", 2), step("EXECUTING_TESTS", 3)],
    });
    const exec = v.find((x) => x.def.id === "execute");
    expect(exec?.status).toBe("failed");
    expect(exec?.note).toBe("sandbox unavailable");
  });

  it("shows the debug branch when it ran", () => {
    const v = computeStageViews({
      taskState: "COMPLETED",
      terminalReason: null,
      entries: [
        step("INGESTING", 1),
        step("EXECUTING_TESTS", 2),
        step("INVESTIGATING", 3),
        step("REPAIRING", 4),
        step("EXECUTING_TESTS", 5),
        step("VERIFYING", 6),
      ],
    });
    const ids = v.map((x) => x.def.id);
    expect(ids).toContain("investigate");
    expect(ids).toContain("repair");
    expect(ids).toContain("execute_retry");
  });

  it("treats a resumed task (state ahead of the timeline) as having passed earlier stages", () => {
    const v = views("VERIFYING", ["INGESTING", "ANALYZING"]);
    const byId = Object.fromEntries(v.map((x) => [x.def.id, x.status]));
    expect(byId.plan).toBe("done");
    expect(byId.implement).toBe("done");
    expect(byId.verify).toBe("active");
  });

  it("marks remaining stages skipped on PARTIALLY_SUPPORTED", () => {
    const v = views("PARTIALLY_SUPPORTED", ["INGESTING", "ANALYZING"]);
    const plan = v.find((x) => x.def.id === "plan");
    expect(plan?.status).toBe("skipped");
  });

  it("counts attempts for a repeated stage", () => {
    const v = computeStageViews({
      taskState: "IMPLEMENTING",
      terminalReason: null,
      entries: [step("PLANNING", 1), step("PLAN_VALIDATION", 2), step("PLANNING", 3), step("PLAN_VALIDATION", 4)],
    });
    const plan = v.find((x) => x.def.id === "plan");
    expect(plan?.attempts).toBe(2);
  });
});
