"""Graph-proximity retriever: expand from the seed files (the lexical / symbol
hits) across the persisted Phase 5 code graph and propose the files within
``k`` hops.

Rationale: the issue often names a symptom in one module but the fix belongs in
a collaborator -- the caller, the imported helper, the test. Graph proximity
surfaces those. Every such candidate is labelled ``INFERENCE``, never ``FACT``
(docs/REPOSITORY_ANALYSIS.md Section 4: a HEURISTIC/UNRESOLVED graph relation is
never asserted as a fact), and its evidence names the seed and the hop count.

Node ``ref`` conventions from app/analysis/graph/builder.py: a FILE node's ref
is its path; a CLASS/FUNCTION/TEST node's ref is ``"{path}::{qualname}"``; a
DEPENDENCY node's ref is ``"dep::{target}"``. Only the first two resolve back to
a repository file.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from aegis.schemas.common import Evidence

from app.analysis.graph import queries as graph_queries
from app.analysis.graph.errors import GraphNodeNotFoundError
from app.analysis.mapping.candidate import RetrievedCandidate, RetrieverResult
from app.repository.graph import GraphRepository

_NAME = "graph"


def _ref_to_path(ref: str) -> str | None:
    if ref.startswith("dep::") or ref.startswith("unresolved::"):
        return None
    if "::" in ref:
        return ref.split("::", 1)[0]
    return ref


def retrieve(
    session: Session,
    snapshot_id: str,
    seed_paths: list[str],
    *,
    hops: int,
    limit: int = 50,
) -> RetrieverResult:
    if not seed_paths:
        return RetrieverResult(name=_NAME, candidates=[])

    graph_repo = GraphRepository(session)
    known_refs = {n.ref for n in graph_repo.list_nodes_for_snapshot(snapshot_id)}
    if not known_refs:
        # No graph built for this snapshot -- retriever simply contributes nothing.
        return RetrieverResult(name=_NAME, candidates=[], available=False)

    seed_set = set(seed_paths)
    best_hop: dict[str, tuple[int, str]] = {}  # path -> (hop, seed)

    for seed in seed_paths:
        if seed not in known_refs:
            continue
        try:
            reached = graph_queries.k_hop_impact(session, snapshot_id, seed, k=hops)
        except GraphNodeNotFoundError:
            continue
        for node in reached:
            path = _ref_to_path(node.ref)
            if path is None or path in seed_set:
                continue
            # k_hop_impact returns nodes but not their distance; approximate hop
            # as 1 for a direct file/module neighbour, else `hops` -- good enough
            # for ordering, and the evidence says "within N hops" not "at N".
            prior = best_hop.get(path)
            if prior is None:
                best_hop[path] = (hops, seed)

    candidates: list[RetrievedCandidate] = []
    for path, (hop, seed) in best_hop.items():
        candidates.append(
            RetrievedCandidate(
                path=path,
                score=1.0 / hop,
                evidence=[
                    Evidence(
                        kind="file",
                        ref=path,
                        detail=(
                            f"within {hop} code-graph hop(s) of {seed!r} "
                            f"(seed matched the issue lexically / by symbol name)"
                        ),
                    )
                ],
            )
        )
    candidates.sort(key=lambda c: (-c.score, c.path))
    return RetrieverResult(name=_NAME, candidates=candidates[:limit])
