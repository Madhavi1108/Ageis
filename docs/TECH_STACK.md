# AEGIS Technology Stack

Traceability: Specification §44, §45. Phase 0 deliverable (Spec §46). Companion to
`AEGIS_IMPLEMENTATION_PLAN.md` §4.1.

Status: Accepted — 2026-09-04.

---

## 1. Chosen stack

| Concern | Choice | Pinned major | Rationale |
|---|---|---|---|
| Backend language | Python | 3.11+ | Spec mandate; matches the MVP target language (analysing Python repos with `ast`); rich ecosystem for AST, graphs, Git |
| Web framework | FastAPI | 0.11x | async, first-class Pydantic + OpenAPI, structured validation and errors, low ceremony |
| Data validation | Pydantic | v2 | schema validation for API **and** the 18 AI output schemas; fast core |
| ORM | SQLAlchemy | 2.0 | mature, DB-agnostic, typed 2.0 API; clean SQLite -> PostgreSQL path |
| Migrations | Alembic | 1.13+ | standard SQLAlchemy companion; reversible migrations required by Spec §35 |
| Code analysis | `ast` (stdlib) + `tree-sitter` | py-tree-sitter 0.21+ | `ast` for correct Python parsing without importing target code; `tree-sitter` for syntax-error resilience and the future-language seam |
| Graph | NetworkX | 3.x | in-process, batteries-included algorithms (centrality, BFS, shortest path); adjacency also persisted to the DB for querying |
| Git (local) | GitPython | 3.1+ | history, blame, churn without shelling out to `git` with untrusted args |
| GitHub | `httpx` REST client | httpx 0.27+ | explicit, testable with `respx`; no heavy SDK; token handling under our control |
| AI | `AIProvider` abstraction | — | `ClaudeProvider`, `OpenAIProvider`, `LocalProvider`, `MockProvider`; provider chosen by config |
| Anthropic SDK | `anthropic` | 0.4x | used only inside `ClaudeProvider` |
| Sandbox | Docker | Engine 24+ | Spec's preferred MVP isolation; rootless where available; resource cgroup controls |
| Docker control | `docker` SDK for Python | 7.x | programmatic container lifecycle; no `shell=True` |
| Test runner | pytest | 8.x | Spec mandate; JUnit-XML + JSON report for structured parsing |
| Coverage | coverage.py / pytest-cov | 7.x / 5.x | changed-line coverage feeds PCS/CRS |
| Property tests | hypothesis | 6.x | loop-bound invariants, normalizer bounds, parser fuzzing |
| HTTP test mocks | respx / responses | — | GitHub client contract tests |
| Frontend | React + TypeScript + Vite | React 18, TS 5.x, Vite 5 | Spec mandate; fast dev loop; typed API client from OpenAPI |
| Frontend data | TanStack Query | 5.x | polling on active tasks, cache, request states |
| Frontend tests | Vitest + React Testing Library + MSW | — | component + mocked-API integration |
| E2E | Playwright | 1.4x | headless pipeline walkthrough in CI |
| Excel | openpyxl | 3.1+ | Spec mandate; write-only mode for large sheets; shares domain services |
| Optional ML | scikit-learn | 1.5+ | only for justified scoring calibration in Phase 25 |
| Lint / format / types | ruff, black, mypy | — | CI gates |
| Security scan | bandit, pip-audit | — | CI gates; SBOM generated |
| Containerisation | Docker + Docker Compose | Compose v2 | api, worker, frontend, optional postgres |
| CI | GitHub Actions | — | lint + types + pytest + coverage gate + frontend build/lint/tsc + Playwright + security scan |

---

## 2. Rejected alternatives

| Area | Considered | Rejected because |
|---|---|---|
| Worker | Celery, RQ, arq | For the MVP an in-process asyncio worker with a DB-backed job table is enough and has zero extra infra. The `orchestration/` abstraction keeps a queue library a drop-in for Phase 27 if soak tests demand it (`ADR-0003`). |
| Graph store | Neo4j, in-repo triple store | Operational weight not justified at MVP scale; NetworkX + adjacency tables cover impact analysis, mapping, and centrality. Revisit only if graph size forces it (`ADR-0007`). |
| Sandbox | gVisor, Firecracker microVMs, nsjail | Stronger isolation, but heavier setup and worse portability across CI runners. Docker with `--cap-drop ALL`, `--network none`, `--pids-limit`, read-only rootfs, non-root, `no-new-privileges` is the Spec's preferred MVP and is sufficient for the threat model; stronger isolation is a documented post-MVP option (`ADR-0010`, `SECURITY_MODEL.md`). |
| DB | PostgreSQL-only from day one | SQLite keeps dev and CI zero-infra; the schema is written to be PostgreSQL-compatible (no SQLite-only types, explicit `ondelete`, UTC timestamps) so migration is mechanical (`ADR-0001`). |
| Code analysis | jedi / rope / LSP servers | Heavier, partly runtime-dependent; `ast` gives us exactly the static facts we need without importing target code. `tree-sitter` covers resilience. |
| AI orchestration | LangChain / LlamaIndex / an agent framework | The pipeline is explicit and typed by design (Spec §52). A framework would obscure the connectedness invariant and the schema contracts. We keep a thin `AIProvider` and our own prompt assembly. |
| GitHub | PyGithub | Hides HTTP details we need to control (rate-limit handling, redaction, SSRF, exact error mapping). A thin `httpx` client is more testable. |
| Frontend framework | Next.js, plain Vue | Spec mandates React + TS + Vite; no SSR need for an internal dashboard. |

---

## 3. Dependency policy

- **Pinned + hashed.** All backend dependencies pinned to exact versions with hashes in the
  lockfile. Frontend uses an exact-version lockfile.
- **Audited.** `pip-audit` runs in CI and fails on a known vulnerability unless an exception is
  recorded with justification and an expiry date.
- **SBOM.** A CycloneDX SBOM is generated per build and stored as an artifact.
- **Sandbox image.** Base image pinned by digest, rebuilt on a schedule, scanned before promotion.
- **New dependency = ADR.** Adding a runtime dependency requires a short ADR (problem, why not
  stdlib / existing dep, size, maintenance signal). "Do not add complexity without cause"
  (Spec §44).

---

## 4. Version-bump policy

- Patch/minor bumps: automated PR, must pass full CI including the security and determinism suites.
- Major bumps: an ADR noting breaking changes and the migration done.
- Python itself: track the current stable minor; CI runs the lowest supported (3.11) and current.

---

## 5. Open questions

| # | Question | Resolution |
|---|---|---|
| T1 | embeddings model for semantic mapping (hosted vs local `sentence-transformers`) | decide after the capability spike; `REPOSITORY_ANALYSIS.md` keeps it optional with a lexical+graph fallback |
| T2 | asyncio worker vs arq at target concurrency | `ADR-0003`; measure in Phase 27 |
| T3 | object storage adapter for artifacts (vs mounted volume) | post-MVP; `ADR-0009` leaves the seam |
