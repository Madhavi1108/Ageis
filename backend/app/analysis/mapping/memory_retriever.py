"""Engineering-memory retriever for issue -> code mapping (Phase 20).

Pure projection of ``MemoryHit``s (produced by ``app/services/memory.py``) into
the shared ``RetrieverResult`` shape. The service wires the DB call; this module
only turns hits into evidence-carrying candidates. The fusion table already
weights ``memory`` at 0.6 and ``evidence.py`` already labels a memory-only
candidate ``INFERENCE`` -- a memory candidate is never a fact.
"""

from __future__ import annotations

from aegis.schemas.common import Evidence

from app.analysis.mapping.candidate import RetrievedCandidate, RetrieverResult

_NAME = "memory"


def build_result(hits: list) -> RetrieverResult:
    best: dict[str, RetrievedCandidate] = {}
    for h in hits:
        for path in h.touched_files or []:
            existing = best.get(path)
            if existing is not None and existing.score >= h.similarity:
                continue
            best[path] = RetrievedCandidate(
                path=path,
                score=float(h.similarity),
                evidence=[
                    Evidence(
                        kind="file",
                        ref=path,
                        detail=(
                            f"{h.provenance} changed this file "
                            f"({h.label}) -- not authoritative"
                        ),
                    )
                ],
                symbols=list(h.touched_symbols or []),
            )
    candidates = sorted(best.values(), key=lambda c: (-c.score, c.path))
    return RetrieverResult(
        name=_NAME, candidates=candidates, available=bool(candidates)
    )
