# AEGIS MVP Definition

Traceability: Specification §38, §54. Phase 0 deliverable (Spec §46 item 27). Companion to
`AEGIS_IMPLEMENTATION_PLAN.md` §7.3 (spine / thicken / harden / deferred) and Appendix C.

Status: Accepted — 2026-09-04. The support matrix is re-verified against passing tests in Phase 28.

---

## 1. MVP scope statement

The MVP takes a well-specified engineering task plus a **Python** Git repository and autonomously
produces a **verified, evidence-backed, review-ready change** — through the full connected pipeline
— with local Git output and a task-pipeline dashboard view. It does **not** include external
GitHub PR creation, the full 14-screen dashboard, Excel, multi-language support, or a productized
benchmark service; those are scheduled immediately after the MVP.

Phases in the MVP: 0–19 (0 planning, 1 walking skeleton, 2–19 the sequential build-out through
Verification and local Git), 20 (basic), 21, 22 (task-pipeline view only), 24, 26, 27, 28.

---

## 2. Support matrix (Spec §38)

Status values: **SUPPORTED** (implemented + executed + tested + integrated + verified),
**PARTIALLY_SUPPORTED** (works within stated limits; returns a structured reason beyond them),
**UNSUPPORTED** (not in the MVP; architecture leaves the seam).

| Capability | MVP status | Notes |
|---|---|---|
| Git repositories | SUPPORTED | local path + GitHub HTTPS URL |
| Python repositories | SUPPORTED | primary target; `ast` + `tree-sitter` resilience |
| JS / TS / Java / Go / C++ | UNSUPPORTED | analysis seam exists (`tree-sitter`); no claims until implemented |
| Local repo ingestion | SUPPORTED | inside configured root paths |
| GitHub repo ingestion | SUPPORTED | public; authenticated when a token is configured |
| Python AST analysis | SUPPORTED | symbols, imports, signatures, entry points, test infra |
| Dependency analysis | SUPPORTED | import edges + package requirements; classification incl. `UNKNOWN` |
| Git history analysis | SUPPORTED | blame, churn, related-fix detection, the four history questions |
| Code graph | SUPPORTED | NetworkX + adjacency; call edges labelled RESOLVED/HEURISTIC/UNRESOLVED |
| Issue -> code mapping | SUPPORTED | lexical + graph + history + memory; semantic PARTIALLY_SUPPORTED |
| Semantic retrieval in mapping | PARTIALLY_SUPPORTED | requires an embeddings provider; lexical+graph fallback with reduced confidence |
| Impact analysis | SUPPORTED | blast radius, callers, related tests, public API; config/db refs labelled INFERENCE |
| Engineering planning | SUPPORTED | AI plan + rule-based fallback when no provider |
| Plan validation | SUPPORTED | schema + feasibility + scope + evidence gate |
| Real code modification | SUPPORTED | anchored edits, unified diff, reversible, scope-tracked |
| Test generation | SUPPORTED | framework-mirroring; boundary + negative per changed public fn |
| Secure sandbox execution | SUPPORTED | Docker; `PARTIALLY_SUPPORTED` if Docker absent |
| Failure analysis | SUPPORTED | traceback parse, frame->symbol, deterministic classification |
| Autonomous repair | SUPPORTED | bounded loop, auto-revert, safe stop with evidence |
| Regression testing | SUPPORTED | smart selection + full suite; full-suite gates completion |
| Code review | SUPPORTED | static + custom AST rules + AI reviewer, 10 categories |
| Risk score (CRS) | SUPPORTED | deterministic, versioned, explained (`scoring-model v1.0.0`, provisional constants) |
| Confidence score (PCS) | SUPPORTED | same; hard gates |
| Repository health profile | SUPPORTED | per-repo + task-specific risk profile |
| Verification | SUPPORTED | mandatory-criteria checklist; engineering trace; no false-complete on negatives |
| Deterministic replay | PARTIALLY_SUPPORTED | fidelity depends on provider seed support; disclosed in the Trust Report |
| Engineering memory | SUPPORTED (basic) | write on terminal state; lexical + symbol retrieval; embeddings optional |
| Local Git branch / commit | SUPPORTED | in the workspace |
| GitHub PR creation | PARTIALLY_SUPPORTED | local PR artifact always; real PR only when write creds + policy permit; **write-automation polish is post-MVP** |
| FastAPI API | SUPPORTED | all endpoint groups; OpenAPI; RBAC; pagination |
| Job orchestration | SUPPORTED | states, retries, cancellation, crash recovery, concurrency cap |
| Dashboard | PARTIALLY_SUPPORTED | task-pipeline view with real data; full 14 screens post-MVP |
| Diff / patch viewer | SUPPORTED | files, +/-, risk, scope, related tests, review findings |
| Excel import / export | UNSUPPORTED (MVP) | scheduled immediately post-MVP (Phase 23); shares domain services when built |
| Structured task report | SUPPORTED | 18-section report as JSON (xlsx rendering post-MVP) |
| Benchmark framework | PARTIALLY_SUPPORTED | evaluation harness for the 16 metrics + capability spike; productized service is post-MVP |
| Competitive baseline (#15) | SUPPORTED (harness) | runs reference agents on the identical task set |
| Cost / latency budgets | SUPPORTED | enforced by the Orchestrator; metrics #13/#14 |
| Persistent engineering memory across tasks | SUPPORTED | provenance-labelled evidence, never auto-applied |

---

## 3. Configurable limits (Spec §37)

All configurable; exceeding any yields `PARTIALLY_SUPPORTED{reason}`, never a crash, never silent
truncation without provenance: repository size, file count, individual file size, Git history
depth, analysis duration, generated-test count, AI context size, patch-candidate count, sandbox
runtime / memory / CPU. Defaults live in `core/limits.py` and `EXECUTION_MODEL.md` §6.

---

## 4. Acceptance criteria -> phase (Spec §54)

| # | Criterion | Phase |
|---|---|---|
| 1 | A real repository can be ingested | 2 |
| 2 | Repository structure can be analyzed | 3 |
| 3 | Symbols and dependencies can be identified | 3, 4 |
| 4 | Git history can be analyzed | 18 |
| 5 | A real issue can be submitted | 5 |
| 6 | Relevant code can be identified | 6 |
| 7 | Evidence-backed impact analysis can be generated | 7 |
| 8 | A structured engineering plan can be created | 8 |
| 9 | The plan can be validated | 8 |
| 10 | Real code can be modified | 9 |
| 11 | Tests can be generated | 10 |
| 12 | Tests can execute in a sandbox | 11 |
| 13 | Failures can be detected | 11, 12 |
| 14 | Root causes can be investigated | 12, 13 |
| 15 | Repair attempts can be performed | 13 |
| 16 | Regression tests can execute | 14 |
| 17 | Generated changes can be reviewed | 15 |
| 18 | Scope violations can be detected | 9, 15, 17 |
| 19 | Risk can be calculated | 16 |
| 20 | Confidence can be calculated | 16 |
| 21 | Final verification can be performed | 17 |
| 22 | A real patch / diff can be produced | 9 |
| 23 | Git branch / commit can be created | 18 |
| 24 | GitHub PR can be created when credentials permit | 18 |
| 25 | Engineering memory can persist the task | 19 |
| 26 | Dashboard can show the actual workflow | 21 |
| 27 | FastAPI exposes the workflow | 1, 20 |
| 28 | Excel reports use real backend data | 22 (post-MVP) |
| 29 | Failures are handled safely | 13, 25, 26 |
| 30 | No fake functionality is used | cross-cutting; enforced by tests every phase |

---

## 5. Explicitly out of MVP (kept in the plan for full Spec coverage)

- GitHub PR **write-automation** polish (creation flow, branch-conflict UX) — Phase 19 tail.
- The full **14-screen dashboard** — Phase 22 tail; MVP ships the task-pipeline view.
- **Excel** import/export and xlsx report rendering — Phase 23.
- **Multi-language** analysis — post-MVP; seam only.
- **Benchmark productization** beyond the evaluation harness — Phase 25 tail.
