// Central query-key factory so invalidation stays consistent.

export type StageKey =
  | "plan"
  | "mapping"
  | "impact"
  | "changes"
  | "tests"
  | "executions"
  | "failures"
  | "repairs"
  | "regression"
  | "review"
  | "risk"
  | "confidence"
  | "verification"
  | "pr"
  | "memory";

export const qk = {
  health: () => ["health"] as const,
  version: () => ["version"] as const,

  repos: () => ["repos"] as const,
  repo: (id: string) => ["repos", id] as const,
  repoHealth: (id: string) => ["repos", id, "health"] as const,
  repoGit: (id: string, kind: string) => ["repos", id, "git", kind] as const,
  repoAnalysis: (id: string, snapshotId: string) => ["repos", id, "analysis", snapshotId] as const,
  graphSummary: (id: string, snapshotId: string) =>
    ["repos", id, "graph", snapshotId, "summary"] as const,
  subgraph: (id: string, snapshotId: string, node: string, hops: number) =>
    ["repos", id, "graph", snapshotId, "subgraph", node, hops] as const,
  graphNode: (id: string, snapshotId: string, nodeId: string) =>
    ["repos", id, "graph", snapshotId, "node", nodeId] as const,

  tasks: (params?: Record<string, unknown>) => ["tasks", params ?? {}] as const,
  task: (id: string) => ["tasks", id] as const,
  taskTimeline: (id: string) => ["tasks", id, "timeline"] as const,
  taskStage: (id: string, stage: StageKey) => ["tasks", id, "stage", stage] as const,

  jobs: (params?: Record<string, unknown>) => ["jobs", params ?? {}] as const,
  job: (id: string) => ["jobs", id] as const,

  memoryList: (repositoryId?: string) => ["memory", "list", repositoryId ?? null] as const,
  memorySearch: (query: string, repositoryId?: string) =>
    ["memory", "search", query, repositoryId ?? null] as const,

  githubRepo: (owner: string, repo: string) => ["github", owner, repo] as const,
  githubIssue: (owner: string, repo: string, number: number) =>
    ["github", owner, repo, "issues", number] as const,
};
