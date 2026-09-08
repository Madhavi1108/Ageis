import { describe, expect, it } from "vitest";

import { implementation } from "../../test/fixtures";
import { changedLineCount, computeDiffStats } from "./diffStats";

describe("computeDiffStats", () => {
  it("parses the fixture patch into one file with correct add/delete counts", () => {
    const stats = computeDiffStats(implementation.patch.diff_text);
    expect(stats.fileStats).toHaveLength(1);
    expect(stats.fileStats[0].path).toBe("invoice.py");
    expect(stats.totalAdditions).toBe(1);
    expect(stats.totalDeletions).toBe(1);
  });

  it("returns empty for an empty diff", () => {
    const stats = computeDiffStats("");
    expect(stats.files).toHaveLength(0);
    expect(stats.totalAdditions).toBe(0);
  });

  it("changedLineCount counts non-normal lines", () => {
    const stats = computeDiffStats(implementation.patch.diff_text);
    expect(changedLineCount(stats.files[0])).toBe(2);
  });
});
