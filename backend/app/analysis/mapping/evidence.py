"""Turn fused retriever output into the API ``MappingCandidate`` list.

Enforces the two hard rules from docs/REPOSITORY_ANALYSIS.md Section 5:

* **No evidence-free candidate.** A fused candidate with no evidence is dropped
  here (and ``MappingCandidate`` itself rejects an empty evidence list, so the
  rule is also enforced at the schema boundary).
* **Threshold -> UNKNOWN.** A candidate whose per-candidate confidence is below
  ``threshold`` is dropped; if that empties the list the caller surfaces an
  empty mapping with ``overall_confidence`` 0.0 (the UNKNOWN case).

Labelling: a candidate backed only by the ``graph`` retriever is ``INFERENCE``
(graph proximity is never a fact); one backed by a lexical or symbol hit is
``FACT`` (a re-checkable line / qualname), and may also carry ``INFERENCE`` when
graph proximity additionally contributed.
"""

from __future__ import annotations

from app.analysis.mapping.confidence import candidate_confidence
from app.analysis.mapping.fuse import FusedCandidate
from app.schemas.mapping import MappingCandidate

_FACTUAL_RETRIEVERS = {"lexical", "symbol", "semantic"}


def _labels(retrievers: list[str]) -> list[str]:
    labels: list[str] = []
    if any(r in _FACTUAL_RETRIEVERS for r in retrievers):
        labels.append("FACT")
    if "graph" in retrievers or "memory" in retrievers or "git_history" in retrievers:
        labels.append("INFERENCE")
    return labels or ["INFERENCE"]


def to_candidates(
    fused: list[FusedCandidate],
    *,
    threshold: float,
    top_k: int,
) -> list[MappingCandidate]:
    out: list[MappingCandidate] = []
    for fc in fused:
        if not fc.evidence:
            continue
        conf = candidate_confidence(len(fc.retrievers))
        if conf < threshold:
            continue
        out.append(
            MappingCandidate(
                path=fc.path,
                symbols=fc.symbols,
                score=round(fc.score, 6),
                confidence=conf,
                labels=_labels(fc.retrievers),
                evidence=fc.evidence,
            )
        )
        if len(out) >= top_k:
            break
    return out
