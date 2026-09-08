import { lazy, Suspense } from "react";
import { createBrowserRouter } from "react-router-dom";

import { AppLayout } from "./components/layout/AppLayout";
import { ErrorBoundary } from "./components/feedback/ErrorBoundary";
import { LoadingBlock } from "./components/feedback/LoadingBlock";
import { CodeImpactPage } from "./pages/CodeImpactPage";
import { CreateTaskPage } from "./pages/CreateTaskPage";
import { DebuggingTimelinePage } from "./pages/DebuggingTimelinePage";
import { EngineeringMemoryPage } from "./pages/EngineeringMemoryPage";
import { HealthPage } from "./pages/HealthPage";
import { NotFoundPage } from "./pages/NotFoundPage";
import { PlanningPage } from "./pages/PlanningPage";
import { PrSummaryPage } from "./pages/PrSummaryPage";
import { RepositoryDashboardPage } from "./pages/RepositoryDashboardPage";
import { ReviewFindingsPage } from "./pages/ReviewFindingsPage";
import { SettingsPage } from "./pages/SettingsPage";
import { TaskExecutionPage } from "./pages/TaskExecutionPage";
import { TaskListPage } from "./pages/TaskListPage";
import { TaskLayout } from "./pages/TaskLayout";
import { TestExecutionPage } from "./pages/TestExecutionPage";
import { VerificationResultPage } from "./pages/VerificationResultPage";

const ImplementationDiffPage = lazy(() =>
  import("./pages/ImplementationDiffPage").then((m) => ({ default: m.ImplementationDiffPage })),
);
const KnowledgeGraphPage = lazy(() =>
  import("./pages/KnowledgeGraphPage").then((m) => ({ default: m.KnowledgeGraphPage })),
);

function lazyRoute(node: React.ReactNode) {
  return (
    <ErrorBoundary>
      <Suspense fallback={<LoadingBlock label="Loading view…" />}>{node}</Suspense>
    </ErrorBoundary>
  );
}

function wrap(node: React.ReactNode) {
  return <ErrorBoundary>{node}</ErrorBoundary>;
}

export const router = createBrowserRouter([
  {
    element: <AppLayout />,
    children: [
      { path: "/", element: wrap(<RepositoryDashboardPage />) },
      { path: "/repositories/:repoId", element: wrap(<RepositoryDashboardPage />) },
      { path: "/repositories/:repoId/graph", element: lazyRoute(<KnowledgeGraphPage />) },
      { path: "/tasks", element: wrap(<TaskListPage />) },
      { path: "/tasks/new", element: wrap(<CreateTaskPage />) },
      {
        path: "/tasks/:taskId",
        element: wrap(<TaskLayout />),
        children: [
          { index: true, element: <TaskExecutionPage /> },
          { path: "plan", element: <PlanningPage /> },
          { path: "impact", element: <CodeImpactPage /> },
          { path: "changes", element: lazyRoute(<ImplementationDiffPage />) },
          { path: "tests", element: <TestExecutionPage /> },
          { path: "debugging", element: <DebuggingTimelinePage /> },
          { path: "review", element: <ReviewFindingsPage /> },
          { path: "verification", element: <VerificationResultPage /> },
          { path: "pr", element: <PrSummaryPage /> },
        ],
      },
      { path: "/memory", element: wrap(<EngineeringMemoryPage />) },
      { path: "/settings", element: wrap(<SettingsPage />) },
      { path: "/health", element: wrap(<HealthPage />) },
      { path: "*", element: <NotFoundPage /> },
    ],
  },
]);
