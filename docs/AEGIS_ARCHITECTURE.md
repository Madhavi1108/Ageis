# AEGIS Architecture

Traceability: Specification §2, §4, §5, §19, §45, §52, §53. Phase 0 deliverable (Spec §46 item 1,
2, 4, 8). Companion to `AEGIS_IMPLEMENTATION_PLAN.md` §3–§4.

Status: Accepted — 2026-09-04. Provisional items are labelled inline.

---

## 1. Purpose and scope

This document fixes the system architecture, module boundaries, the agent-orchestration model, and
the workflow state machine for AEGIS. It is the reference every later phase builds against. It does
not restate the full cross-cutting foundations — those live in `AEGIS_IMPLEMENTATION_PLAN.md` §4 and
in the topic documents (`DATA_MODEL.md`, `SECURITY_MODEL.md`, `EXECUTION_MODEL.md`,
`AI_AGENT_DESIGN.md`, `REPOSITORY_ANALYSIS.md`).

---

## 2. System context and trust boundaries

```
        +-------------------+        +--------------------------+
        |  Human / API      |        |  GitHub (optional)       |
        |  Excel import     |        |  issues / repos / PRs    |
        +---------+---------+         +------------+-------------+
                  |                                |
            (untrusted input)               (untrusted content)
                  v                                v
        +====================================================+
        |                A E G I S  (trusted)                |
        |                                                    |
        |  API  ->  Orchestrator  ->  Agents  ->  Engines    |
        |                    |                               |
        |                    v                               |
        |            Docker sandbox  <---- target repo code  |
        |            (untrusted execution)                   |
        +====================================================+
                  |                                |
                  v                                v
        +-------------------+        +--------------------------+
        |  DB (SQLite/PG)   |        |  Artifact store (fs)     |
        +-------------------+        +--------------------------+
```

Trust rules (enforced everywhere; see `SECURITY_MODEL.md`):

- **AEGIS code and its database are trusted.**
- **Target repositories are untrusted.** Their files, Git metadata, tests, configuration, and any
  code AEGIS generates for them are hostile input until proven safe. They are only ever executed
  inside the Docker sandbox.
- **AI provider outputs are untrusted** until schema-validated and evidence-checked. Execution
  results always outrank AI assertions.
- **Issue / task text is untrusted.** It is never concatenated into a system prompt; only
  structured, sanitized fields reach the model.

---

## 3. Module boundaries (`backend/app/*`)

| Package | Responsibility | May depend on |
|---|---|---|
| `core/` | config, logging + redaction, error envelope, security primitives, limits, ids | (nothing internal) |
| `db/` | engine/session, `Base`, Alembic wiring | `core` |
| `models/` | SQLAlchemy models (see `DATA_MODEL.md`) | `db`, `core` |
| `schemas/` | Pydantic request/response + the 18 AI output schemas | `core` |
| `repository/` | ingestion, workspace, git client, URL validation, limits | `models`, `schemas`, `core` |
| `analysis/` | Python AST, symbols, imports, project meta, `graph/`, `impact`, `mapping/` | `repository`, `models`, `schemas`, `core` |
| `ai/` | `AIProvider` abstraction + implementations, prompt assembly, schema guard | `schemas`, `core` |
| `agents/` | the 7 agents; pure orchestration of engines + `ai` | `analysis`, `ai`, `implementation`, `testing`, `debugging`, `review`, `verification`, `schemas` |
| `implementation/` | RW workspace, anchored editor, patcher, scope tracker | `repository`, `schemas`, `core` |
| `testing/` | test generator, selector, regression selection, catalog | `analysis`, `sandbox`, `schemas` |
| `debugging/` | investigate, RCA, hypotheses, bounded repair loop, guard | `analysis`, `implementation`, `sandbox`, `ai`, `schemas` |
| `review/` | static checks, custom AST rules, AI review, aggregation | `implementation`, `ai`, `schemas` |
| `verification/` | criteria evaluators, plan-alignment, verdict, trace | `testing`, `review`, `scoring`, `schemas` |
| `scoring/` | PCS, CRS, RHP, model registry | `analysis`, `schemas`, `core` |
| `memory/` | engineering-memory store, index, retrieval | `models`, `schemas`, `ai` (embed only) |
| `github/` | GitHub client/provider, PR builder | `schemas`, `core` |
| `sandbox/` | docker backend, policy, resource limits, result parser | `core` |
| `reporting/` | Excel import/export, report builder, Trust Report | domain services only |
| `orchestration/` | orchestrator, job queue, worker, state machine | everything above |
| `api/` | FastAPI routers, one per endpoint group | `orchestration`, `schemas`, `core` |

**Dependency direction:** `api` -> `orchestration` -> `agents` -> engines -> `core`. No cycles.
Agents do not call each other; the Orchestrator sequences them.

---

## 4. Component map

| Layer | Components |
|---|---|
| Entry | FastAPI API; Excel import/export; optional GitHub issue intake |
| Orchestration | Orchestrator (owns workflow state); Job queue + Worker; Workflow state machine |
| Agents | Repository Analyst · Planning · Implementation · Testing · Debugging · Code Review · Verification |
| Engines | Repository intelligence (AST); Code graph (NetworkX); Issue->Code mapping; Impact analysis; Regression selection; Scoring (PCS/CRS/RHP); Reporting |
| Platform | `AIProvider` abstraction; Docker sandbox; Git/GitHub clients; Artifact store; Engineering memory; Observability |
| Persistence | SQLAlchemy models on SQLite (dev) / PostgreSQL-compatible schema |
| Frontend | React + TS + Vite dashboard (MVP: task-pipeline view; full 14 screens post-MVP) |

---

## 5. Multi-agent orchestration model (Spec §4, §5)

A **small, fixed** set of seven specialized agents coordinated by a central **Orchestrator** that
owns workflow state. Agents communicate only through typed schemas (`schemas/`), never free text.

```
                         ORCHESTRATOR  (owns state, sequences agents, enforces budgets)
                                |
   +------------+------------+--+---------+------------+------------+------------+
   |            |            |            |            |            |            |
 Repository  Planning   Implementation  Testing    Debugging    Code Review  Verification
 Analyst      Agent       Agent          Agent       Agent        Agent        Agent
   |            |            |            |            |            |            |
   +------------+------------+------------+------------+------------+------------+
                                |
                          Engineering Memory  (read before planning/mapping; write at terminal state)
```

| Agent | Consumes | Produces | Failure behaviour |
|---|---|---|---|
| Repository Analyst | snapshot | `RepositoryAnalysis` / `RepositoryContext` | unparseable file recorded, analysis continues |
| Planning | `RepositoryContext`, `IssueCodeMapping`, `ImpactAnalysis` | `EngineeringPlan` + `PlanValidation` | invalid schema -> one repair round -> `FAILED`; no provider -> rule-based fallback plan (LOW confidence) |
| Implementation | approved `EngineeringPlan` | `ImplementationResult` (+ `Patch`) | ambiguous anchor -> stop loudly; out-of-scope write -> blocked event |
| Testing | plan, changed symbols, framework profile | `TestGeneration` (+ `TestCase`s) | uncollectable test -> `INVALID`, one repair round |
| Debugging | `FailureAnalysis`, diff, graph | `RootCauseAnalysis`, `RepairProposal`, `RepairAttempt`s | bounded loop; safe stop with evidence if unresolved |
| Code Review | `Patch`, tests | `ReviewFinding[]` / `ReviewReport` | AI finding without a line -> downgraded to `INFO` |
| Verification | everything above | `VerificationResult` + engineering trace | any mandatory criterion fails -> `NOT_VERIFIED` |

Full agent detail: `AI_AGENT_DESIGN.md`.

---

## 6. Workflow state machine (Spec §19, §36)

States: `PENDING`, `QUEUED`, `INGESTING`, `ANALYZING`, `PLANNING`, `PLAN_VALIDATION`,
`IMPLEMENTING`, `GENERATING_TESTS`, `EXECUTING_TESTS`, `INVESTIGATING`, `REPAIRING`,
`REGRESSION_TESTING`, `REVIEWING`, `VERIFYING`, `AWAITING_APPROVAL`, `COMPLETED`, `FAILED`,
`CANCELLED`, `PARTIALLY_SUPPORTED`.

| From | To (allowed) | Trigger |
|---|---|---|
| PENDING | QUEUED, CANCELLED | run requested / cancelled |
| QUEUED | INGESTING, CANCELLED | worker picks up job |
| INGESTING | ANALYZING, FAILED, PARTIALLY_SUPPORTED, CANCELLED | repo cloned / limit hit / error |
| ANALYZING | PLANNING, FAILED, PARTIALLY_SUPPORTED, CANCELLED | analysis persisted |
| PLANNING | PLAN_VALIDATION, FAILED, CANCELLED | plan produced |
| PLAN_VALIDATION | IMPLEMENTING, PLANNING, AWAITING_APPROVAL, FAILED, CANCELLED | approved / revise / high-risk |
| IMPLEMENTING | GENERATING_TESTS, FAILED, CANCELLED | patch generated |
| GENERATING_TESTS | EXECUTING_TESTS, FAILED, CANCELLED | tests written |
| EXECUTING_TESTS | REGRESSION_TESTING, INVESTIGATING, FAILED, CANCELLED | pass / fail |
| INVESTIGATING | REPAIRING, FAILED, CANCELLED | failure analysed |
| REPAIRING | EXECUTING_TESTS, REGRESSION_TESTING, FAILED, CANCELLED | candidate applied / budget exhausted (safe stop) |
| REGRESSION_TESTING | REVIEWING, INVESTIGATING, FAILED, CANCELLED | regression clean / new failure |
| REVIEWING | VERIFYING, FAILED, CANCELLED | review complete |
| VERIFYING | COMPLETED, AWAITING_APPROVAL, FAILED, CANCELLED | verified / needs approval / not verified |
| AWAITING_APPROVAL | VERIFYING, COMPLETED, CANCELLED, FAILED | human decision |
| COMPLETED / FAILED / CANCELLED / PARTIALLY_SUPPORTED | (terminal) | — |

Every transition is explicit, guarded by the state machine module, persisted to `TaskStep` /
`Job`, and emitted to the task timeline. Illegal transitions raise and are rejected. Detailed job
mechanics (retries, recovery, concurrency) are in `EXECUTION_MODEL.md`.

---

## 7. The connectedness invariant (Spec §52)

AEGIS is a pipeline, not a bag of prompts. Each stage consumes the **typed, persisted output** of
the previous stage. Phase 21 ships an automated test asserting, for a completed task, that each
stage's input record is identical to the prior stage's output record — no stage re-derives facts,
no stage runs on unstructured text.

```
Issue -> TaskNormalization -> RepoIngestion -> RepoIntelligence -> CodeGraph -> Issue->CodeMapping
      -> ImpactAnalysis -> EngineeringPlan -> PlanValidation -> Implementation -> TestGeneration
      -> SecureExecution -> FailureAnalysis -> RootCause -> Repair(bounded) -> RegressionTesting
      -> CodeReview -> Scope+Security -> Risk+Confidence -> Verification -> Patch/PR -> Memory
```

---

## 8. Request / job / execution separation (Spec §19)

- **HTTP request:** validates input, creates or reads records, enqueues a job, returns fast. Never
  blocks on analysis, an agent, the sandbox, or an AI call.
- **Analysis job:** one per task run, owned by the Worker, drives the state machine through the
  Orchestrator, checkpoints after every phase for crash recovery.
- **Agent execution:** synchronous within a job step; its inputs/outputs/duration are recorded.
- **Sandbox execution:** a child `docker` process with resource caps and a wall-clock kill; only
  the sandbox ever runs target code.
- **AI request:** behind `AIProvider`; retried, timed out, budgeted, redacted-logged.

---

## 9. Deployment topology

```
docker-compose:
  api        (FastAPI + Uvicorn)         -> DB, artifact volume
  worker     (job runner)               -> DB, artifact volume, /var/run/docker.sock? NO
                                            -> talks to a dedicated sandbox Docker context
  frontend   (Vite build served static / dev server)
  postgres   (optional; SQLite file by default)
  sandbox    images built, not a long-running service; the worker starts short-lived containers
```

- The worker does **not** mount the host Docker socket into the API container. Sandbox containers
  are launched via a scoped Docker context / remote API with a restricted capability set (see
  `SECURITY_MODEL.md` §"Container escape").
- Artifact store is a mounted volume in dev; an object-store adapter is a post-MVP option.

---

## 10. Open questions (tracked, not blocking)

| # | Question | Resolution plan |
|---|---|---|
| A1 | asyncio worker vs a queue library (RQ/arq) at scale | `ADR-0003`; revisit in Phase 27 with soak data |
| A2 | betweenness centrality cost on large graphs | approximate + budget in Phase 5; measure Phase 27 |
| A3 | rootless Docker availability on target CI runners | Phase 2 sandbox spike; fall back to `PARTIALLY_SUPPORTED` |
| A4 | embeddings provider for semantic mapping | optional in Phase 7; local model fallback; decision after capability spike |
