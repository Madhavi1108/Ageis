# AEGIS Developer Guide

Audience: contributors. Quick setup lives in [`../CONTRIBUTING.md`](../CONTRIBUTING.md);
this covers how the codebase is organised and how not to break the CI gates.

Status: final — reconciled against the built system (Phases 0–28), 2026-09-09.

---

## 1. Repository layout

```
docs/                       architecture, strategic, and decision docs; the guides
  DECISIONS/                 ADR-0001 … ADR-0020
  AEGIS_IMPLEMENTATION_PLAN.md   the phase-by-phase plan (source of truth for scope)
scripts/
  build_plan_pdf.py          renders the plan to PDF
  gen_api_reference.py       regenerates docs/API_REFERENCE.md from the app's OpenAPI
  quickstart_check.py        non-Docker end-to-end smoke test (CI gate)
  capability_spike/          throwaway Stage-A capability harness
backend/
  aegis/                     the Phase 1 walking skeleton — a self-contained reduced
                             pipeline; kept as an executable reference, NOT imported by app/
  app/                       the real service, built up phase by phase:
    api/                     FastAPI routers
    services/                use-case orchestration per stage
    agents/, ai/             the 7 agents + the AI provider abstraction + AI schemas
    analysis/, ingestion/    repository intelligence
    implementation/, testing/, sandbox/, debugging/, review/, scoring/, verification/
    git/, github/            Git + GitHub intelligence
    memory/                  engineering memory
    orchestration/           the pipeline state machine, job queue, worker, GC
    core/                    config, logging, errors, ids, limits, circuit breaker, security/
    models/                  SQLAlchemy tables (34); db/migrations/ Alembic revisions (0001…0021)
    repository/              thin data-access classes, one per aggregate
  tests/  unit/ integration/ e2e/ security/ perf/ docs/
frontend/                    Vite + React + TS dashboard
test-repositories/           aegis-acceptance (+ -unfixable) — the worked example
docker/                      sandbox.Dockerfile, api.Dockerfile, frontend.Dockerfile
```

`backend/aegis/` and `backend/app/` are **two separate packages**. `aegis/` is
the throwaway-scope skeleton from Phase 1; `app/` is the product. Changes in one
do not affect the other.

## 2. The phase / migration model

The plan (`docs/AEGIS_IMPLEMENTATION_PLAN.md`) defines 28 phases; each ends in
verified, integrated functionality with its own tests and, where it touches the
schema, one Alembic migration. Migrations are linear — `0001` … `0021` — and
`alembic downgrade` must work (a CI smoke test runs `upgrade head` then
`downgrade base`). To add one:

```bash
cd backend
alembic revision -m "short description"      # writes versions/00NN_*.py
# edit upgrade()/downgrade(); add the model change under app/models/
alembic upgrade head && alembic downgrade -1 && alembic upgrade head   # round-trip
```

## 3. Local checks (must pass before pushing)

```bash
cd backend
ruff check . && black --check . && mypy app
pytest -q                      # full suite (~940 tests; e2e + benchmark included)
pytest -q tests/docs           # the documentation-drift gates
python ../scripts/quickstart_check.py
pytest -q --perf tests/perf    # optional: the perf / soak-shape suite (deselected by default)
```

CI (`.github/workflows/ci.yml`) runs the same, plus a `security` job (bandit,
pip-audit, CycloneDX SBOM, lockfile-drift) and the frontend job.

## 4. The agent + AI-schema pattern

Every AI call goes through `app/ai/provider.py::AIProvider.complete(template,
variables, schema, …)`. Templates live in `app/ai/prompts/`; the response is
validated against a Pydantic schema (`app/schemas/*`) with one bounded repair
attempt, and every AI conclusion carries an `evidence` list. The CI default
provider is `MockProvider` (deterministic, offline). Add a new AI step by: a
prompt template, a response schema with `evidence`, an agent function that builds
`variables` and calls `complete`, and a service that persists the typed output +
a `TaskStep` + an `AuditLog` row. Bound context with
`ai/context.py::fit_context` against `limits.ai_context_tokens(settings)`.

## 5. The documentation-drift gates (`backend/tests/docs/`)

These fail CI on drift — keep them green when you change a route or a doc:

| Test | Fails when | Fix |
|---|---|---|
| `test_doc_links.py` | a relative link / `#anchor` in a Markdown doc doesn't resolve | fix the link or the target heading |
| `test_api_reference_fresh.py` | `docs/API_REFERENCE.md` ≠ generator output, or a route is missing from it | `python scripts/gen_api_reference.py --write` |
| `test_support_matrix_evidence.py` | a `SUPPORTED`/`PARTIALLY_SUPPORTED` row in `MVP_DEFINITION.md` §2 cites an evidence path that doesn't exist | point it at a real `backend/tests/...` path or artifact |
| `test_acceptance_contract.py` | `docs/ACCEPTANCE_CONTRACT.md` isn't 30 rows, or an evidence test file is missing, or the rules section isn't 20 rows | update the contract row / add the test |

Doc↔code constant sync is separately guarded by
`tests/unit/test_scoring_model_version_sync.py` and
`test_mapping_model_version_sync.py` — a weight/threshold change needs a matching
`docs/METRICS.md` edit **and** a model-version bump.

## 6. Conventions

- `ruff` + `black` (line length per `pyproject.toml`); `mypy app` (not `aegis/`).
- Repository classes are thin (no business logic); services own the use case;
  routers are one-liners over services.
- Errors are `AppError` subclasses with a `code`, a message and a `status_code`;
  the envelope is `{code, message, details, evidence?}`.
- No feature is "done" until it has a test and is wired end to end (Absolute
  Rules 1, 17, 18 — see `docs/ACCEPTANCE_CONTRACT.md`).
