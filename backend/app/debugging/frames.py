"""Resolve traceback frames to repository symbols + source context
(docs/AEGIS_IMPLEMENTATION_PLAN.md Section 21, step 2/3).

A frame (path, lineno) maps to the ``RepositorySymbol`` whose ``symbol_id``
belongs to that file and whose ``[lineno, end_lineno]`` span contains the frame
line; the innermost (smallest) span wins. No match -> ``symbol_id=None`` (never
a guess).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.debugging.traceback_parser import ParsedFrame


@dataclass
class ResolvedFrame:
    file: str
    lineno: int
    symbol_id: str | None
    in_diff: bool
    code_slice: str | None


def _normalise(path: str, known_paths: set[str]) -> str:
    """Best-effort map a printed frame path onto a snapshot-relative path."""
    p = path.replace("\\", "/").lstrip("./")
    if p in known_paths:
        return p
    # strip a leading workspace prefix like '/workspace/' or an absolute prefix
    for kp in known_paths:
        if p.endswith("/" + kp) or p.endswith(kp):
            return kp
    base = Path(p).name
    matches = [kp for kp in known_paths if Path(kp).name == base]
    return matches[0] if len(matches) == 1 else p


def resolve_frames(
    parsed_frames: list[ParsedFrame],
    *,
    symbols_by_path: dict[str, list[tuple[int, int, str]]],
    known_paths: set[str],
    touched_paths: set[str],
    source_by_path: dict[str, str],
    slice_lines: int,
) -> list[ResolvedFrame]:
    resolved: list[ResolvedFrame] = []
    for fr in parsed_frames:
        path = _normalise(fr.file, known_paths)

        symbol_id: str | None = None
        best_span = None
        for lo, hi, sid in symbols_by_path.get(path, []):
            if lo <= fr.lineno <= hi:
                span = hi - lo
                if best_span is None or span < best_span:
                    best_span, symbol_id = span, sid

        code_slice = _slice(source_by_path.get(path), fr.lineno, slice_lines)

        resolved.append(
            ResolvedFrame(
                file=path,
                lineno=fr.lineno,
                symbol_id=symbol_id,
                in_diff=path in touched_paths,
                code_slice=code_slice,
            )
        )
    return resolved


def _slice(source: str | None, lineno: int, ctx: int) -> str | None:
    if not source:
        return None
    lines = source.splitlines()
    if lineno < 1 or lineno > len(lines):
        return None
    start = max(0, lineno - 1 - ctx)
    end = min(len(lines), lineno + ctx)
    out = []
    for i in range(start, end):
        marker = ">>" if (i + 1) == lineno else "  "
        out.append(f"{marker} {i + 1:>4} | {lines[i]}")
    return "\n".join(out)
