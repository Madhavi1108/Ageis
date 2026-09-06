"""Frame -> symbol resolution + in_diff + code slice."""

from __future__ import annotations

from app.debugging.frames import resolve_frames
from app.debugging.traceback_parser import ParsedFrame

# symbol spans for "mod.py": outer func 3-20, nested helper 8-12
_SYMBOLS = {
    "mod.py": [
        (3, 20, "mod.py::outer"),
        (8, 12, "mod.py::outer.<locals>.helper"),
    ]
}
_SOURCE = {"mod.py": "\n".join(f"line {i}" for i in range(1, 25))}


def _resolve(frames, touched=frozenset()):
    return resolve_frames(
        frames,
        symbols_by_path=_SYMBOLS,
        known_paths={"mod.py"},
        touched_paths=set(touched),
        source_by_path=_SOURCE,
        slice_lines=2,
    )


def test_line_inside_span_resolves_to_symbol():
    [rf] = _resolve([ParsedFrame(file="mod.py", lineno=5)])
    assert rf.symbol_id == "mod.py::outer"


def test_nested_span_picks_innermost():
    [rf] = _resolve([ParsedFrame(file="mod.py", lineno=10)])
    assert rf.symbol_id == "mod.py::outer.<locals>.helper"


def test_unknown_path_yields_none():
    [rf] = _resolve([ParsedFrame(file="ghost.py", lineno=3)])
    assert rf.symbol_id is None
    assert rf.code_slice is None


def test_in_diff_reflects_touched_paths():
    [inside] = _resolve([ParsedFrame(file="mod.py", lineno=5)], touched={"mod.py"})
    [outside] = _resolve([ParsedFrame(file="mod.py", lineno=5)])
    assert inside.in_diff is True
    assert outside.in_diff is False


def test_code_slice_marks_the_frame_line():
    [rf] = _resolve([ParsedFrame(file="mod.py", lineno=5)])
    assert ">>    5 | line 5" in rf.code_slice
    assert "   3 | line 3" in rf.code_slice  # 2 lines of context before


def test_basename_fallback_normalises_absolute_path():
    [rf] = _resolve([ParsedFrame(file="/workspace/mod.py", lineno=5)])
    assert rf.file == "mod.py"
    assert rf.symbol_id == "mod.py::outer"
