"""Regression-selection classifier + per-stage policies
(docs/AEGIS_IMPLEMENTATION_PLAN.md Section 23). Deterministic, no AI.

Pure functions over already-loaded inputs -- the service
(app/services/regression.py) does the DB / graph IO and hands these value
objects in, so the classifier is unit-testable without a session.

Classes (first match wins):
  TARGETED   -- the test directly covers a changed symbol / file, or its name
                targets a changed module
  RELATED    -- the test covers something within k graph hops of the change, or
                lives in the same directory as a changed file
  REGRESSION -- the covered code has high architectural centrality, or the test
                has failed in this area before
  FULL       -- everything else (still run under mode=full / pre-verification)
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import networkx as nx

_CLASS_RANK = {"TARGETED": 0, "RELATED": 1, "REGRESSION": 2, "FULL": 3}


@dataclass(frozen=True)
class CorpusTest:
    test_id: str
    path: str
    covered_files: frozenset[str]
    covered_symbol: str | None
    generated: bool


@dataclass(frozen=True)
class Classified:
    test_id: str
    path: str
    classification: str
    rationale: str
    covers_symbol: str | None
    hops: int | None


def _stem(path: str) -> str:
    return Path(path).stem


def _centrality_threshold(
    centrality: dict[str, dict[str, float]], decile: float
) -> float:
    values = sorted(v.get("betweenness", 0.0) for v in centrality.values())
    if not values:
        return 1.0  # nothing can qualify
    idx = min(len(values) - 1, int(round(decile * (len(values) - 1))))
    thr = values[idx]
    # a graph where every betweenness is 0 -> nothing is "high centrality"
    return thr if thr > 0.0 else 1.0


def _min_hops(
    graph: nx.MultiDiGraph, sources: set[str], targets: set[str], cutoff: int
) -> int | None:
    if not sources or not targets:
        return None
    und = graph.to_undirected(as_view=True)
    best: int | None = None
    for s in sources:
        if s not in und:
            continue
        lengths = nx.single_source_shortest_path_length(und, s, cutoff=cutoff)
        for t in targets:
            d = lengths.get(t)
            if d is not None and (best is None or d < best):
                best = d
    return best


def classify(
    *,
    corpus: list[CorpusTest],
    changed_files: set[str],
    changed_symbols: set[str],
    graph: nx.MultiDiGraph,
    centrality: dict[str, dict[str, float]],
    prior_failure_files: set[str],
    related_hops: int,
    centrality_decile: float,
) -> list[Classified]:
    changed_stems = {_stem(f) for f in changed_files}
    changed_dirs = {str(Path(f).parent) for f in changed_files}
    hi_thr = _centrality_threshold(centrality, centrality_decile)

    out: list[Classified] = []
    for t in corpus:
        covered = set(t.covered_files)
        sym = t.covered_symbol
        name_target = (
            _stem(t.path).startswith("test_")
            and _stem(t.path)[len("test_") :] in changed_stems
        )

        # --- TARGETED ---
        if sym is not None and sym in changed_symbols:
            out.append(
                Classified(
                    t.test_id,
                    t.path,
                    "TARGETED",
                    f"generated test targets changed symbol {sym}",
                    sym,
                    0,
                )
            )
            continue
        direct_files = sorted(covered & changed_files)
        if direct_files:
            out.append(
                Classified(
                    t.test_id,
                    t.path,
                    "TARGETED",
                    f"covers changed file(s) {direct_files}",
                    _first_changed_symbol(direct_files, changed_symbols),
                    0,
                )
            )
            continue
        if name_target:
            out.append(
                Classified(
                    t.test_id,
                    t.path,
                    "TARGETED",
                    f"name targets changed module {_stem(t.path)[5:]!r}",
                    sym,
                    0,
                )
            )
            continue

        # --- RELATED ---
        hops = _min_hops(graph, covered, changed_files, related_hops)
        if hops is not None and hops <= related_hops:
            cf = sorted(covered)[0] if covered else "?"
            out.append(
                Classified(
                    t.test_id,
                    t.path,
                    "RELATED",
                    f"covers {cf}, {hops} graph hop(s) from a changed file",
                    sym,
                    hops,
                )
            )
            continue
        test_dir = str(Path(t.path).parent)
        if test_dir not in ("", ".") and test_dir in changed_dirs and covered:
            out.append(
                Classified(
                    t.test_id,
                    t.path,
                    "RELATED",
                    f"test file shares directory {test_dir!r} with a changed file",
                    sym,
                    None,
                )
            )
            continue

        # --- REGRESSION ---
        if t.path in prior_failure_files:
            out.append(
                Classified(
                    t.test_id,
                    t.path,
                    "REGRESSION",
                    "this test's file has failed in a prior investigation",
                    sym,
                    None,
                )
            )
            continue
        hot = _hot_covered(covered, centrality, hi_thr)
        if hot is not None:
            bt = centrality[hot]["betweenness"]
            out.append(
                Classified(
                    t.test_id,
                    t.path,
                    "REGRESSION",
                    f"covers {hot} with high architectural centrality "
                    f"(betweenness {bt:.4f})",
                    sym,
                    None,
                )
            )
            continue

        # --- FULL ---
        out.append(
            Classified(t.test_id, t.path, "FULL", "full-suite coverage only", sym, None)
        )

    out.sort(key=lambda c: (_CLASS_RANK[c.classification], c.test_id))
    return out


def _first_changed_symbol(files: list[str], changed_symbols: set[str]) -> str | None:
    for sid in sorted(changed_symbols):
        if sid.split("::", 1)[0] in files:
            return sid
    return None


def _hot_covered(
    covered: set[str], centrality: dict[str, dict[str, float]], threshold: float
) -> str | None:
    for f in sorted(covered):
        if centrality.get(f, {}).get("betweenness", 0.0) >= threshold:
            return f
    return None


# --------------------------------------------------------------------------- #
# Per-stage selection policy
# --------------------------------------------------------------------------- #

_REPAIR_CLASSES = {"TARGETED", "RELATED"}
_SMART_PREVERIFY_CLASSES = {"TARGETED", "RELATED", "REGRESSION"}


@dataclass(frozen=True)
class StageSelection:
    test_ids: list[str]
    justification: str | None = None
    risk_note: str | None = None


def select_for_stage(
    classified: list[Classified], stage: str, *, mode: str
) -> StageSelection:
    all_ids = sorted(c.test_id for c in classified)
    if stage == "repair":
        ids = sorted(
            c.test_id for c in classified if c.classification in _REPAIR_CLASSES
        )
        return StageSelection(ids)

    if stage == "pre_verification":
        if mode == "full":
            return StageSelection(all_ids)
        ids = sorted(
            c.test_id
            for c in classified
            if c.classification in _SMART_PREVERIFY_CLASSES
        )
        if len(ids) < len(all_ids):
            omitted = len(all_ids) - len(ids)
            return StageSelection(
                ids,
                justification=(
                    f"smart selection: {len(ids)} of {len(all_ids)} tests "
                    "(TARGETED + RELATED + REGRESSION); FULL-only tests omitted"
                ),
                risk_note=(
                    f"{omitted} FULL-only test(s) not run in smart mode -- rerun "
                    "with mode=full before final verification"
                ),
            )
        return StageSelection(ids)

    raise ValueError(f"unknown stage {stage!r}")
