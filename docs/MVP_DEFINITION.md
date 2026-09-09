# AEGIS MVP Definition

Traceability: Specification §38, §54. Phase 0 deliverable (Spec §46 item 27). Companion to
`AEGIS_IMPLEMENTATION_PLAN.md` §7.3 (spine / thicken / harden / deferred), Appendix C, and
`ACCEPTANCE_CONTRACT.md`.

Status: final — reconciled against the built system (Phases 0–28), 2026-09-09. The MVP scope
below was drafted in Phase 0; several "post-MVP" items (the full dashboard, Excel, the benchmark
harness) were in fact delivered in Phases 22/23/25 and the matrix now reflects the **as-built**
state. Every SUPPORTED / PARTIALLY_SUPPORTED row cites a test; `backend/tests/docs/`
checks the citations and the OpenAPI surface.

---

## 1. MVP scope statement

AEGIS takes a well-specified engineering task plus a **Python** Git repository and autonomously
produces a **verified, evidence-backed, review-ready change** — through the full connected
pipeline — with local Git output, an external GitHub PR when credentials and policy permit, a
React dashboard, and Excel/structured reporting. Multi-language analysis and a productized
benchmark *service* remain post-MVP (the evaluation harness itself ships).

All 28 phases are implemented. Known caveats: the Docker sandbox happy path and the capability
spike have not been run against a live daemon / live provider in this environment; the worker is
single sequential. See `ACCEPTANCE_CONTRACT.md` → "Open items".

---

## 2. Support matrix (Spec §38)

Status values: **SUPPORTED** (implemented + executed + tested + integrated + verified),
**PARTIALLY_SUPPORTED** (works within stated limits; returns a structured reason beyond them),
**UNSUPPORTED** (not implemented; architecture leaves the seam).

| Capability | Status | Evidence | Notes |
|---|---|---|---|
| Git repositories | SUPPORTED | `backend/tests/integration/test_ingest_local_fixture.py` | local path + GitHub HTTPS URL |
| Python repositories | SUPPORTED | `backend/tests/integration/test_analyze_acceptance_fixture.py` | primary target; `ast` + `tree-sitter` resilience |
| JS / TS / Java / Go / C++ | UNSUPPORTED | — | analysis seam exists; no claims until implemented |
| Local repo ingestion | SUPPORTED | `backend/tests/integration/test_ingest_local_fixture.py` | inside configured root paths |
| GitHub repo ingestion | SUPPORTED | `backend/tests/integration/test_ingest_git_fixture.py` | public; authenticated when a token is configured |
| Python AST analysis | SUPPORTED | `backend/tests/integration/test_analyze_acceptance_fixture.py` | symbols, imports, signatures, entry points, test infra |
| Dependency analysis | SUPPORTED | `backend/tests/integration/test_analyze_builds_graph.py` | import edges + package requirements; classification incl. `UNKNOWN` |
| Git history analysis | SUPPORTED | `backend/tests/integration/test_git_api.py` | blame, churn, related-fix detection, the four history questions |
| Code graph | SUPPORTED | `backend/tests/integration/test_graph_api.py` | NetworkX + adjacency; call edges labelled RESOLVED/HEURISTIC/UNRESOLVED |
| Issue -> code mapping | SUPPORTED | `backend/tests/integration/test_mapping_acceptance_fixture.py` | lexical + graph + history + memory |
| Semantic retrieval in mapping | PARTIALLY_SUPPORTED | `backend/tests/unit/test_mapping_fuse.py` | needs an embeddings provider; lexical+graph fallback with reduced confidence |
| Impact analysis | SUPPORTED | `backend/tests/integration/test_impact_acceptance_fixture.py` | blast radius, callers, related tests, public API; config/db refs labelled INFERENCE |
| Engineering planning | SUPPORTED | `backend/tests/integration/test_planning_api.py` | AI plan + rule-based fallback when no provider |
| Plan validation | SUPPORTED | `backend/tests/integration/test_planning_api.py` | schema + feasibility + scope + evidence gate |
| Real code modification | SUPPORTED | `backend/tests/integration/test_implementation_acceptance_fixture.py` | anchored edits, unified diff, reversible, scope-tracked |
| Test generation | SUPPORTED | `backend/tests/integration/test_testing_acceptance_fixture.py` | framework-mirroring; boundary + negative per changed public fn |
| Secure sandbox execution | PARTIALLY_SUPPORTED | `backend/tests/integration/test_execution_acceptance_fixture.py` | Docker hardened path; `PARTIALLY_SUPPORTED` (no host fallback) when Docker absent — the case in this environment |
| Failure analysis | SUPPORTED | `backend/tests/integration/test_investigation_acceptance_fixture.py` | traceback parse, frame->symbol, deterministic classification |
| Autonomous repair | SUPPORTED | `backend/tests/integration/test_repair_acceptance_fixture.py` | bounded loop, auto-revert, safe stop with evidence |
| Regression testing | SUPPORTED | `backend/tests/integration/test_regression_acceptance_fixture.py` | smart selection + full suite; full-suite gates completion |
| Code review | SUPPORTED | `backend/tests/integration/test_review_acceptance_fixture.py` | static + custom AST rules + AI reviewer, 10 categories |
| Risk score (CRS) | SUPPORTED | `backend/tests/unit/test_scoring_risk.py` | deterministic, versioned, explained (`scoring-model v1.0.0`, provisional constants) |
| Confidence score (PCS) | SUPPORTED | `backend/tests/unit/test_scoring_confidence.py` | same; hard gates |
| Repository health profile | SUPPORTED | `backend/tests/unit/test_scoring_repo_health.py` | per-repo + task-specific risk profile |
| Verification | SUPPORTED | `backend/tests/integration/test_verification_acceptance_fixture.py` | mandatory-criteria checklist; engineering trace; no false-complete on negatives |
| Deterministic replay | PARTIALLY_SUPPORTED | `docs/GOVERNANCE.md` | fidelity depends on provider seed support; disclosed in the Trust Report |
| Engineering memory | SUPPORTED | `backend/tests/integration/test_memory_acceptance_fixture.py` | opt-in write on terminal state; lexical + symbol retrieval; embeddings optional |
| Local Git branch / commit | SUPPORTED | `backend/tests/integration/test_git_api.py` | in the workspace |
| GitHub PR creation | PARTIALLY_SUPPORTED | `backend/tests/integration/test_pr_acceptance_fixture.py` | local PR artifact always; real PR only on GitHub 201 + stored URL, and only when write creds + policy permit |
| FastAPI API | SUPPORTED | `backend/tests/integration/test_openapi_snapshot.py` | all endpoint groups; OpenAPI; RBAC; pagination |
| Job orchestration | SUPPORTED | `backend/tests/integration/test_worker_lifecycle.py` | states, retries with real backoff, cancellation, crash recovery, backpressure |
| Dashboard | SUPPORTED | `frontend/src/test/integration/screens.render.test.tsx` | 14 screens; every panel calls the backend |
| Diff / patch viewer | SUPPORTED | `frontend/src/features/diff/diffStats.test.ts` | files, +/-, risk, scope, related tests, review findings |
| Excel import / export | SUPPORTED | `backend/tests/integration/test_reports_api.py` | workbook import with hard limits; `.xlsx` task + metrics export |
| Structured task report | SUPPORTED | `backend/tests/integration/test_reporting_acceptance_fixture.py` | 18-section report as JSON + xlsx rendering |
| Benchmark framework | SUPPORTED (harness) | `backend/tests/integration/test_benchmark_pipeline.py` | evaluation harness for the 16 metrics + capability spike; a productized *service* is post-MVP |
| Competitive baseline (#15) | PARTIALLY_SUPPORTED | `docs/EVAL_HARNESS.md` | harness runs reference agents on the identical task set; no live reference results yet (metric #15 N/A) |
| Cost / latency budgets | SUPPORTED | `backend/tests/e2e/test_full_pipeline.py` | enforced by the Orchestrator; metrics #13/#14 |
| Reliability (limits / GC / breakers) | SUPPORTED | `backend/tests/integration/test_queue_backpressure_api.py` | §37 limits → `PARTIALLY_SUPPORTED`; artifact GC; AI/GitHub circuit breakers; `/readyz` + `/metrics` |

---

## 3. Configurable limits (Spec §37)

All configurable; exceeding any yields `PARTIALLY_SUPPORTED{reason}`, never a crash, never silent
truncation without provenance: repository size, file count, individual file size, Git history
depth, analysis duration, generated-test count, AI context size, code-graph nodes, patch-candidate
count, sandbox runtime / memory / CPU. Defaults live in `backend/app/core/limits.py` +
`backend/app/core/config.py` and are tabulated in `EXECUTION_MODEL.md` §6. Enforcement is
exercised by `backend/tests/integration/test_analysis_budget.py` and
`backend/tests/integration/test_ingest_oversized.py`.

---

## 4. Acceptance criteria (Spec §54)

The 30 criteria, each mapped to satisfying code and a demonstrating test, are in
[`ACCEPTANCE_CONTRACT.md`](ACCEPTANCE_CONTRACT.md) (Part 1). The §55 absolute-rules audit is
Part 2 of the same document. Both are checked by
`backend/tests/docs/test_acceptance_contract.py`.

---

## 5. Post-MVP polish (kept in the plan for full Spec coverage)

- **Multi-language** analysis — seam only; no language beyond Python is claimed.
- A **distributed / parallel worker** — the MVP worker is single sequential (ADR-0003).
- **`limit_graph_nodes`** enforcement — configuration only; no partial-graph fallback yet.
- A **container-image registry / publish pipeline** for the sandbox image (ADR-0010).
- A productized **benchmark service** beyond the evaluation harness.
- **Live-provider** runs of the capability spike and the acceptance contract.
