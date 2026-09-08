import { describe, expect, it } from "vitest";
import { axe } from "vitest-axe";
import { screen, waitFor } from "@testing-library/react";

import { RepositoryDashboardPage } from "../../pages/RepositoryDashboardPage";
import { ReviewFindingsPage } from "../../pages/ReviewFindingsPage";
import { TaskListPage } from "../../pages/TaskListPage";
import { PipelineView } from "../../features/task-pipeline/PipelineView";
import { REPO_ID, TASK_ID } from "../fixtures";
import { renderWithProviders } from "../utils/renderWithProviders";

describe("screen render + accessibility", () => {
  it("Task list renders backend rows and is axe-clean", async () => {
    const { container } = renderWithProviders(<TaskListPage />);
    expect(await screen.findByText("Discount not capped at 0.5")).toBeInTheDocument();
    expect(await axe(container)).toHaveNoViolations();
  });

  it("Repository dashboard renders health from the backend", async () => {
    renderWithProviders(<RepositoryDashboardPage />, {
      route: `/repositories/${REPO_ID}`,
      path: "/repositories/:repoId",
    });
    expect(await screen.findByText("acceptance")).toBeInTheDocument();
    await waitFor(() => expect(screen.getByText("72")).toBeInTheDocument());
  });

  it("Review findings renders and is axe-clean", async () => {
    const { container } = renderWithProviders(<ReviewFindingsPage />, {
      route: `/tasks/${TASK_ID}/review`,
      path: "/tasks/:taskId/review",
    });
    expect(await screen.findByText(/Consider documenting the 0.5 cap/i)).toBeInTheDocument();
    expect(await axe(container)).toHaveNoViolations();
  });

  it("Pipeline view is axe-clean", async () => {
    const { container } = renderWithProviders(<PipelineView taskId={TASK_ID} />);
    await screen.findByText("Verify");
    expect(await axe(container)).toHaveNoViolations();
  });
});
