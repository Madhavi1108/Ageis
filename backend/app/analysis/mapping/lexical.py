"""Lexical retriever: an in-memory SQLite FTS5 index over file source + symbol
text, queried with the issue's tokens and ranked by ``bm25()``.

Design (docs/AEGIS_IMPLEMENTATION_PLAN.md Section 15, docs/REPOSITORY_ANALYSIS.md
Section 5):

* The index is built per call in ``sqlite3.connect(":memory:")`` and thrown
  away -- "build once per snapshot and reuse" is a later optimisation
  (plan Section 4.13), not a Phase 7 gate.
* One FTS row per file. Its content column concatenates the file's own source
  with the qualnames / signatures / docstrings of the symbols defined in it, so
  a symbol-name hit and a code hit share one ranked list.
* Deterministic: ``bm25`` is a pure function of the indexed corpus + query, and
  ties break on ``path``.
* Evidence: the first source line that contains a matched query term, so the
  candidate is independently re-checkable (the "no evidence-free candidate"
  rule).

If FTS5 is unavailable in the runtime's SQLite build the retriever degrades to a
plain token-overlap count over the same corpus rather than failing the mapping.
"""

from __future__ import annotations

import sqlite3

from aegis.schemas.common import Evidence

from app.analysis.mapping.candidate import RetrievedCandidate, RetrieverResult
from app.analysis.mapping.inputs import FileDoc, SymbolDoc
from app.analysis.mapping.text import tokenize

_NAME = "lexical"


def _fts5_available() -> bool:
    try:
        con = sqlite3.connect(":memory:")
        con.execute("CREATE VIRTUAL TABLE t USING fts5(x)")
        con.close()
        return True
    except sqlite3.OperationalError:
        return False


def _symbol_text(symbols: list[SymbolDoc]) -> dict[str, str]:
    by_path: dict[str, list[str]] = {}
    for s in symbols:
        chunk = s.qualname
        if s.signature:
            chunk += " " + s.signature
        if s.docstring:
            chunk += " " + s.docstring
        by_path.setdefault(s.path, []).append(chunk)
    return {p: " ".join(v) for p, v in by_path.items()}


def _evidence_for(doc: FileDoc, terms: list[str]) -> Evidence:
    lowered = {t for t in terms}
    for i, line in enumerate(doc.text.splitlines(), start=1):
        ll = line.lower()
        hit = [t for t in lowered if t in ll]
        if hit:
            return Evidence(
                kind="file",
                ref=doc.path,
                detail=f"lexical hit for {sorted(hit)} at line {i}",
            )
    # matched only via symbol text (docstring/signature), not a raw source line
    return Evidence(
        kind="file",
        ref=doc.path,
        detail=f"lexical hit for {sorted(lowered)} in symbol text",
    )


def _fallback_overlap(
    files: list[FileDoc], symbols: list[SymbolDoc], query_terms: list[str]
) -> RetrieverResult:
    sym_text = _symbol_text(symbols)
    qset = set(query_terms)
    scored: list[RetrievedCandidate] = []
    for doc in files:
        corpus = (doc.text + " " + sym_text.get(doc.path, "")).lower()
        overlap = sorted(t for t in qset if t in corpus)
        if not overlap:
            continue
        scored.append(
            RetrievedCandidate(
                path=doc.path,
                score=float(len(overlap)),
                evidence=[_evidence_for(doc, overlap)],
            )
        )
    scored.sort(key=lambda c: (-c.score, c.path))
    return RetrieverResult(name=_NAME, candidates=scored)


def retrieve(
    issue_text: str,
    files: list[FileDoc],
    symbols: list[SymbolDoc],
    *,
    limit: int = 50,
) -> RetrieverResult:
    query_terms = tokenize(issue_text)
    if not query_terms:
        return RetrieverResult(name=_NAME, candidates=[])
    if not _fts5_available():
        return _fallback_overlap(files, symbols, query_terms)

    sym_text = _symbol_text(symbols)
    con = sqlite3.connect(":memory:")
    try:
        con.execute("CREATE VIRTUAL TABLE docs USING fts5(path UNINDEXED, body)")
        con.executemany(
            "INSERT INTO docs(path, body) VALUES (?, ?)",
            [(doc.path, doc.text + "\n" + sym_text.get(doc.path, "")) for doc in files],
        )
        # OR the terms together; quote each to neutralise FTS operators.
        match_expr = " OR ".join(f'"{t}"' for t in query_terms)
        rows = con.execute(
            "SELECT path, bm25(docs) AS rank FROM docs "
            "WHERE docs MATCH ? ORDER BY rank, path LIMIT ?",
            (match_expr, limit),
        ).fetchall()
    finally:
        con.close()

    doc_by_path = {d.path: d for d in files}
    candidates: list[RetrievedCandidate] = []
    for path, rank in rows:
        doc = doc_by_path.get(path)
        if doc is None:
            continue
        # bm25 returns a negative number, more negative = better match; flip it
        # so higher = better, consistent with every other retriever's score.
        candidates.append(
            RetrievedCandidate(
                path=path,
                score=-float(rank),
                evidence=[_evidence_for(doc, query_terms)],
            )
        )
    return RetrieverResult(name=_NAME, candidates=candidates)
