"""Issue -> code mapping orchestrator (docs/AEGIS_IMPLEMENTATION_PLAN.md Section 15).

All DB / workspace IO lives here; the individual retrievers are pure functions
over the value objects in inputs.py. Flow:

    load files (+ source text) & symbols
      -> lexical + symbol retrievers
      -> seed graph-proximity from their top hits
      -> reciprocal-rank fusion (fuse.py)
      -> threshold + label -> MappingCandidate list (evidence.py)
      -> related tests (graph TESTS edges + test_<module> naming)
      -> dependencies (Dependency rows for candidate files)
      -> heuristic overall_confidence (confidence.py)

An empty result is returned as ``candidates=[]`` + ``overall_confidence=0.0``
(the UNKNOWN case) -- never an exception.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from sqlalchemy.orm import Session

from app.analysis.mapping import graph_proximity, lexical, semantic, symbol_match
from app.analysis.mapping.confidence import overall_confidence
from app.analysis.mapping.evidence import to_candidates
from app.analysis.mapping.fuse import MAPPING_MODEL_VERSION, fuse
from app.analysis.mapping.inputs import FileDoc, SymbolDoc
from app.analysis.mapping.text import split_identifier, tokenize
from app.core.config import Settings
from app.ingestion.workspace import workspace_dir
from app.repository.dependencies import DependencyRepository
from app.repository.files import FileRepository
from app.repository.graph import GraphRepository
from app.repository.symbols import SymbolRepository
from app.schemas.mapping import MappingCandidate

_SEED_LIMIT = 8


@dataclass
class MappingComputation:
    snapshot_id: str
    candidates: list[MappingCandidate]
    related_tests: list[str]
    dependencies: list[str]
    overall_confidence: float
    semantic_available: bool
    model_version: str = MAPPING_MODEL_VERSION
    #: files that could not be indexed (too large) -- provenance, not surfaced in
    #: the API response but logged by the caller.
    skipped_files: list[str] = field(default_factory=list)


def _load_files(
    session: Session, snapshot_id: str, settings: Settings
) -> tuple[list[FileDoc], list[str], dict[str, str]]:
    ws_root = workspace_dir(snapshot_id, settings)
    rows = FileRepository(session).list_for_snapshot(snapshot_id)
    docs: list[FileDoc] = []
    skipped: list[str] = []
    id_to_path: dict[str, str] = {r.id: r.path for r in rows}
    for r in rows:
        if r.language != "python" or r.is_vendored:
            continue
        if r.size_bytes > settings.mapping_max_indexed_file_bytes:
            skipped.append(r.path)
            continue
        abs_path = ws_root / r.path
        try:
            text = abs_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            # Workspace GC'd or file vanished -- index by path alone.
            text = r.path
        docs.append(FileDoc(path=r.path, text=text, is_test=r.is_test))
    return docs, skipped, id_to_path


def _load_symbols(
    session: Session, snapshot_id: str, id_to_path: dict[str, str]
) -> list[SymbolDoc]:
    rows = SymbolRepository(session).list_for_snapshot(snapshot_id)
    out: list[SymbolDoc] = []
    for s in rows:
        path = id_to_path.get(s.file_id) or s.symbol_id.split("::", 1)[0]
        out.append(
            SymbolDoc(
                path=path,
                symbol_id=s.symbol_id,
                qualname=s.qualname,
                kind=s.kind,
                signature=s.signature,
                docstring=s.docstring,
                is_exported=bool(s.is_exported),
            )
        )
    return out


def _related_tests(
    session: Session,
    snapshot_id: str,
    candidate_paths: list[str],
    files: list[FileDoc],
) -> list[str]:
    if not candidate_paths:
        return []
    cand_set = set(candidate_paths)
    cand_stems = {Path(p).stem for p in candidate_paths}
    found: list[str] = []

    # 1. graph TESTS edges whose target file is a candidate.
    graph_repo = GraphRepository(session)
    nodes = {n.id: n for n in graph_repo.list_nodes_for_snapshot(snapshot_id)}
    if nodes:
        for e in graph_repo.list_edges_for_snapshot(snapshot_id, edge_type="TESTS"):
            src = nodes.get(e.source_node_id)
            tgt = nodes.get(e.target_node_id)
            if src is None or tgt is None:
                continue
            tgt_path = tgt.ref.split("::", 1)[0]
            if tgt_path in cand_set:
                test_path = src.ref.split("::", 1)[0]
                if test_path not in found:
                    found.append(test_path)

    # 2. naming heuristic: a test file whose name / tokens name a candidate module.
    for f in files:
        if not f.is_test or f.path in found:
            continue
        stem_parts = split_identifier(f.path)
        if stem_parts & cand_stems or any(
            s in tokenize(f.text)[:200] for s in cand_stems
        ):
            found.append(f.path)

    return sorted(found)


def _dependencies_for(
    session: Session,
    snapshot_id: str,
    candidate_paths: list[str],
    id_to_path: dict[str, str],
) -> list[str]:
    if not candidate_paths:
        return []
    path_to_ids = {}
    for fid, p in id_to_path.items():
        path_to_ids.setdefault(p, set()).add(fid)
    cand_file_ids: set[str] = set()
    for p in candidate_paths:
        cand_file_ids |= path_to_ids.get(p, set())

    out: list[str] = []
    for d in DependencyRepository(session).list_for_snapshot(snapshot_id):
        if d.from_file_id in cand_file_ids and d.classification in (
            "THIRD_PARTY",
            "LOCAL",
        ):
            if d.target not in out:
                out.append(d.target)
    return sorted(out)


def map_issue(
    session: Session,
    *,
    snapshot_id: str,
    issue_text: str,
    settings: Settings,
    top_k: int,
) -> MappingComputation:
    files, skipped, id_to_path = _load_files(session, snapshot_id, settings)
    symbols = _load_symbols(session, snapshot_id, id_to_path)

    lex = lexical.retrieve(issue_text, files, symbols)
    sym = symbol_match.retrieve(issue_text, symbols)
    sem = semantic.retrieve()

    seed_paths: list[str] = []
    for res in (lex, sym):
        for c in res.candidates[:_SEED_LIMIT]:
            if c.path not in seed_paths:
                seed_paths.append(c.path)

    grph = graph_proximity.retrieve(
        session, snapshot_id, seed_paths, hops=settings.mapping_graph_hops
    )

    results = [lex, sym, grph, sem]
    fused = fuse(results)
    candidates = to_candidates(
        fused, threshold=settings.mapping_confidence_threshold, top_k=top_k
    )

    n_available = sum(1 for r in results if r.available)
    conf = overall_confidence(
        fused, semantic_available=sem.available, n_available_retrievers=n_available
    )
    if not candidates:
        conf = 0.0

    cand_paths = [c.path for c in candidates]
    return MappingComputation(
        snapshot_id=snapshot_id,
        candidates=candidates,
        related_tests=_related_tests(session, snapshot_id, cand_paths, files),
        dependencies=_dependencies_for(session, snapshot_id, cand_paths, id_to_path),
        overall_confidence=conf,
        semantic_available=sem.available,
        skipped_files=skipped,
    )
