import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { screen, waitFor } from "@testing-library/react";

import { PipelineView } from "../../features/task-pipeline/PipelineView";
import { TASK_ID } from "../fixtures";
import { server } from "../msw/server";
import { renderWithProviders } from "../utils/renderWithProviders";

/**
 * Acceptance test for §30's "no decorative data" rule: with every stage panel
 * force-opened, each stage endpoint must receive at least one request.
 */
const EXPECTED_PATHS = [
  "/tasks/task_1/timeline",
  "/tasks/task_1/mapping",
  "/tasks/task_1/impact",
  "/tasks/task_1/plan",
  "/tasks/task_1/changes",
  "/tasks/task_1/tests",
  "/tasks/task_1/executions",
  "/tasks/task_1/regression",
  "/tasks/task_1/review",
  "/tasks/task_1/verification",
  "/tasks/task_1/risk",
  "/tasks/task_1/confidence",
];

describe("every pipeline panel issues a backend call", () => {
  const seen = new Set<string>();
  const record = ({ request }: { request: Request }) => {
    seen.add(new URL(request.url).pathname);
  };

  beforeEach(() => {
    seen.clear();
    server.events.on("request:start", record);
  });
  afterEach(() => {
    server.events.removeListener("request:start", record);
  });

  it("hits every stage endpoint", async () => {
    renderWithProviders(<PipelineView taskId={TASK_ID} forceOpenAll />);
    await screen.findByText("Verify");

    await waitFor(
      () => {
        for (const p of EXPECTED_PATHS) {
          expect(seen.has(p), `expected a request to ${p}`).toBe(true);
        }
      },
      { timeout: 4000 },
    );
  });
});
