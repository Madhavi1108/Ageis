import { http, HttpResponse } from "msw";

import * as fx from "../fixtures";

const BASE = "http://localhost:8000";
const u = (path: string) => `${BASE}${path}`;

export const handlers = [
  http.get(u("/healthz"), () => HttpResponse.json({ status: "ok" })),
  http.get(u("/version"), () => HttpResponse.json({ version: "0.2.0", git_sha: "abc1234" })),

  // repositories
  http.post(u("/repositories"), () => HttpResponse.json(fx.repository, { status: 201 })),
  http.get(u("/repositories/:id"), () => HttpResponse.json(fx.repository)),
  http.get(u("/repositories/:id/health"), () => HttpResponse.json(fx.repoHealth)),
  http.get(u("/repositories/:id/git/context"), () => HttpResponse.json(fx.gitContext)),
  http.post(u("/repositories/:id/snapshots"), () =>
    HttpResponse.json(
      {
        snapshot_id: fx.SNAPSHOT_ID,
        repository_id: fx.REPO_ID,
        commit_sha: "abc1234",
        branch: "main",
        status: "READY",
        limit_reason: null,
        file_count: 12,
        total_bytes: 4096,
        languages: { python: 12 },
        ingested_at: "2026-09-08T10:00:00Z",
        job_id: "job_x",
      },
      { status: 201 },
    ),
  ),

  // graph
  http.get(u("/repositories/:id/snapshots/:sid/analysis/graph"), () =>
    HttpResponse.json(fx.graphSummary),
  ),
  http.get(u("/repositories/:id/snapshots/:sid/analysis/graph/subgraph"), () =>
    HttpResponse.json(fx.subgraph),
  ),
  http.get(u("/repositories/:id/snapshots/:sid/analysis/graph/node/:nid"), () =>
    HttpResponse.json({
      node: fx.subgraph.center,
      centrality: { degree: 0.5, betweenness: 0.2 },
      incoming: [fx.subgraph.edges[0]],
      outgoing: [],
    }),
  ),

  // tasks
  http.get(u("/tasks"), () => HttpResponse.json(fx.taskList)),
  http.post(u("/tasks"), () =>
    HttpResponse.json(
      { task: fx.makeTask({ state: "PENDING" }), normalization: { truncated: false, original_bytes: 40, stored_bytes: 40 } },
      { status: 201 },
    ),
  ),
  http.get(u("/tasks/:id"), () => HttpResponse.json(fx.makeTask())),
  http.post(u("/tasks/:id/run"), () => HttpResponse.json(fx.makeTask({ state: "QUEUED" }))),
  http.post(u("/tasks/:id/cancel"), () => HttpResponse.json(fx.makeTask({ state: "CANCELLED" }))),
  http.get(u("/tasks/:id/timeline"), () => HttpResponse.json(fx.fullTimeline)),
  http.get(u("/tasks/:id/mapping"), () => HttpResponse.json(fx.mapping)),
  http.get(u("/tasks/:id/impact"), () => HttpResponse.json(fx.impact)),
  http.get(u("/tasks/:id/plan"), () => HttpResponse.json(fx.plan)),
  http.post(u("/tasks/:id/plan"), () => HttpResponse.json(fx.plan, { status: 201 })),
  http.post(u("/tasks/:id/plan/validate"), () => HttpResponse.json(fx.plan)),
  http.get(u("/tasks/:id/changes"), () => HttpResponse.json(fx.implementation)),
  http.post(u("/tasks/:id/changes"), () => HttpResponse.json(fx.implementation, { status: 201 })),
  http.get(u("/tasks/:id/tests"), () => HttpResponse.json(fx.tests)),
  http.post(u("/tasks/:id/tests"), () => HttpResponse.json(fx.tests, { status: 201 })),
  http.get(u("/tasks/:id/executions"), () => HttpResponse.json(fx.executions)),
  http.post(u("/tasks/:id/executions"), () => HttpResponse.json(fx.executions[0], { status: 201 })),
  http.get(u("/tasks/:id/failures"), () => HttpResponse.json(fx.failures)),
  http.get(u("/tasks/:id/repairs"), () => HttpResponse.json(fx.repairs)),
  http.get(u("/tasks/:id/regression"), () => HttpResponse.json(fx.regression)),
  http.get(u("/tasks/:id/review"), () => HttpResponse.json(fx.review)),
  http.get(u("/tasks/:id/risk"), () => HttpResponse.json(fx.risk)),
  http.get(u("/tasks/:id/confidence"), () => HttpResponse.json(fx.confidence)),
  http.get(u("/tasks/:id/verification"), () => HttpResponse.json(fx.makeVerification())),
  http.post(u("/tasks/:id/verification/decision"), async ({ request }) => {
    const body = (await request.json()) as { decision: string };
    return HttpResponse.json(
      fx.makeVerification({
        verdict: body.decision === "APPROVE" ? "VERIFIED" : "NOT_VERIFIED",
        resulting_state: body.decision === "APPROVE" ? "COMPLETED" : "FAILED",
        decision: {
          decision: body.decision as "APPROVE" | "REJECT",
          reason: "looks good",
          actor: "tester",
          decided_at: "2026-09-08T10:05:00Z",
        },
      }),
    );
  }),
  http.get(u("/tasks/:id/pr"), () => HttpResponse.json(fx.pr)),
  http.post(u("/tasks/:id/pr"), () => HttpResponse.json(fx.pr, { status: 201 })),
  http.get(u("/tasks/:id/memory"), () => HttpResponse.json(fx.memoryList[0])),

  // jobs
  http.get(u("/jobs"), () => HttpResponse.json(fx.jobList)),
  http.get(u("/jobs/:id"), () => HttpResponse.json(fx.jobList.items[0])),
  http.post(u("/jobs/:id/cancel"), () => HttpResponse.json(fx.jobList.items[0])),

  // memory
  http.get(u("/memory"), () => HttpResponse.json(fx.memoryList)),
  http.post(u("/memory/search"), () => HttpResponse.json(fx.memoryHits)),

  // github
  http.get(u("/github/repos/:owner/:repo"), () =>
    HttpResponse.json({
      full_name: "acme/widgets",
      default_branch: "main",
      private: false,
      html_url: "https://github.com/acme/widgets",
      description: null,
    }),
  ),
  http.get(u("/github/repos/:owner/:repo/issues/:number"), () =>
    HttpResponse.json({
      number: 42,
      title: "Discount bug",
      body: "discount exceeds 0.5",
      state: "open",
      html_url: "https://github.com/acme/widgets/issues/42",
    }),
  ),
];

/** A 404-style ErrorEnvelope response, for "stage not produced yet" tests. */
export function notFound(code = "PLAN_NOT_FOUND") {
  return HttpResponse.json(
    { code, message: "not produced yet", details: null, evidence: null },
    { status: 404 },
  );
}

export function conflict(code = "TASK_INVALID_STATE") {
  return HttpResponse.json(
    { code, message: "precondition not met", details: null, evidence: null },
    { status: 409 },
  );
}

export function forbidden() {
  return HttpResponse.json(
    { code: "HTTP_403", message: "forbidden", details: null, evidence: null },
    { status: 403 },
  );
}
