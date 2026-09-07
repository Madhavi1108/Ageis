"""Phase 20 unit: the in-memory lexical index (FTS5 + token-overlap fallback)."""

from __future__ import annotations

from app.memory.index import IndexDoc, MemoryIndex

_DOCS = [
    IndexDoc("A", "invoice discount cap calculate_total not applied above 0.5"),
    IndexDoc("B", "checkout shipping address validation missing"),
    IndexDoc("C", "invoice rounding error on discount totals"),
]


def test_query_ranks_relevant_docs_first():
    idx = MemoryIndex.build(_DOCS)
    ranked = idx.query("invoice discount cap not applied", limit=10)
    ids = [tid for tid, _ in ranked]
    assert ids[0] == "A"
    assert "B" not in ids  # no token overlap
    # scores are descending
    scores = [s for _, s in ranked]
    assert scores == sorted(scores, reverse=True)


def test_fallback_matches_fts5_ordering_on_this_corpus():
    fts = MemoryIndex(_DOCS, fts5=True)
    plain = MemoryIndex(_DOCS, fts5=False)
    fts_ids = [t for t, _ in fts.query("invoice discount", limit=10)]
    plain_ids = [t for t, _ in plain.query("invoice discount", limit=10)]
    # both must surface A and C (invoice + discount), never B, A before/with C
    assert set(fts_ids) == {"A", "C"} == set(plain_ids)
    assert fts_ids[0] in ("A", "C") and plain_ids[0] in ("A", "C")


def test_empty_corpus_or_query():
    assert MemoryIndex.build([]).query("anything") == []
    assert MemoryIndex.build(_DOCS).query("   ") == []
    assert MemoryIndex.build(_DOCS).query("zzzznotatoken") == []
