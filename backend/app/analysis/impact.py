"""Impact analysis (docs/AEGIS_IMPLEMENTATION_PLAN.md Section 16,
docs/REPOSITORY_ANALYSIS.md Section 6).

From the Phase 7 issue -> code mapping + the Phase 5 code graph, assemble the
affected surface of a task's predicted change: the changed set, its blast radius
by hop (reverse-graph BFS), direct/indirect callers, related tests, the public
API touched, best-effort config / DB references, ranked regression areas, and a
bundle of the normalised signals the Change Risk Score will consume in Phase 17.

This module computes; it does not score. Signals that need data not produced
until a later phase (a real patch -> Phase 10, coverage -> Phase 12, Git churn /
prior failures -> Phase 19+) are emitted as ``value=None`` with an
``unavailable_reason`` -- never fabricated.

Pure-ish: takes a session + ids + the persisted mapping row, no HTTP, no job
bookkeeping (that is app/services/impact.py).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import networkx as nx
from sqlalchemy.orm import Session

from app.analysis.graph.centrality import compute_centrality
from app.analysis.graph.store import build_networkx
from app.analysis.symbols import _is_route_decorator
from app.core.config import Settings
from app.ingestion.workspace import workspace_dir
from app.repository.files import FileRepository
from app.repository.graph import GraphRepository
from app.repository.symbols import SymbolRepository

# --------------------------------------------------------------------------- #
# Heuristic reference scanners (always basis INFERENCE, Specification Section 21)
# --------------------------------------------------------------------------- #

_CONFIG_PATTERNS = [
    (re.compile(r"\bsettings\.([A-Za-z_][A-Za-z0-9_]*)"), "settings attribute {0}"),
    (re.compile(r"\bos\.environ\[\s*['\"]([^'\"]+)['\"]\s*\]"), "os.environ[{0!r}]"),
    (re.compile(r"\bos\.getenv\(\s*['\"]([^'\"]+)['\"]"), "os.getenv({0!r})"),
    (re.compile(r"(?<!\.)\bgetenv\(\s*['\"]([^'\"]+)['\"]"), "getenv({0!r})"),
]

_DB_PATTERNS = [
    (re.compile(r"class\s+\w+\s*\([^)]*\bBase\b[^)]*\)"), "ORM model (Base subclass)"),
    (re.compile(r"\bmapped_column\(|\bColumn\("), "ORM column definition"),
    (
        re.compile(r"\bimport\s+sqlalchemy\b|\bfrom\s+sqlalchemy\b"),
        "imports sqlalchemy",
    ),
    (re.compile(r"\.(query|execute)\("), "session query/execute call"),
    (
        re.compile(
            r"['\"]\s*(SELECT|INSERT|UPDATE|DELETE|CREATE TABLE)\b", re.IGNORECASE
        ),
        "SQL string literal",
    ),
]

_SECURITY_KEYWORDS = (
    "hashlib",
    "hmac",
    "jwt",
    "secrets",
    "cryptography",
    "bcrypt",
    "argon2",
    "subprocess",
    "os.system",
    "eval(",
    "exec(",
    "pickle",
    "marshal",
    "yaml.load",
    "os.path",
    "pathlib",
    "shutil",
    "socket",
    "requests",
    "urllib",
    "httpx",
    "password",
    "passwd",
    "secret",
    "token",
    "credential",
    "auth",
    "login",
)


@dataclass
class ImpactComputation:
    snapshot_id: str
    changed_set: dict
    blast_radius: dict
    callers: list
    related_tests: list
    public_api_touched: list
    config_refs: list
    db_refs: list
    regression_areas: list
    risk_signal_bundle: dict


def _clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))


def _ref_path(ref: str) -> str:
    return ref.split("::", 1)[0]


# --------------------------------------------------------------------------- #
# Sub-steps
# --------------------------------------------------------------------------- #


def _resolve_changed_set(mapping_candidates: list, symbols) -> dict:
    files = sorted({c["path"] for c in mapping_candidates})
    by_key = {(s.symbol_id.split("::", 1)[0], s.qualname): s.symbol_id for s in symbols}
    resolved: set[str] = set()
    for c in mapping_candidates:
        for qn in c.get("symbols", []):
            sid = by_key.get((c["path"], qn))
            if sid is not None:
                resolved.add(sid)
    return {"files": files, "symbols": sorted(resolved)}


def _blast_radius(graph: nx.MultiDiGraph, seeds: list[str], hops: int) -> dict:
    if not seeds:
        return {}
    reverse = graph.reverse(copy=False)
    min_dist: dict[str, int] = {}
    for seed in seeds:
        if seed not in reverse:
            continue
        for ref, dist in nx.single_source_shortest_path_length(
            reverse, seed, cutoff=hops
        ).items():
            if dist == 0:
                continue
            if ref not in min_dist or dist < min_dist[ref]:
                min_dist[ref] = dist
    grouped: dict[str, list[str]] = {}
    for ref, dist in min_dist.items():
        grouped.setdefault(str(dist), []).append(ref)
    return {k: sorted(v) for k, v in sorted(grouped.items(), key=lambda kv: int(kv[0]))}


def _callers(graph: nx.MultiDiGraph, changed_symbols: list[str], hops: int) -> list:
    out = []
    for sym in changed_symbols:
        if sym not in graph:
            continue
        found: dict[str, tuple[int, str | None]] = {}
        frontier = {sym}
        for hop in range(1, hops + 1):
            next_frontier: set[str] = set()
            for node in frontier:
                for pred, _t, data in graph.in_edges(node, data=True):
                    if data.get("edge_type") != "CALLS":
                        continue
                    conf = data.get("confidence") if hop == 1 else None
                    if pred not in found:
                        found[pred] = (hop, conf)
                        next_frontier.add(pred)
            frontier = next_frontier
            if not frontier:
                break
        if found:
            out.append(
                {
                    "symbol": sym,
                    "callers": [
                        {"ref": ref, "hop": hop, "edge_confidence": conf}
                        for ref, (hop, conf) in sorted(
                            found.items(), key=lambda kv: (kv[1][0], kv[0])
                        )
                    ],
                }
            )
    out.sort(key=lambda e: e["symbol"])
    return out


def _related_tests(
    graph: nx.MultiDiGraph, node_types: dict[str, str], changed_files: set[str]
) -> list[str]:
    found: set[str] = set()
    # 1. graph TESTS edges pointing at a changed file / symbol.
    for u, v, data in graph.edges(data=True):
        if data.get("edge_type") == "TESTS" and _ref_path(v) in changed_files:
            found.add(_ref_path(u))
    # 2. naming heuristic: a TEST/FILE node whose stem names a changed module.
    changed_stems = {Path(p).stem for p in changed_files}
    for ref, ntype in node_types.items():
        if ntype not in ("TEST", "FILE"):
            continue
        path = _ref_path(ref)
        stem = Path(path).stem
        if not stem.startswith("test"):
            continue
        target = stem[len("test") :].lstrip("_")
        if target and target in changed_stems:
            found.add(path)
    return sorted(found)


def _public_api_touched(changed_symbols: list[str], symbols) -> list:
    by_id = {s.symbol_id: s for s in symbols}
    out = []
    for sid in changed_symbols:
        s = by_id.get(sid)
        if s is None:
            continue
        decorators = s.decorators or []
        if any(_is_route_decorator(d) for d in decorators):
            out.append({"symbol_id": sid, "reason": "route"})
        elif s.is_exported:
            out.append({"symbol_id": sid, "reason": "exported"})
    out.sort(key=lambda e: e["symbol_id"])
    return out


def _scan_refs(source_by_path: dict[str, str]) -> tuple[list, list]:
    config_refs: list = []
    db_refs: list = []
    seen_cfg: set[tuple[str, str]] = set()
    seen_db: set[tuple[str, str]] = set()
    for path, src in sorted(source_by_path.items()):
        for pattern, template in _CONFIG_PATTERNS:
            for m in pattern.finditer(src):
                detail = template.format(*m.groups())
                key = (path, detail)
                if key not in seen_cfg:
                    seen_cfg.add(key)
                    config_refs.append(
                        {"ref": path, "detail": detail, "basis": "INFERENCE"}
                    )
        for pattern, detail in _DB_PATTERNS:
            if pattern.search(src):
                key = (path, detail)
                if key not in seen_db:
                    seen_db.add(key)
                    db_refs.append(
                        {"ref": path, "detail": detail, "basis": "INFERENCE"}
                    )
    return config_refs, db_refs


def _security_sensitive(source_by_path: dict[str, str]) -> bool:
    for path, src in source_by_path.items():
        haystack = (path + "\n" + src).lower()
        if any(kw in haystack for kw in _SECURITY_KEYWORDS):
            return True
    return False


def _regression_areas(
    centrality: dict[str, dict[str, float]],
    changed_files: set[str],
    blast_files: set[str],
    limit: int,
) -> list:
    # coverage_gap is 1.0 until Phase 12 supplies real per-file coverage; so this
    # ranks by architectural centrality alone for now (documented limitation).
    coverage_gap = 1.0
    areas = []
    for path in sorted(changed_files | blast_files):
        bt = centrality.get(path, {}).get("betweenness", 0.0)
        score = round(bt * coverage_gap, 6)
        areas.append(
            {
                "path": path,
                "score": score,
                "reason": f"betweenness={bt:.4f}, coverage_gap=1.0 (no coverage until Phase 12)",
            }
        )
    areas.sort(key=lambda a: (-a["score"], a["path"]))
    return areas[:limit]


def _risk_signal_bundle(
    *,
    n_files_changed: int,
    n_impacted: int,
    public_api: bool,
    max_centrality: float,
    security_sensitive: bool,
) -> dict:
    def sig(value, normalized, basis, reason=None):
        return {
            "value": value,
            "normalized": normalized,
            "basis": basis,
            "unavailable_reason": reason,
        }

    return {
        "files_changed": sig(
            float(n_files_changed), _clamp(n_files_changed / 10.0), "FACT"
        ),
        "dependency_impact": sig(
            float(n_impacted), _clamp(n_impacted / 30.0), "INFERENCE"
        ),
        "public_api_touched": sig(
            1.0 if public_api else 0.0, 1.0 if public_api else 0.0, "FACT"
        ),
        "architectural_centrality": sig(
            round(max_centrality, 6), round(_clamp(max_centrality), 6), "FACT"
        ),
        "security_sensitivity": sig(
            1.0 if security_sensitive else 0.0,
            1.0 if security_sensitive else 0.0,
            "INFERENCE",
        ),
        "lines_changed": sig(None, None, "INFERENCE", "no patch until Phase 10"),
        "complexity_delta": sig(None, None, "INFERENCE", "no patch until Phase 10"),
        "inverse_coverage": sig(
            None, None, "INFERENCE", "no executed coverage until Phase 12"
        ),
        "historical_churn": sig(
            None, None, "INFERENCE", "no Git history until Phase 19"
        ),
        "prior_failures": sig(
            None, None, "INFERENCE", "no execution history until Phase 13+"
        ),
    }


# --------------------------------------------------------------------------- #
# Entry point
# --------------------------------------------------------------------------- #


def compute(
    session: Session,
    *,
    snapshot_id: str,
    mapping_candidates: list,
    settings: Settings,
) -> ImpactComputation:
    hops = settings.impact_blast_radius_hops

    symbols = SymbolRepository(session).list_for_snapshot(snapshot_id)
    changed_set = _resolve_changed_set(mapping_candidates, symbols)
    changed_files = set(changed_set["files"])
    changed_symbols = changed_set["symbols"]

    graph_repo = GraphRepository(session)
    nodes = graph_repo.list_nodes_for_snapshot(snapshot_id)
    edges = graph_repo.list_edges_for_snapshot(snapshot_id)
    graph = build_networkx(nodes, edges)
    node_types = {n.ref: n.node_type for n in nodes}

    seeds = [ref for ref in [*changed_symbols, *changed_set["files"]] if ref in graph]
    blast_radius = _blast_radius(graph, seeds, hops)
    n_impacted = sum(len(v) for v in blast_radius.values())

    callers = _callers(graph, changed_symbols, hops)
    related_tests = _related_tests(graph, node_types, changed_files)
    public_api = _public_api_touched(changed_symbols, symbols)

    # Source for the heuristic scanners: the changed files, read from the
    # read-only ingestion workspace (same source app/analysis/analyze.py uses).
    ws_root = workspace_dir(snapshot_id, settings)
    file_rows = {
        r.path: r for r in FileRepository(session).list_for_snapshot(snapshot_id)
    }
    source_by_path: dict[str, str] = {}
    for path in changed_files:
        if path not in file_rows:
            continue
        try:
            source_by_path[path] = (ws_root / path).read_text(
                encoding="utf-8", errors="replace"
            )
        except OSError:
            continue

    config_refs, db_refs = _scan_refs(source_by_path)
    security_sensitive = _security_sensitive(source_by_path)

    centrality = compute_centrality(graph)
    blast_files = {_ref_path(r) for refs in blast_radius.values() for r in refs}
    regression_areas = _regression_areas(
        centrality, changed_files, blast_files, settings.impact_max_regression_areas
    )

    max_centrality = max(
        (centrality.get(ref, {}).get("betweenness", 0.0) for ref in seeds),
        default=0.0,
    )

    risk_signal_bundle = _risk_signal_bundle(
        n_files_changed=len(changed_files),
        n_impacted=n_impacted,
        public_api=bool(public_api),
        max_centrality=max_centrality,
        security_sensitive=security_sensitive,
    )

    return ImpactComputation(
        snapshot_id=snapshot_id,
        changed_set=changed_set,
        blast_radius=blast_radius,
        callers=callers,
        related_tests=related_tests,
        public_api_touched=public_api,
        config_refs=config_refs,
        db_refs=db_refs,
        regression_areas=regression_areas,
        risk_signal_bundle=risk_signal_bundle,
    )
