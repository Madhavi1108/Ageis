# ADR-0007: Code-analysis & graph abstraction

Status: Accepted
Date: 2026-09-04
Deciders: Phase 0

## Context

Spec §3.1 requires a machine-readable understanding of the repository (structure, symbols, imports,
tests, entry points, build system); §22 requires a relationship graph; the MVP targets Python with
an architecture that allows other languages later, and must never import or execute target code.

## Decision

- A `LanguageAnalyzer` abstraction; `PythonAnalyzer` is the only MVP implementation, using stdlib
  `ast`. `tree-sitter` is the fallback for files that fail to parse and the seam for future
  languages.
- Analyzer output is normalized into language-agnostic records: `RepositorySymbol`, `Dependency`,
  and callee-name lists (`REPOSITORY_ANALYSIS.md` §2).
- A `CodeGraph` built with **NetworkX** in memory for algorithms + adjacency tables persisted in
  the DB for queries + a serialized-graph `Artifact`. Reload-from-DB must equal in-memory
  (determinism test).
- Call edges carry a confidence label `RESOLVED` / `HEURISTIC` / `UNRESOLVED`; a non-`RESOLVED`
  edge is never asserted as a `FACT`.
- Centrality (degree + approximate betweenness with a time budget) feeds the risk score.
- Undeterminable facts are recorded as `UNKNOWN`; a parse failure is recorded per file and
  analysis continues.

## Consequences

- No graph database to operate; sufficient for impact analysis, mapping, and centrality at MVP
  scale.
- Adding a language = a new `LanguageAnalyzer`; the graph and downstream stages are unchanged.
- Very large graphs need approximation + a size limit (`PARTIALLY_SUPPORTED`); tracked as an open
  question, measured in Phase 5 / Phase 27.

## Alternatives considered

- **Neo4j / a triple store** — rejected: operational weight not justified at MVP scale
  (`TECH_STACK.md` §2).
- **jedi / rope / an LSP server** — rejected: heavier, partly runtime-dependent; `ast` gives the
  static facts we need without importing target code.
- **Treat all call edges as facts** — rejected by Spec §21; dynamic dispatch makes this unsound.
