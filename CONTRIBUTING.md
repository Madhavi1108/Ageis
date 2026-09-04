# Contributing to AEGIS

This covers local dev setup as of **Phase 2 (Project Foundation)**. See
`docs/AEGIS_IMPLEMENTATION_PLAN.md` for the full phase-by-phase plan and
`README.md` for the project overview and doc index.

## Prerequisites

- Python 3.11+
- Node 20+
- Docker (optional but recommended -- required for `--sandbox docker` and for
  `docker compose up`)

## Backend setup

```
cd backend
pip install -e ".[dev]"
```

PowerShell:
```powershell
cd backend
pip install -e ".[dev]"
```

Run the API locally:
```
uvicorn app.main:app --reload
```
Then `curl http://localhost:8000/healthz`.

Run the Phase 1 walking-skeleton CLI:
```
python -m aegis.skeleton run ../test-repositories/aegis-acceptance ../test-repositories/aegis-acceptance/task.md --sandbox fake
```

### Tests

```
pytest tests -q
```
`tests/unit/` and `tests/integration/` cover both `app/` (Phase 2) and `aegis/`
(Phase 1); `tests/e2e/` includes one Docker-gated test that auto-skips
without a daemon.

### Database / migrations

The default dev database is a local SQLite file (`AEGIS_DATABASE_URL`,
default `sqlite:///./aegis.db`) -- zero extra infra required.

```
alembic upgrade head        # apply all migrations
alembic downgrade -1         # roll back one revision
alembic revision -m "add X"  # create a new empty migration
```

PowerShell: same commands, run from `backend/`.

### Lint / format / types

```
ruff check .
black .
mypy app          # only backend/app is gated in CI for now; aegis/ is Phase 1 code
```

### Regenerating the dependency lockfile

```
pip-compile --extra dev --output-file requirements.lock pyproject.toml
```
`pip-tools` currently drops the `sys_platform == "win32"` marker on
`pywin32` (a transitive dependency of the `docker` SDK) -- re-add it by hand
after regenerating, or CI on Linux will fail trying to install it. Look for
the `pywin32` line and confirm it still has ` ; sys_platform == "win32"`
before committing.

### Async database access

Phase 2 uses a synchronous SQLAlchemy engine (`app/db/session.py`), which is
sufficient for current load. An async engine (`create_async_engine` +
`AsyncSession`) is a drop-in swap if a later phase's concurrency needs
demand it; there's no code committing to sync today beyond `db/session.py`
itself.

## Frontend setup

```
cd frontend
npm install
cp .env.example .env
npm run dev
```

```
npm run build       # tsc -b && vite build
npm run lint         # eslint
npx tsc -b --noEmit   # type-check only
```

## Docker Compose (full dev stack)

```
cp .env.example .env
docker compose up
```
Brings up `api` (port 8000), `frontend` (port 5173), and a `worker`
placeholder (no real job-processing logic yet). Postgres is opt-in:
```
docker compose --profile postgres up
```
and set `AEGIS_DATABASE_URL` in `.env` to point at it.

## Migration workflow

1. Change a model under `backend/app/models/`.
2. `cd backend && alembic revision --autogenerate -m "describe the change"`.
3. Review the generated migration -- autogenerate misses some SQLite-specific
   changes; check `upgrade()` and `downgrade()` are both correct.
4. `alembic upgrade head` to apply it locally; `alembic downgrade -1` to
   confirm it reverses cleanly.

## Commit conventions

Keep commits scoped to one logical change. Reference the phase or doc
section a change implements in the commit body when useful (see the `Phase
0` / `Phase 1` commits for the existing style).
