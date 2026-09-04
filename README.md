# AEGIS

**A**utonomous **E**ngineering, **G**eneration, **I**ntelligence & **S**elf-Repair **S**ystem —
an autonomous AI software-engineering platform that takes a real development task and a Git
repository and drives it through a verified, evidence-backed change: understand the repo, map the
issue to code, plan, implement, test, execute securely, debug, review, score, verify, and
optionally open a PR.

Working name; see `docs/POSITIONING.md` for the strategic thesis and wedge.

**Status: Phase 0 (Greenfield Architecture & Planning) — COMPLETE.** Next: Phase 1 (Walking
Skeleton). See `docs/AEGIS_IMPLEMENTATION_PLAN.md` for the full phase-by-phase plan.

---

## Documentation index

**Plan**
- [`docs/AEGIS_IMPLEMENTATION_PLAN.md`](docs/AEGIS_IMPLEMENTATION_PLAN.md) ([PDF](docs/AEGIS_IMPLEMENTATION_PLAN.pdf)) — the full phase-by-phase implementation plan, testing strategy, delivery strategy, and appendices.

**Architecture (Specification §46)**
- [`docs/AEGIS_ARCHITECTURE.md`](docs/AEGIS_ARCHITECTURE.md) — system architecture, module boundaries, agent orchestration, state machine.
- [`docs/TECH_STACK.md`](docs/TECH_STACK.md) — technology choices and rationale.
- [`docs/DATA_MODEL.md`](docs/DATA_MODEL.md) — the 28-entity data model.
- [`docs/SECURITY_MODEL.md`](docs/SECURITY_MODEL.md) — threat model, sandbox controls, RBAC.
- [`docs/MVP_DEFINITION.md`](docs/MVP_DEFINITION.md) — SUPPORTED / PARTIALLY_SUPPORTED / UNSUPPORTED matrix.
- [`docs/AI_AGENT_DESIGN.md`](docs/AI_AGENT_DESIGN.md) — the 7 agents, AI provider abstraction, the 18 AI schemas.
- [`docs/METRICS.md`](docs/METRICS.md) — the 16 objective metrics and the scoring algorithms.
- [`docs/EXECUTION_MODEL.md`](docs/EXECUTION_MODEL.md) — job model, sandbox execution flow, limits.
- [`docs/REPOSITORY_ANALYSIS.md`](docs/REPOSITORY_ANALYSIS.md) — ingestion, AST analysis, code graph, issue→code retrieval.

**Strategic (plan additions)**
- [`docs/POSITIONING.md`](docs/POSITIONING.md) — wedge, non-goals, competitive landscape, kill criteria.
- [`docs/COST_MODEL.md`](docs/COST_MODEL.md) — per-task cost envelope, model routing, CI budget bands.
- [`docs/GOVERNANCE.md`](docs/GOVERNANCE.md) — deterministic replay, audit chain, RBAC, Trust Report.
- [`docs/EVAL_HARNESS.md`](docs/EVAL_HARNESS.md) — benchmark datasets, reference agents, calibration protocol.

**Decisions**
- [`docs/DECISIONS/`](docs/DECISIONS/) — 20 Architecture Decision Records.

**Phase 0 artifacts**
- [`docs/PHASE0_CHECKLIST.md`](docs/PHASE0_CHECKLIST.md) — coverage of all 28 Specification §46 items.
- [`docs/CAPABILITY_SPIKE.md`](docs/CAPABILITY_SPIKE.md) — the Stage A capability gate (G0); live run pending.

## Repository layout

```
docs/                 architecture, strategic, and decision documents (this Phase 0's output)
scripts/
  build_plan_pdf.py       renders the implementation plan to PDF
  capability_spike/       throwaway harness for the Stage A capability gate (see its README)
backend/, frontend/       not yet created — begin in Phase 1 / Phase 2
```

## Quickstart

Not yet available — the runnable system begins with Phase 1 (walking skeleton). Once it lands,
this section will show `docker compose up` and a first task run.

## Regenerating the plan PDF

```
python scripts/build_plan_pdf.py
```

## Running the capability-spike harness (mock)

```
python scripts/capability_spike/run.py --provider mock --tasks scripts/capability_spike/tasks.example.yaml
```
