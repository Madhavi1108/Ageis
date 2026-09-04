# Phase 0 Coverage Checklist

Traceability: Specification §46 (Phase 0 must explicitly define 28 items). This checklist proves
each is addressed by a Phase 0 document section. Zero "gap" rows at exit.

Status: COMPLETE — 2026-09-04.

---

## 1. The 28 required definitions (Spec §46)

| # | Item (Spec §46) | Addressed in | Status |
|---|---|---|---|
| 1 | System architecture | `AEGIS_ARCHITECTURE.md` §2–§4, §9 | DONE |
| 2 | Module boundaries | `AEGIS_ARCHITECTURE.md` §3; `TECH_STACK.md` §1 | DONE |
| 3 | Database schema | `DATA_MODEL.md` (all); `ADR-0001` | DONE |
| 4 | Workflow state machine | `AEGIS_ARCHITECTURE.md` §6; `EXECUTION_MODEL.md` §2–§3; `ADR-0002` | DONE |
| 5 | Artifact storage | `DATA_MODEL.md` §4; `EXECUTION_MODEL.md`; `ADR-0009` | DONE |
| 6 | Sandbox threat model | `SECURITY_MODEL.md` §2; `ADR-0010`; `EXECUTION_MODEL.md` §4–§5 | DONE |
| 7 | AI provider abstraction | `AI_AGENT_DESIGN.md` §3–§4; `ADR-0005`, `ADR-0019` | DONE |
| 8 | Agent responsibilities | `AI_AGENT_DESIGN.md` §2; `AEGIS_ARCHITECTURE.md` §5; `ADR-0004` | DONE |
| 9 | AI schemas | `AI_AGENT_DESIGN.md` §6–§7 (the 18 schemas + `Evidence`/`Confidence`) | DONE |
| 10 | Repository ingestion model | `REPOSITORY_ANALYSIS.md` §1; `ADR-0006` | DONE |
| 11 | Issue -> code retrieval strategy | `REPOSITORY_ANALYSIS.md` §5; `METRICS.md` §4 (`mapping-model v1.0.0`) | DONE |
| 12 | Dependency graph | `REPOSITORY_ANALYSIS.md` §4; `ADR-0007`; Spec §22 | DONE |
| 13 | Planning model | `AI_AGENT_DESIGN.md` §2, §7 (`EngineeringPlan`, `PlanValidation`); plan §16 | DONE |
| 14 | Patch model | `ADR-0008`; `DATA_MODEL.md` §2.2 (`Patch`, `Implementation`) | DONE |
| 15 | Testing model | `ADR-0013`; `AEGIS_IMPLEMENTATION_PLAN.md` Phases 11, 15 | DONE |
| 16 | Debugging loop | `AI_AGENT_DESIGN.md` §2, §5; `EXECUTION_MODEL.md` §6 (bounds); plan Phase 14 | DONE |
| 17 | Review model | `DATA_MODEL.md` §2.4 (`ReviewFinding` 10 categories, 5 severities); plan Phase 16 | DONE |
| 18 | Verification model | `AI_AGENT_DESIGN.md` §2; `GOVERNANCE.md` §6 (Trust Report); plan Phase 18 | DONE |
| 19 | Memory architecture | `ADR-0016`; `DATA_MODEL.md` §2.4 (`EngineeringMemory`) | DONE |
| 20 | GitHub integration | `ADR-0015`; `MVP_DEFINITION.md` §2 | DONE |
| 21 | API architecture | `AEGIS_ARCHITECTURE.md` §3 (`api/`), §8; `TECH_STACK.md` §1; plan Phase 21 | DONE |
| 22 | Frontend architecture | `ADR-0018`; `MVP_DEFINITION.md` §2; plan Phase 22 | DONE |
| 23 | Excel architecture | `MVP_DEFINITION.md` §2, §5 (post-MVP, shares domain services); plan Phase 23 | DONE (scoped) |
| 24 | Job / concurrency model | `EXECUTION_MODEL.md` §1–§3; `ADR-0003` | DONE |
| 25 | Repository limits | `EXECUTION_MODEL.md` §5–§6; `ADR-0012` | DONE |
| 26 | Scoring algorithms | `METRICS.md` §2 (`scoring-model v1.0.0`); `ADR-0017` | DONE |
| 27 | MVP boundaries | `MVP_DEFINITION.md` (all); `AEGIS_IMPLEMENTATION_PLAN.md` §7.3 | DONE |
| 28 | Acceptance tests | `MVP_DEFINITION.md` §4; `AEGIS_IMPLEMENTATION_PLAN.md` Appendix C; plan Phase 24 | DONE |

---

## 2. Early architectural decisions (Spec §51) — ADR coverage

All 18 Spec §51 items have an ADR, plus two plan-addition ADRs:

`ADR-0001` database schema · `ADR-0002` analysis state machine · `ADR-0003` job model ·
`ADR-0004` agent orchestration · `ADR-0005` AI provider abstraction · `ADR-0006` repository
abstraction · `ADR-0007` code-analysis abstraction · `ADR-0008` patch representation ·
`ADR-0009` artifact storage · `ADR-0010` sandbox architecture · `ADR-0011` security policy ·
`ADR-0012` repository limits · `ADR-0013` test execution model · `ADR-0014` Git strategy ·
`ADR-0015` GitHub strategy · `ADR-0016` memory architecture · `ADR-0017` metric algorithms ·
`ADR-0018` frontend state model · `ADR-0019` model routing (plan addition) ·
`ADR-0020` capability floors (plan addition).

---

## 3. Phase 0 deliverable inventory

| Deliverable | File(s) | Status |
|---|---|---|
| Implementation plan (phase-by-phase + testing) | `AEGIS_IMPLEMENTATION_PLAN.md` (+ `.pdf`) | DONE (prior work) |
| Architecture | `AEGIS_ARCHITECTURE.md` | DONE |
| Tech stack | `TECH_STACK.md` | DONE |
| Data model | `DATA_MODEL.md` | DONE |
| Security model | `SECURITY_MODEL.md` | DONE |
| MVP definition | `MVP_DEFINITION.md` | DONE |
| AI & agent design | `AI_AGENT_DESIGN.md` | DONE |
| Metrics & scoring | `METRICS.md` | DONE |
| Execution model | `EXECUTION_MODEL.md` | DONE |
| Repository analysis | `REPOSITORY_ANALYSIS.md` | DONE |
| Positioning | `POSITIONING.md` | DONE |
| Cost model | `COST_MODEL.md` | DONE |
| Governance | `GOVERNANCE.md` | DONE |
| Evaluation harness | `EVAL_HARNESS.md` | DONE |
| ADRs | `DECISIONS/README.md` + `ADR-0001..0020.md` | DONE (20) |
| Capability spike | `CAPABILITY_SPIKE.md` + `scripts/capability_spike/` | HARNESS DONE (mock); LIVE RUN PENDING |
| This checklist | `PHASE0_CHECKLIST.md` | DONE |

---

## 4. Exit status

- All 28 Spec §46 definitions: **addressed**, zero gap rows.
- All 18 Spec §51 decisions: **ADR present** (+ 2 plan-addition ADRs).
- `scoring-model v1.0.0`, `mapping-model v1.0.0`, `pricing-table v1.0.0`: **frozen, provisional**,
  calibrated in Phase 25.
- Capability spike (Stage A / gate G0): **harness runs on mock**; the live run against a real
  provider + the ~30-task benchmark subset + Docker is **PENDING** — see `CAPABILITY_SPIKE.md`.
  Per the plan, Phase 1 (walking skeleton) may begin; G0 must be evaluated with live numbers
  before broad breadth work.
