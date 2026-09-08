import { describe, expect, it } from "vitest";

import { taskRefetchInterval } from "./usePolling";

describe("taskRefetchInterval", () => {
  it("polls at the base cadence while the task is loading", () => {
    expect(taskRefetchInterval(undefined, 2000)).toBe(2000);
  });

  it("polls at the base cadence for an active state", () => {
    expect(taskRefetchInterval({ state: "IMPLEMENTING" }, 2000)).toBe(2000);
  });

  it("slows down for AWAITING_APPROVAL", () => {
    expect(taskRefetchInterval({ state: "AWAITING_APPROVAL" }, 2000)).toBe(8000);
  });

  it("stops at every terminal state", () => {
    for (const s of ["COMPLETED", "FAILED", "CANCELLED", "PARTIALLY_SUPPORTED"]) {
      expect(taskRefetchInterval({ state: s }, 2000)).toBe(false);
    }
  });

  it("stops when the base interval is not positive (Live toggle off)", () => {
    expect(taskRefetchInterval({ state: "IMPLEMENTING" }, 0)).toBe(false);
  });
});
