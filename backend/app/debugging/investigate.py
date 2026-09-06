"""Failure-investigation orchestrator (docs/AEGIS_IMPLEMENTATION_PLAN.md
Section 21). Deterministic, no AI.

parse tracebacks -> classify -> resolve frames to symbols + source ->
bundle evidence -> assemble facts (re-checkable) and inferences (hedged
candidate signals). No root cause is asserted -- that is Phase 14.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.debugging import traceback_parser
from app.debugging.classify import classify
from app.debugging.frames import resolve_frames
from app.ingestion.workspace import workspace_dir
from app.models.test_execution import TestExecution as ExecutionRow
from app.repository.files import FileRepository
from app.repository.graph import GraphRepository
from app.repository.symbols import SymbolRepository
from app.schemas.failure import FailureRecord, Frame


@dataclass
class AnalysedFailure:
    record: dict  # FailureRecord.model_dump()
    raw_traceback: str


@dataclass
class InvestigationResult:
    analysed: list[AnalysedFailure]
    facts: list[str]
    inferences: list[str]
    classification: dict
    evidence: dict
    summary: str
    failure_records: list[dict] = field(default_factory=list)


def _symbol_indexes(session: Session, snapshot_id: str):
    """(by_path, by_leaf_qualname) over the snapshot's symbols. ``by_leaf`` maps
    the last qualname segment -> [(symbol_id, path)] for non-test files, used to
    resolve a callable named in an assertion-rewrite detail line."""
    by_path: dict[str, list[tuple[int, int, str]]] = {}
    by_leaf: dict[str, list[tuple[str, str]]] = {}
    for s in SymbolRepository(session).list_for_snapshot(snapshot_id):
        path = s.symbol_id.split("::", 1)[0]
        by_path.setdefault(path, []).append((s.lineno, s.end_lineno, s.symbol_id))
        leaf = s.qualname.split(".")[-1]
        if leaf and s.kind in ("FUNCTION", "METHOD", "CLASS"):
            by_leaf.setdefault(leaf, []).append((s.symbol_id, path))
    return by_path, by_leaf


def _diff_hunks_for(diff_text: str, files: set[str]) -> list[str]:
    if not diff_text or not files:
        return []
    hunks: list[str] = []
    current: list[str] = []
    keep = False
    for line in diff_text.splitlines():
        if line.startswith("diff --git ") or (line.startswith("--- ") and current):
            if keep and current:
                hunks.append("\n".join(current))
            current = [line]
            keep = any(f in line for f in files)
            continue
        current.append(line)
    if keep and current:
        hunks.append("\n".join(current))
    return hunks


def _related_tests(
    session: Session, snapshot_id: str, frame_files: set[str]
) -> list[str]:
    repo = GraphRepository(session)
    nodes = {n.id: n for n in repo.list_nodes_for_snapshot(snapshot_id)}
    if not nodes:
        return []
    out: list[str] = []
    for e in repo.list_edges_for_snapshot(snapshot_id, edge_type="TESTS"):
        src, tgt = nodes.get(e.source_node_id), nodes.get(e.target_node_id)
        if src is None or tgt is None:
            continue
        if tgt.ref.split("::", 1)[0] in frame_files:
            p = src.ref.split("::", 1)[0]
            if p not in out:
                out.append(p)
    return sorted(out)


def run(
    session: Session,
    *,
    execution_row: ExecutionRow,
    implementation_version: int,
    touched_paths: set[str],
    diff_text: str,
    stdout_text: str,
    stderr_text: str,
    settings: Settings,
) -> InvestigationResult:
    """Entry point -- the service supplies ``touched_paths`` + ``diff_text``
    (both derived from the Implementation row it already holds)."""
    combined = (stdout_text or "") + ("\n" + stderr_text if stderr_text else "")
    parsed = traceback_parser.parse(combined)

    snapshot_id = execution_row.snapshot_id
    symbols_by_path, symbols_by_leaf = _symbol_indexes(session, snapshot_id)
    known_paths = {
        f.path for f in FileRepository(session).list_for_snapshot(snapshot_id)
    }

    ws_root = workspace_dir(snapshot_id, settings)
    frame_files: set[str] = set()
    for pf in parsed:
        for fr in pf.frames:
            frame_files.add(fr.file)
    source_by_path: dict[str, str] = {}
    for p in known_paths:
        if any(p in ff or ff.endswith(Path(p).name) for ff in frame_files):
            try:
                source_by_path[p] = (ws_root / p).read_text(
                    encoding="utf-8", errors="replace"
                )
            except OSError:
                pass

    analysed: list[AnalysedFailure] = []
    facts: list[str] = [
        f"execution v{execution_row.version} outcome = {execution_row.outcome} "
        f"(exit {execution_row.exit_code})"
    ]
    all_types: set[str] = set()
    in_diff_frame_count = 0
    primary_symbol_id: str | None = None
    primary_frame: dict | None = None
    primary_test: str | None = None
    resolved_frame_files: set[str] = set()
    assertion_symbol_candidates: list[str] = []

    for pf in parsed:
        ftype = classify(
            exception_type=pf.exception_type,
            raw_text=pf.raw,
            execution_outcome=execution_row.outcome,
        )
        all_types.add(ftype)
        resolved = resolve_frames(
            pf.frames,
            symbols_by_path=symbols_by_path,
            known_paths=known_paths,
            touched_paths=touched_paths,
            source_by_path=source_by_path,
            slice_lines=settings.investigation_code_slice_lines,
        )
        for rf in resolved:
            resolved_frame_files.add(rf.file)
            if rf.symbol_id:
                facts.append(f"frame {rf.file}:{rf.lineno} is in symbol {rf.symbol_id}")
            if rf.in_diff:
                in_diff_frame_count += 1
                facts.append(
                    f"frame {rf.file}:{rf.lineno} is within an applied edit "
                    f"(implementation v{implementation_version})"
                )

        record = FailureRecord(
            test_name=pf.test_name,
            failure_type=ftype,
            exception_type=pf.exception_type,
            message=pf.message,
            frames=[
                Frame(
                    file=rf.file,
                    lineno=rf.lineno,
                    symbol_id=rf.symbol_id,
                    in_diff=rf.in_diff,
                    code_slice=rf.code_slice,
                )
                for rf in resolved
            ],
            chained=pf.chained,
        )
        facts.append(
            f"{pf.test_name} failed: "
            f"{pf.exception_type or ftype}: {pf.message or '(no message)'}"
        )
        for name in pf.assertion_calls:
            facts.append(
                f"{pf.test_name}: assertion detail references a call to {name}(...)"
            )
            # prefer a candidate in the changed files
            cands = symbols_by_leaf.get(name, [])
            in_diff_cands = [sid for sid, p in cands if p in touched_paths]
            for sid in in_diff_cands or [sid for sid, _ in cands]:
                if sid not in assertion_symbol_candidates:
                    assertion_symbol_candidates.append(sid)

        analysed.append(
            AnalysedFailure(record=record.model_dump(), raw_traceback=pf.raw)
        )

        # deepest resolved frame = where it blew up (pytest prints innermost last),
        # preferring a frame inside the applied change and a non-test symbol.
        deepest = (
            next(
                (
                    rf
                    for rf in reversed(resolved)
                    if rf.symbol_id and rf.in_diff and "::test" not in rf.symbol_id
                ),
                None,
            )
            or next(
                (
                    rf
                    for rf in reversed(resolved)
                    if rf.symbol_id and "::test" not in rf.symbol_id
                ),
                None,
            )
            or next((rf for rf in reversed(resolved) if rf.symbol_id), None)
        )
        if deepest is not None and primary_symbol_id is None:
            primary_symbol_id = deepest.symbol_id
            primary_frame = {"file": deepest.file, "lineno": deepest.lineno}
            primary_test = pf.test_name

    if primary_test is None and analysed:
        primary_test = analysed[0].record["test_name"]

    # A pure assertion failure has no production frame -- fall back to the symbol
    # named in the assertion detail (INFERENCE, recorded below).
    assertion_primary: str | None = None
    if assertion_symbol_candidates and (
        primary_symbol_id is None or "::test" in primary_symbol_id
    ):
        assertion_primary = assertion_symbol_candidates[0]
        primary_symbol_id = assertion_primary
        cand_path = assertion_primary.split("::", 1)[0]
        cand_lineno = next(
            (
                lo
                for lo, _hi, sid in symbols_by_path.get(cand_path, [])
                if sid == assertion_primary
            ),
            None,
        )
        if cand_lineno:
            primary_frame = {"file": cand_path, "lineno": cand_lineno}

    # files relevant to the diff bundle: the resolved frame files plus the
    # implicated symbol's file (a pure assertion failure has no production frame).
    diff_files = set(resolved_frame_files)
    if primary_frame:
        diff_files.add(primary_frame["file"])
    if primary_symbol_id:
        diff_files.add(primary_symbol_id.split("::", 1)[0])

    related_tests = _related_tests(
        session, snapshot_id, resolved_frame_files | diff_files
    )
    diff_hunks = _diff_hunks_for(diff_text, diff_files)

    inferences: list[str] = []
    if primary_symbol_id:
        if assertion_primary:
            kind = "named in the assertion detail"
        elif in_diff_frame_count:
            kind = "deepest in-change frame"
        else:
            kind = "deepest resolved frame"
        inferences.append(
            f"most-implicated symbol ({kind}): {primary_symbol_id} "
            "-- a candidate signal, not a confirmed cause"
        )
    for p in related_tests:
        inferences.append(
            f"related test {p} also exercises the implicated code (candidate context)"
        )
    for af in analysed:
        et = af.record.get("exception_type")
        inferences.append(
            f"{af.record['test_name']}: failure type classified "
            f"{af.record['failure_type']} from "
            f"{'the exception type' if et else 'output markers'}"
        )

    classification = {
        "failure_type": analysed[0].record["failure_type"] if analysed else "ENV",
        "failing_test_count": len(analysed),
        "distinct_failure_types": sorted(all_types),
        "in_diff_frame_count": in_diff_frame_count,
        "primary_test": primary_test,
        "primary_symbol_id": primary_symbol_id,
        "primary_frame": primary_frame,
    }
    evidence = {
        "code_slices": [
            {"file": fr["file"], "lineno": fr["lineno"], "slice": fr["code_slice"]}
            for af in analysed
            for fr in af.record["frames"]
            if fr.get("code_slice")
        ],
        "diff_hunks": diff_hunks,
        "related_tests": related_tests,
        "recent_commits": [],  # Git intelligence is Phase 19
    }
    summary = (
        f"{len(analysed)} failing test(s); "
        f"type(s) {', '.join(sorted(all_types))}; "
        f"primary {primary_test or '<unknown>'}"
        + (f" -> {primary_symbol_id}" if primary_symbol_id else "")
    )

    return InvestigationResult(
        analysed=analysed,
        facts=facts,
        inferences=inferences,
        classification=classification,
        evidence=evidence,
        summary=summary,
        failure_records=[af.record for af in analysed],
    )
