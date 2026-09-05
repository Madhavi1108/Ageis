"""Semantic (embeddings) retriever -- seam only, in Phase 7.

The plan (docs/AEGIS_IMPLEMENTATION_PLAN.md Section 15) makes semantic retrieval
optional: "without an embeddings provider the system degrades to lexical + graph
and reports reduced confidence." There is no ``AIProvider`` in ``app/`` yet (the
provider abstraction is its own later step), so this always reports
``available=False`` and contributes nothing. The fusion weights table already
carries a ``semantic`` row, and ``confidence.overall_confidence`` scales its
result down when this is unavailable -- so wiring a real embeddings retriever in
later is a one-file change here.
"""

from __future__ import annotations

from app.analysis.mapping.candidate import RetrieverResult

_NAME = "semantic"


def retrieve(*_args, **_kwargs) -> RetrieverResult:
    return RetrieverResult(name=_NAME, candidates=[], available=False)
