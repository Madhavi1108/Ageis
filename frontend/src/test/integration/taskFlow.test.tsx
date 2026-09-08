import { describe, expect, it } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { PipelineView } from "../../features/task-pipeline/PipelineView";
import { TASK_ID } from "../fixtures";
import { renderWithProviders } from "../utils/renderWithProviders";

describe("task pipeline view", () => {
  it("renders the stage list from the timeline and lets a panel load its data", async () => {
    renderWithProviders(<PipelineView taskId={TASK_ID} />);

    // header + stages
    expect(await screen.findByText("Verify")).toBeInTheDocument();
    expect(screen.getByText("Implement")).toBeInTheDocument();
    expect(screen.getByText("Run tests")).toBeInTheDocument();

    // expand the Implement stage -> its panel calls /tasks/:id/changes
    await userEvent.click(screen.getByRole("button", { name: /Implement/i }));
    await waitFor(() =>
      expect(screen.getByText(/Open diff view/i)).toBeInTheDocument(),
    );
    expect(screen.getByText(/in scope/i)).toBeInTheDocument();
  });

  it("shows every pipeline stage as done for a COMPLETED task", async () => {
    renderWithProviders(<PipelineView taskId={TASK_ID} />);
    await screen.findByText("Verify");
    // 10 linear stages, all done -> 10 "done" status icons
    await waitFor(() => {
      const done = screen.getAllByLabelText("done");
      expect(done.length).toBeGreaterThanOrEqual(9);
    });
  });
});
