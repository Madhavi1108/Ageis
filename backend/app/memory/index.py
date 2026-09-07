"""In-memory lexical index over engineering-memory records.

Ported pattern from ``app/analysis/mapping/lexical.py``: build a throwaway
``sqlite3`` FTS5 table per call, query with ``bm25()``, and fall back to a plain
token-overlap count when the runtime's SQLite has no FTS5. Deterministic --
``bm25`` is a pure function of the corpus + query and ties break on ``task_id``.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass

from app.analysis.mapping.text import tokenize


@dataclass
class IndexDoc:
    task_id: str
    text: str


def _fts5_available() -> bool:
    try:
        con = sqlite3.connect(":memory:")
        con.execute("CREATE VIRTUAL TABLE t USING fts5(x)")
        con.close()
        return True
    except sqlite3.OperationalError:
        return False


class MemoryIndex:
    def __init__(self, docs: list[IndexDoc], *, fts5: bool) -> None:
        self._docs = docs
        self._fts5 = fts5

    @classmethod
    def build(cls, docs: list[IndexDoc]) -> "MemoryIndex":
        return cls(list(docs), fts5=_fts5_available())

    def query(self, text: str, *, limit: int = 50) -> list[tuple[str, float]]:
        """``[(task_id, score)]`` best first; higher score = better. ``[]`` when
        the corpus or the query has no usable tokens."""
        terms = tokenize(text)
        if not self._docs or not terms:
            return []
        if self._fts5:
            return self._query_fts5(terms, limit)
        return self._query_overlap(terms, limit)

    # ------------------------------------------------------------------ #

    def _query_fts5(self, terms: list[str], limit: int) -> list[tuple[str, float]]:
        con = sqlite3.connect(":memory:")
        try:
            con.execute(
                "CREATE VIRTUAL TABLE docs USING fts5(task_id UNINDEXED, body)"
            )
            con.executemany(
                "INSERT INTO docs(task_id, body) VALUES (?, ?)",
                [(d.task_id, " ".join(tokenize(d.text))) for d in self._docs],
            )
            match_expr = " OR ".join(f'"{t}"' for t in terms)
            rows = con.execute(
                "SELECT task_id, bm25(docs) AS rank FROM docs "
                "WHERE docs MATCH ? ORDER BY rank, task_id LIMIT ?",
                (match_expr, limit),
            ).fetchall()
        finally:
            con.close()
        # bm25 returns a negative number (lower = better); flip so higher = better
        return [(tid, -float(rank)) for tid, rank in rows]

    def _query_overlap(self, terms: list[str], limit: int) -> list[tuple[str, float]]:
        want = set(terms)
        scored: list[tuple[str, float]] = []
        for d in self._docs:
            overlap = want & set(tokenize(d.text))
            if overlap:
                scored.append((d.task_id, float(len(overlap))))
        scored.sort(key=lambda x: (-x[1], x[0]))
        return scored[:limit]
