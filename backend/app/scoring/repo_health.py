"""Repository Health Profile (RHP), 0-100, higher = healthier, and the
Task-Specific Risk Profile (RHP restricted to the impact set).
docs/AEGIS_IMPLEMENTATION_PLAN.md Section 4.10.3 / docs/METRICS.md Section 2.3.

Sub-scores are computed from already-persisted Phase 4/5 data (symbols, the
code graph, the file list). ``test_coverage`` and ``churn_stability`` have no
data source yet (coverage instrumentation is absent; Git churn is Phase 19),
so they contribute the documented neutral prior with basis INFERENCE
(docs/METRICS.md Section 2.5). ``maintainability`` is a coarse span-length
proxy pending radon in Phase 25.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.analysis.graph.centrality import compute_centrality
from app.analysis.graph.store import build_networkx
from app.repository.files import FileRepository
from app.repository.graph import GraphRepository
from app.repository.symbols import SymbolRepository
from app.scoring._signal import Contribution, clamp
from app.scoring.model_registry import (
    RHP_CLASSIFICATION,
    RHP_COUPLING_DIVISOR,
    RHP_MAINTAINABILITY_LOC_DIVISOR,
    RHP_RISKY_MODULES_DECILE,
    RHP_WEIGHTS,
    SCORING_MODEL_VERSION,
    UNAVAILABLE_PRIOR_GOOD,
)

_CI_MARKERS = (
    ".github/workflows/",
    ".gitlab-ci.yml",
    "azure-pipelines.yml",
    "jenkinsfile",
    ".circleci/config.yml",
    ".travis.yml",
)


@dataclass
class RHPResult:
    value: int
    classification: str
    subscores: list[Contribution]
    risky_modules: list[dict] = field(default_factory=list)
    model_version: str = SCORING_MODEL_VERSION


def _classify(value: int) -> str:
    if value >= RHP_CLASSIFICATION["HIGH"]:
        return "HIGH"
    if value >= RHP_CLASSIFICATION["MEDIUM"]:
        return "MEDIUM"
    if value >= RHP_CLASSIFICATION["LOW"]:
        return "LOW"
    return "VERY_LOW"


def _path_of(symbol_id: str) -> str:
    return symbol_id.split("::", 1)[0]


def _sub(name, raw, normalized, basis, reason=None) -> Contribution:
    weight = RHP_WEIGHTS[name]
    return Contribution(
        name=name,
        raw=raw,
        normalized=normalized,
        weight=weight,
        contribution=weight * normalized,
        basis=basis,
        unavailable_reason=reason,
        evidence=[],
    )


def compute_rhp(
    db: Session,
    snapshot_id: str,
    *,
    repository_id: str,
    restrict_to: set[str] | None = None,
) -> RHPResult:
    symbols = SymbolRepository(db).list_for_snapshot(snapshot_id)
    files = FileRepository(db).list_for_snapshot(snapshot_id)
    nodes = GraphRepository(db).list_nodes_for_snapshot(snapshot_id)
    edges = GraphRepository(db).list_edges_for_snapshot(snapshot_id)

    if restrict_to is not None:
        symbols = [s for s in symbols if _path_of(s.symbol_id) in restrict_to]
        files = [f for f in files if f.path in restrict_to]

    # --- maintainability: 1 - clamp(mean symbol span LOC / DIVISOR) ---------- #
    spans = [max(1, (s.end_lineno or s.lineno) - s.lineno + 1) for s in symbols]
    if spans:
        mean_loc = sum(spans) / len(spans)
        maint = _sub(
            "maintainability",
            round(mean_loc, 2),
            round(1.0 - clamp(mean_loc / RHP_MAINTAINABILITY_LOC_DIVISOR), 6),
            "INFERENCE",  # coarse span-length proxy pending radon (Phase 25)
        )
    else:
        maint = _sub(
            "maintainability", None, UNAVAILABLE_PRIOR_GOOD, "INFERENCE",
            "no symbols in scope",
        )

    # --- test_coverage: no coverage instrumentation exists ------------------ #
    cov = _sub(
        "test_coverage", None, UNAVAILABLE_PRIOR_GOOD, "INFERENCE",
        "no executed coverage available",
    )

    # --- inverse_dependency_coupling: 1 - clamp(mean fan-in+out / DIVISOR) -- #
    graph = build_networkx(nodes, edges)
    if restrict_to is not None:
        keep = {
            n for n in graph.nodes if _path_of(str(n)) in restrict_to
        }
        graph = graph.subgraph(keep).copy()
    if graph.number_of_nodes() > 0:
        degrees = [graph.in_degree(n) + graph.out_degree(n) for n in graph.nodes]
        mean_deg = sum(degrees) / len(degrees)
        coupling = _sub(
            "inverse_dependency_coupling",
            round(mean_deg, 3),
            round(1.0 - clamp(mean_deg / RHP_COUPLING_DIVISOR), 6),
            "FACT",
        )
    else:
        coupling = _sub(
            "inverse_dependency_coupling", None, UNAVAILABLE_PRIOR_GOOD,
            "INFERENCE", "no code graph in scope",
        )

    # --- churn_stability: Git history is Phase 19 -------------------------- #
    churn = _sub(
        "churn_stability", None, UNAVAILABLE_PRIOR_GOOD, "INFERENCE",
        "no Git history available (Phase 19)",
    )

    # --- documentation_ratio: symbols with a docstring / total ------------- #
    if symbols:
        documented = sum(1 for s in symbols if (s.docstring or "").strip())
        ratio = documented / len(symbols)
        doc = _sub(
            "documentation_ratio",
            round(ratio, 4),
            round(ratio, 6),
            "FACT",
        )
    else:
        doc = _sub(
            "documentation_ratio", None, UNAVAILABLE_PRIOR_GOOD, "INFERENCE",
            "no symbols in scope",
        )

    # --- ci_presence: a CI config file exists ----------------------------- #
    all_files = FileRepository(db).list_for_snapshot(snapshot_id)
    has_ci = any(
        any(marker in f.path.lower() for marker in _CI_MARKERS) for f in all_files
    )
    ci = _sub("ci_presence", 1.0 if has_ci else 0.0, 1.0 if has_ci else 0.0, "FACT")

    subscores = [maint, cov, coupling, churn, doc, ci]
    rhp_raw = 100.0 * sum(c.contribution for c in subscores)
    value = round(rhp_raw)

    risky = _risky_modules(
        symbols, graph_nodes=nodes, graph_edges=edges, restrict_to=restrict_to
    )

    return RHPResult(
        value=value,
        classification=_classify(value),
        subscores=subscores,
        risky_modules=risky,
        model_version=SCORING_MODEL_VERSION,
    )


def _risky_modules(
    symbols, *, graph_nodes, graph_edges, restrict_to: set[str] | None
) -> list[dict]:
    """Top ``1 - RHP_RISKY_MODULES_DECILE`` fraction of files by
    ``centrality * churn * inverse_coverage * complexity``. ``churn`` and
    ``inverse_coverage`` have no data source so contribute 1.0 (documented);
    ``complexity`` is the same span-length proxy as ``maintainability``.
    """
    graph = build_networkx(graph_nodes, graph_edges)
    centrality = compute_centrality(graph)

    loc_by_file: dict[str, list[int]] = {}
    for s in symbols:
        loc_by_file.setdefault(_path_of(s.symbol_id), []).append(
            max(1, (s.end_lineno or s.lineno) - s.lineno + 1)
        )
    paths = sorted(loc_by_file)
    if restrict_to is not None:
        paths = [p for p in paths if p in restrict_to]
    if not paths:
        return []

    scored = []
    for path in paths:
        bt = centrality.get(path, {}).get("betweenness", 0.0)
        locs = loc_by_file[path]
        complexity = clamp((sum(locs) / len(locs)) / RHP_MAINTAINABILITY_LOC_DIVISOR)
        score = round(bt * 1.0 * 1.0 * complexity, 6)
        scored.append(
            {
                "path": path,
                "score": score,
                "centrality": round(bt, 6),
                "churn": None,
                "inverse_coverage": None,
                "complexity": round(complexity, 6),
            }
        )

    scored.sort(key=lambda m: (-m["score"], m["path"]))
    keep = max(1, round(len(scored) * (1.0 - RHP_RISKY_MODULES_DECILE)))
    return [m for m in scored[:keep] if m["score"] > 0.0]
