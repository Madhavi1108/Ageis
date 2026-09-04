# AEGIS

**A**utonomous **E**ngineering, **G**eneration, **I**ntelligence & **S**elf-Repair **S**ystem —
an autonomous AI software-engineering platform that takes a real development task and a Git
repository and drives it through a verified, evidence-backed change: understand the repo, map the
issue to code, plan, implement, test, execute securely, debug, review, score, verify, and
optionally open a PR.

Working name; see `docs/POSITIONING.md` for the strategic thesis and wedge.

**Status: Phase 0 (Greenfield Architecture & Planning) and Phase 1 (Walking Skeleton) — COMPLETE.**
The CLI runs a real task end-to-end to a **VERIFIED** diff (`--sandbox fake`); with the real Docker
sandbox (the default), it correctly reports `PARTIALLY_SUPPORTED` in this Docker-less environment
rather than falling back to host execution. Next: Phase 2 (Project Foundation — the real FastAPI
app, DB, and CI). See `docs/AEGIS_IMPLEMENTATION_PLAN.md` for the full phase-by-phase plan.

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
docs/                    architecture, strategic, and decision documents (Phase 0's output)
scripts/
  build_plan_pdf.py       renders the implementation plan to PDF
  capability_spike/       throwaway harness for the Stage A capability gate (see its README)
backend/                  the Phase 1 Walking Skeleton (real code) -- see backend/aegis/
  aegis/                  ingest -> analyze -> map -> plan -> implement -> test -> repair -> verify
  tests/unit/, tests/e2e/ 47 tests, 1 Docker-gated (auto-skips without a daemon)
docker/
  sandbox.Dockerfile      the walking skeleton's sandbox image (build before using --sandbox docker)
test-repositories/
  aegis-acceptance/       the seeded acceptance task (Specification §39's worked example)
  fixtures/unfixable/     exercises the bounded repair loop's clean-stop path
frontend/                 not yet created -- later phases
```

## Quickstart

```
cd backend && pip install -e .[dev]
python -m aegis.skeleton run ../test-repositories/aegis-acceptance ../test-repositories/aegis-acceptance/task.md --sandbox fake
```

`--sandbox fake` runs tests as a local subprocess so the full pipeline is demonstrable without
Docker (only ever use it against trusted fixtures, never a real repository). Build
`docker/sandbox.Dockerfile` and drop `--sandbox fake` (the default is `docker`) to use the real,
hardened sandbox.

```
pytest backend/tests -q
```

## Regenerating the plan PDF

```
python scripts/build_plan_pdf.py
```

## Running the capability-spike harness (mock)

```
python scripts/capability_spike/run.py --provider mock --tasks scripts/capability_spike/tasks.example.yaml
```
