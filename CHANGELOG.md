# Changelog

All notable changes to AEGIS are recorded here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); this project versions
the *platform as a whole* (the `backend/` package version in
`backend/pyproject.toml` tracks it).

Each line points at the implementation-plan phase
(`docs/AEGIS_IMPLEMENTATION_PLAN.md`) that delivered it. Phase numbers, not
commit hashes, are the unit of history for the MVP build-out.

## [0.2.0] - 2026-09-09

First feature-complete MVP: a real task and a real Git repository can be driven
end to end to a verified, evidence-backed change.

### Added — core pipeline

- **Repository ingestion** — local path + GitHub HTTPS, snapshot model,
  size/file/history limits (Phase 3).
- **Python analysis** — AST symbols, imports, signatures, entry points, test
  infrastructure detection; dependency classification incl. `UNKNOWN` (Phase 4).
- **Code graph** — IMPORTS/CALLS/DEFINES edges, centrality, call-edge
  confidence labels (Phase 5).
- **Task / issue ingestion** — untrusted-text normalization, idempotent
  create/run/cancel (Phase 6).
- **Issue → code mapping** — fused lexical + graph + history + memory
  retrieval, `mapping-model v1.0.0`, semantic retrieval as an optional signal
  (Phase 7).
- **Impact analysis** — blast radius, callers, related tests, public-API surface
  with evidence and `INFERENCE` labels (Phase 8).
- **Engineering planning + validation** — schema-constrained AI plan with a
  deterministic rule-based fallback; feasibility / scope / evidence gate
  (Phase 9).
- **Autonomous implementation** — anchored edit operations, unified diff,
  reversible, scope-tracked (Phase 10).
- **Test generation** — framework-mirroring, boundary + negative cases per
  changed public function (Phase 11).
- **Secure sandbox execution** — Docker with `--network none`, read-only rootfs,
  dropped capabilities, resource limits; `PARTIALLY_SUPPORTED` (no host
  fallback) when Docker is absent (Phase 12).
- **Failure investigation** — traceback parsing, frame→symbol, deterministic
  classification (Phase 13).
- **Autonomous debugging & repair** — bounded loop (iterations + wall-clock +
  no-progress), auto-revert, `SAFE_STOP` with evidence (Phase 14).
- **Regression intelligence** — smart selection + full-suite gate (Phase 15).
- **Code review engine** — static + AST rules + AI reviewer across 10 categories
  (Phase 16).
- **Scoring** — `scoring-model v1.0.0`: Patch Confidence Score, Change Risk
  Score, Repository Health Profile — deterministic, versioned, explained, with
  hard gates (Phase 17).
- **Verification** — mandatory-criteria checklist, engineering trace, no
  false-complete on negative tests (Phase 18).
- **Git & GitHub integration** — workspace branch/commit, PR artifact always,
  real PR only with write credentials + policy approval (Phase 19).
- **Engineering memory** — opt-in write on terminal state, provenance-labelled
  retrieval, never auto-applied (Phase 20).
- **Job orchestration** — pipeline state machine, guarded transitions,
  checkpoints, cooperative cancel, crash-recovery resume (Phase 21).

### Added — product surfaces

- **Dashboard** — React/TS frontend; task pipeline view, diff/patch viewer,
  trust report, all backed by real API data (Phase 22).
- **Excel integration & reporting** — workbook import with hard limits, the
  18-section structured task report, `.xlsx` rendering (Phase 23).

### Added — evaluation & release engineering

- **End-to-end acceptance repository** — the `test-repositories/aegis-acceptance`
  worked example with crafted Git history; full-pipeline e2e suite (Phase 24).
- **Benchmarking + metric calibration** — the 16-metric harness, seeded
  fault-injection datasets, `benchmarks/` runner and publisher, retained
  `scoring-model v1.0.0` (Phase 25).
- **Security hardening** — `core/security/` (path jail, subprocess guard, env
  allowlist, SSRF, redaction), generated-test static scan, strict request
  bodies, opt-in rate limiting, a CI `security` job (bandit + pip-audit +
  CycloneDX SBOM + lockfile drift) (Phase 26).
- **Performance & reliability** — consolidated `core/limits.py`, job
  retry/backoff/heartbeat, queue-depth backpressure (`JOB_QUEUE_FULL` 429),
  circuit breakers around the AI + GitHub clients, deterministic AI context
  windowing, analysis wall-clock budget → `PARTIALLY_SUPPORTED`, artifact &
  workspace garbage collection, `/readyz` + `/metrics` (Phase 27).
- **Documentation & release** — this changelog, `LICENSE` (Apache-2.0), the
  user / operator / developer guides, `RUNBOOKS.md`, a generated
  `API_REFERENCE.md`, the evidence-linked `ACCEPTANCE_CONTRACT.md`, and the
  docs-drift CI gates (Phase 28).

### Known limitations

- The Docker sandbox happy path has not been exercised against a live daemon in
  this environment (`PARTIALLY_SUPPORTED` is verified; container hardening rests
  on policy unit tests).
- The Phase 0 capability spike and the acceptance contract have not been run
  against a live AI provider on a real benchmark subset.
- The worker is a single sequential process; a distributed / parallel worker is
  a documented follow-up.
- `limit_graph_nodes` is enforced as configuration only (no partial-graph
  fallback yet).

## [0.1.0] - 2026-09-04

- Phase 0 — greenfield architecture, 14 design documents, 20 ADRs, the
  implementation plan.
- Phase 1 — walking-skeleton CLI: ingest → analyze → map → plan → implement →
  test → repair → verify against a trusted fixture.
- Phase 2 — FastAPI service foundation: config, JSON logging with secret
  redaction, SQLAlchemy + Alembic, typed error envelope, `/healthz` +
  `/version`, CI, the Vite/React scaffold, the Docker Compose dev stack.
