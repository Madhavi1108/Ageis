# AEGIS — 5-minute demo

A scripted walkthrough of the worked example: a discount-cap bug that AEGIS
introduces a fix for, sees fail its own boundary test, repairs, and verifies.

Status: final — reconciled against the built system (Phases 0–28), 2026-09-09.

---

## 0. One command (no Docker, no services)

```bash
python scripts/quickstart_check.py
```

Drives the full pipeline in-process against `test-repositories/aegis-acceptance`
with the deterministic mock provider and the fake sandbox. Expect:

```
  ingested <sha>        ( 0.7s)
  analyzed              ( 0.8s)
  pipeline -> AWAITING_APPROVAL ( 6.5s)
  approved -> COMPLETED  ( 6.6s)
QUICKSTART PASS
```

That is the acceptance task from Specification §39 running end to end.

## 1. The same thing, over the API + dashboard (~5 min)

```bash
# terminal 1 — API
cd backend && pip install -e ".[dev]" && alembic upgrade head && uvicorn app.main:app --reload
# terminal 2 — worker
cd backend && python -m app.orchestration.worker
# terminal 3 — dashboard
cd frontend && npm install && cp .env.example .env && npm run dev
```

Then, following [`USER_GUIDE.md`](USER_GUIDE.md) §2:

1. `POST /repositories` with `{"source_type":"LOCAL","url_or_path":"<abs path to>/test-repositories/aegis-acceptance"}`
   (make sure that directory is under an `AEGIS_INGESTION_LOCAL_ROOTS` entry).
2. `POST /repositories/{id}/snapshots` then `.../analysis`.
3. `POST /tasks` with the text of `test-repositories/aegis-acceptance/task.md` and
   `"allowed_paths": ["invoice.py", "test_invoice.py"]`.
4. `POST /tasks/{id}/run`.

## 2. What to point at

- **Dashboard → task pipeline view:** each stage lights up — map, plan,
  implement, generate tests, execute (first run **fails** the boundary test),
  investigate, repair, re-execute (**passes**), regression, review, score,
  verify.
- **Diff / patch viewer:** the final change to `invoice.py`, with per-file risk,
  scope status (in-scope), related tests, and review findings.
- **Trust report:** the engineering trace (every stage's input/output/evidence),
  the PCS / CRS scores with their algorithm, and the deterministic-replay
  fidelity disclosure.
- **Timeline API** (`GET /tasks/{id}/timeline`): the same, as JSON.

## 3. The point

The first implementation attempt is wrong on purpose — AEGIS's own generated
boundary test catches it, the debugging loop finds the root cause and repairs it
within the bounded budget, and only then does verification let it reach
`COMPLETED`. Nothing is claimed that wasn't executed.
