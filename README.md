# AEGIS

**A**utonomous **E**ngineering, **G**eneration, **I**ntelligence & **S**elf-Repair **S**ystem —
an autonomous AI software-engineering platform that takes a real development task and a Git
repository and drives it through a verified, evidence-backed change: understand the repo, map the
issue to code, plan, implement, test, execute securely, debug, review, score, verify, and
optionally open a PR.

Working name; see `docs/POSITIONING.md` for the strategic thesis and wedge.

**Status: all 28 phases implemented — feature-complete MVP.** AEGIS takes a real engineering
task and a real Git repository and drives it through the full connected pipeline to a verified,
evidence-backed diff, with local Git output, an external GitHub PR when credentials and policy
permit, a React dashboard, and Excel / structured reporting. The `backend/app/` FastAPI service
covers every stage; `backend/aegis/` is the original walking skeleton kept as an executable
reference. See [`CHANGELOG.md`](CHANGELOG.md) for what each phase delivered and
[`docs/ACCEPTANCE_CONTRACT.md`](docs/ACCEPTANCE_CONTRACT.md) for the 30-point acceptance contract
with linked evidence.

Known caveats: the Docker sandbox happy path and the Phase 0 capability spike have not been run
against a live daemon / live AI provider in this environment (degradation to
`PARTIALLY_SUPPORTED` *is* verified); the job worker is single sequential. Details in
`docs/ACCEPTANCE_CONTRACT.md` → "Open items".

---

## Documentation index

**Plan**
- [`docs/AEGIS_IMPLEMENTATION_PLAN.md`](docs/AEGIS_IMPLEMENTATION_PLAN.md) ([PDF](docs/AEGIS_IMPLEMENTATION_PLAN.pdf)) — the full phase-by-phase implementation plan, testing strategy, delivery strategy, and appendices.

**Guides**
- [`docs/USER_GUIDE.md`](docs/USER_GUIDE.md) — submitting tasks, reading results, task states, approvals.
- [`docs/OPERATOR_GUIDE.md`](docs/OPERATOR_GUIDE.md) — processes, the full `AEGIS_*` config reference, health/metrics, backups.
- [`docs/DEVELOPER_GUIDE.md`](docs/DEVELOPER_GUIDE.md) — repo layout, the phase/migration model, the docs-CI gates.
- [`docs/RUNBOOKS.md`](docs/RUNBOOKS.md) — incident playbooks (provider outage, sandbox down, queue full, stuck job, GC, migrations, secrets).
- [`docs/API_REFERENCE.md`](docs/API_REFERENCE.md) — generated from the live OpenAPI schema.
- [`docs/ACCEPTANCE_CONTRACT.md`](docs/ACCEPTANCE_CONTRACT.md) — the 30 §54 criteria + the 20 §55 rules, each with linked evidence.
- [`docs/DEMO.md`](docs/DEMO.md) — a 5-minute walkthrough.
- [`CHANGELOG.md`](CHANGELOG.md) — release history by phase.

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
docs/                    architecture, strategic, decision docs; the user/operator/developer guides
scripts/
  gen_api_reference.py   regenerates docs/API_REFERENCE.md from the app's OpenAPI schema
  quickstart_check.py    non-Docker end-to-end smoke test (a CI gate)
  build_plan_pdf.py      renders the implementation plan to PDF
  capability_spike/      throwaway harness for the Stage A capability gate
backend/
  aegis/                 the original walking skeleton: ingest -> analyze -> ... -> verify
                         (kept as an executable reference; not imported by app/)
  app/                   the service: api/, services/, agents/, ai/, analysis/, implementation/,
                         testing/, sandbox/, debugging/, review/, scoring/, verification/, git/,
                         github/, memory/, orchestration/, core/, models/ (34 tables), db/migrations/
  tests/                 unit/ integration/ e2e/ security/ perf/ docs/
docker/                  sandbox.Dockerfile, api.Dockerfile, frontend.Dockerfile
docker-compose.yml       dev stack: api, worker, frontend, optional postgres (requires Docker)
frontend/                Vite + React + TS dashboard (14 screens; every panel calls the backend)
test-repositories/
  aegis-acceptance/      the seeded acceptance task (Specification §39's worked example)
  aegis-acceptance-unfixable/   exercises the bounded repair loop's clean-stop path
.github/workflows/ci.yml backend (ruff/black/mypy/pytest/coverage/migrations/quickstart) +
                         security (bandit/pip-audit/SBOM) + frontend (eslint/tsc/vitest/build)
```

## Quickstart

The whole pipeline, end to end, no Docker and no services:

```
cd backend && pip install -e .[dev]
python ../scripts/quickstart_check.py        # ingest -> ... -> verify -> COMPLETED, prints PASS
pytest -q                                     # the full test suite
```

See [`docs/DEMO.md`](docs/DEMO.md) for the same thing over the API + dashboard, and
[`docs/USER_GUIDE.md`](docs/USER_GUIDE.md) for submitting your own task.

## Local development

Full setup, migrations, Docker Compose, and lint/type/test commands are in `CONTRIBUTING.md`.
Quick start for the API + frontend:

```
cd backend && pip install -e .[dev] && alembic upgrade head && uvicorn app.main:app --reload
```
```
cd frontend && npm install && cp .env.example .env && npm run dev
```
or the whole stack at once (**requires Docker**; not exercised in CI):
```
cp .env.example .env && docker compose up
```

## Regenerating docs

```
python scripts/gen_api_reference.py --write    # docs/API_REFERENCE.md from OpenAPI
python scripts/build_plan_pdf.py               # docs/AEGIS_IMPLEMENTATION_PLAN.pdf
```

## Running the capability-spike harness (mock)

```
python scripts/capability_spike/run.py --provider mock --tasks scripts/capability_spike/tasks.example.yaml
```

## License

Apache License 2.0 — see [`LICENSE`](LICENSE) and [`NOTICE`](NOTICE).
