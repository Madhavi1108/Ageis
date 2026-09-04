# AEGIS Repository Analysis & Retrieval

Traceability: Specification §3.1, §3.3, §3.4, §22. Phase 0 deliverable (Spec §46 items 10, 11, 12).
Companion to `AEGIS_IMPLEMENTATION_PLAN.md` Phases 3–5, 7, 8; `ADR-0006`, `ADR-0007`.

Status: Accepted — 2026-09-04.

---

## 1. Ingestion model (Spec §3.1, §37)

Inputs: a local path (inside a configured roots list) or a GitHub HTTPS URL.

1. **Validate** — URL scheme/host allowlist; SSRF guard (block private / loopback / link-local
   and DNS names resolving to them); local path canonicalised and confined to roots.
2. **Clone / copy** — GitPython, configurable `--depth`; `core.hooksPath=/dev/null`;
   `--no-recurse-submodules`; no credential prompts. Workspace under
   `artifacts/workspaces/<snapshot_id>`, restrictive permissions, read-only after build.
3. **Manifest** — walk (honour `.gitignore`, skip vendored/generated trees); per file: path,
   size, `sha256`, language (extension + shebang), `is_test`, `is_vendored`.
4. **Limits** — repo size / file count / file size / history depth; exceeding any ->
   `RepositorySnapshot.status = PARTIALLY_SUPPORTED` with `limit_reason`, partial manifest kept.
5. **Persist** — `Repository`, `RepositorySnapshot`, `RepositoryFile` rows; workspace as an
   ephemeral `Artifact`.
6. **Idempotency** — re-ingesting the same commit returns the existing snapshot (dedupe by
   `(repository_id, commit_sha)`).

Target repository code is **never executed** during ingestion.

---

## 2. Python AST analysis (Spec §3.1)

Uses stdlib `ast` (no import, no exec of target code); `tree-sitter` fallback for files that fail
to parse and as the future-language seam.

Extracted per file:

- **Symbols** — modules, classes, functions, methods: `symbol_id = "{relpath}::{qualname}"`,
  `kind`, `qualname`, `signature` (args, defaults, `*args`/`**kwargs`, annotations, return),
  `decorators`, `lineno`/`end_lineno`, `docstring`, `is_exported` (in `__all__`, package top
  level, or a route decorator).
- **Imports** — module + names; classified `STDLIB` / `THIRD_PARTY` / `LOCAL` / `UNKNOWN` using
  the stdlib list + the manifest + declared dependencies. Conditional / aliased imports captured.
- **Callee names** — names invoked within each symbol (not resolved here; resolution is Phase 5
  with a confidence label).
- **Parse failures** — recorded on the `RepositoryFile` (`parse_status`, `parse_error`); analysis
  continues.

Nothing is guessed: undeterminable facts are `UNKNOWN`.

---

## 3. Project metadata detection

| Fact | Sources (first match wins, else `UNKNOWN`) |
|---|---|
| Package manager | `poetry.lock`+`[tool.poetry]` -> poetry; `uv.lock` -> uv; `Pipfile` -> pipenv; `requirements*.txt` -> pip; else `UNKNOWN` |
| Build backend | `[build-system] build-backend` in `pyproject.toml` |
| Dependencies | `[project.dependencies]` / `[tool.poetry.dependencies]` / `requirements*.txt` |
| Test framework | `pytest` config (`pytest.ini`, `[tool.pytest.ini_options]`, `conftest.py`), `unittest` usage, `tox.ini` |
| Test command | explicit config -> `tox`/`nox` -> `pytest` default; recorded with its source |
| Entry points | `if __name__ == "__main__"`, `[project.scripts]` / `console_scripts`, ASGI/WSGI app objects, CLI frameworks |

Output assembled into `RepositoryAnalysis` / `RepositoryContext`.

---

## 4. Code graph (Spec §22)

**Nodes:** `repo`, `file`, `module`, `class`, `function`, `test`, `dependency`, `commit`, `issue`,
`patch`. **Edges:** `IMPORTS`, `CALLS`, `DEFINES`, `TESTS`, `MODIFIES`, `DEPENDS_ON`,
`CHANGED_BY`, `RELATED_TO`, `FIXED_BY`, `AFFECTS`.

- **Call-edge resolution** by name + import table + same-module scope, each labelled
  `RESOLVED` / `HEURISTIC` / `UNRESOLVED`. Dynamic dispatch -> `UNRESOLVED`. A `HEURISTIC` or
  `UNRESOLVED` edge is never asserted as a `FACT`.
- **Test linkage** — `TESTS` edges from test-file imports + `test_<module>` naming + shared
  fixtures.
- **Storage** — NetworkX in memory for algorithms; adjacency persisted to the DB for querying;
  the serialized graph as an `Artifact`. Reload-from-DB must equal the in-memory graph
  (determinism test).
- **Centrality** — degree + betweenness (approximate for large graphs, with a time budget);
  normalized betweenness feeds `architectural_centrality` in CRS.
- **Queries** — callers, callees, k-hop impact set, shortest path, subgraph export.

---

## 5. Issue -> code retrieval (Spec §3.3)

Combine retrievers, each emitting candidates with concrete `Evidence`:

| Retriever | Evidence it attaches |
|---|---|
| lexical (SQLite FTS5 over code + docstrings + symbol names) | matched line + term |
| symbol-name match | matched qualname |
| graph proximity | k-hop path from seed symbols |
| git-history | related historical commit / file |
| engineering memory | prior task, provenance-labelled ("historical — verify") |
| semantic (embeddings, **optional**) | nearest chunk; absent -> lower `overall_confidence` |

**Fusion:** reciprocal-rank fusion, `mapping-model v1.0.0` weights (`METRICS.md` §4), `k = 60`.

**Hard rule:** no candidate is returned without >= 1 concrete evidence item. Below the threshold
-> `UNKNOWN`. Deterministic given a fixed index + model.

Output: `IssueCodeMapping` — ranked `candidates[]` with `{path, symbols[], score, confidence,
labels[], evidence[]}`, `related_tests[]`, `dependencies[]`, `overall_confidence`, `model_version`.

Confidence calibration is heuristic in `v1.0.0` (cross-retriever agreement + top-score margin),
calibrated in Phase 25. Metric #1 (`recall@k`, F1) measures it.

---

## 6. Impact analysis (Spec §3.4)

From the mapping + graph:

- **Blast radius** — reverse-graph BFS from the changed set to a configurable depth; grouped by
  hop.
- **Callers** — direct + indirect (labelled by hop and edge confidence).
- **Related tests** — graph `TESTS` edges + heuristics.
- **Public API touched** — exported symbols / routes in the changed set.
- **Config refs** — uses of settings / env keys referenced by changed code.
- **DB refs** — ORM model references and SQL string literals — **labelled `INFERENCE`**, never
  `FACT`.
- **Regression areas** — ranked by `centrality * coverage_gap`.
- **Risk signal bundle** — the normalized inputs CRS needs (files, lines, dep impact, public API,
  coverage, churn, prior failures, centrality, complexity delta, security sensitivity).

Output: `ImpactAnalysis`, both a human-readable report (matching the Spec's worked-example shape)
and the machine bundle. Persisted once per task.

---

## 7. Repository Health Profile

Computed per snapshot: maintainability index, test coverage, dependency coupling (inverse), churn
stability, documentation ratio, CI presence -> `RHP` (see `METRICS.md` §2.3). Emits
`risky_modules`. The Task-Specific Risk Profile restricts inputs to the impact set.

---

## 8. Determinism

Given a fixed snapshot + indexes + model metadata, analysis, graph, mapping, and impact are
reproducible: stable ordering everywhere, no wall-clock in outputs, `PYTHONHASHSEED=0` in any
subprocess. Golden-snapshot tests guard each stage.

---

## 9. Open questions

| # | Question | Resolution |
|---|---|---|
| R1 | embeddings model + chunking strategy | decide after the capability spike; symbol-level chunks as the default |
| R2 | betweenness approximation error budget on large graphs | measured in Phase 5; `PARTIALLY_SUPPORTED` past a size limit |
| R3 | monorepo sub-project detection | heuristic (per-`pyproject.toml` roots) in Phase 4; refine with real repos |
