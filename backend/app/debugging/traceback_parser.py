"""Parse pytest / unittest failure output into structured records
(docs/AEGIS_IMPLEMENTATION_PLAN.md Section 21, deliverable 1).

Deterministic and defensive: an unrecognised shape yields one ``ParsedFailure``
with ``frames=[]`` and the raw text retained -- never a guessed frame or cause.

Recognised shapes:
  * pytest console ``=== FAILURES ===`` / ``=== ERRORS ===`` sections, with
    ``____ name ____`` blocks, ``E   Exc: msg`` detail lines, short frame lines
    ``path.py:LN: in func`` / ``path.py:LN: ExcType``, and the
    ``=== short test summary info ===`` ``FAILED/ERROR nodeid - msg`` list.
  * chained exceptions ("During handling of the above exception…" / "The above
    exception was the direct cause…") -> ``chained=True``, outermost is primary.
  * the plain Python / unittest ``Traceback (most recent call last):`` +
    ``  File "path", line N, in func`` shape.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

_SECTION_RE = re.compile(r"^=+\s*(FAILURES|ERRORS)\s*=+\s*$")
_ANY_SECTION_RE = re.compile(r"^=+.*=+\s*$")
_BLOCK_TITLE_RE = re.compile(r"^_{3,}\s*(.+?)\s*_{3,}\s*$")
_SUMMARY_HDR_RE = re.compile(r"^=+\s*short test summary info\s*=+\s*$")
_SUMMARY_LINE_RE = re.compile(r"^(FAILED|ERROR)\s+(\S+?)(?:\s+-\s+(.*))?$")
_E_LINE_RE = re.compile(r"^E\s+(.*)$")
_SHORT_FRAME_RE = re.compile(
    r"^(?P<path>[^\s].*?\.py):(?P<lineno>\d+):(?:\s+(?P<rest>.*))?$"
)
_PY_FRAME_RE = re.compile(
    r'^\s+File "(?P<path>[^"]+)", line (?P<lineno>\d+)(?:, in (?P<func>.+))?$'
)
_EXC_LINE_RE = re.compile(
    r"^(?P<exc>[A-Za-z_][\w.]*(?:Error|Exception|Warning|Exit)):?\s*(?P<msg>.*)$"
)
# pytest assertion-rewrite detail: "+  where 10 = calculate_total(100, 0.9)"
_ASSERT_CALL_RE = re.compile(r"(?:where|and)\s+.+?=\s+([A-Za-z_][\w.]*)\s*\(")
_CHAIN_MARKERS = (
    "During handling of the above exception",
    "The above exception was the direct cause",
)


@dataclass
class ParsedFrame:
    file: str
    lineno: int
    func: str | None = None


@dataclass
class ParsedFailure:
    test_name: str
    exception_type: str | None = None
    message: str | None = None
    frames: list[ParsedFrame] = field(default_factory=list)
    chained: bool = False
    raw: str = ""
    #: callables named in the pytest assertion-rewrite detail ("where X = f(...)")
    assertion_calls: list[str] = field(default_factory=list)


# --------------------------------------------------------------------------- #


def _split_sections(lines: list[str]) -> list[list[str]]:
    """Return the body line-lists of every FAILURES / ERRORS section."""
    bodies: list[list[str]] = []
    i = 0
    n = len(lines)
    while i < n:
        if _SECTION_RE.match(lines[i]):
            i += 1
            body: list[str] = []
            while i < n and not _ANY_SECTION_RE.match(lines[i]):
                body.append(lines[i])
                i += 1
            bodies.append(body)
        else:
            i += 1
    return bodies


def _split_blocks(body: list[str]) -> list[tuple[str, list[str]]]:
    blocks: list[tuple[str, list[str]]] = []
    title: str | None = None
    buf: list[str] = []
    for line in body:
        m = _BLOCK_TITLE_RE.match(line)
        if m and "_ _ _" not in line:  # a real block title, not a sub-frame rule
            if title is not None:
                blocks.append((title, buf))
            title = m.group(1)
            buf = []
        else:
            buf.append(line)
    if title is not None:
        blocks.append((title, buf))
    return blocks


def _exc_from_e_lines(e_lines: list[str]) -> tuple[str | None, str | None]:
    for raw in e_lines:
        s = raw.strip()
        if s.startswith("assert "):
            return "AssertionError", s
        m = _EXC_LINE_RE.match(s)
        if m:
            return m.group("exc"), (m.group("msg") or "").strip() or None
    if e_lines:
        return None, e_lines[0].strip()
    return None, None


def _frames_from_block(buf: list[str]) -> list[ParsedFrame]:
    frames: list[ParsedFrame] = []
    for line in buf:
        pm = _PY_FRAME_RE.match(line)
        if pm:
            frames.append(
                ParsedFrame(
                    file=pm.group("path"),
                    lineno=int(pm.group("lineno")),
                    func=(pm.group("func") or "").strip() or None,
                )
            )
            continue
        sm = _SHORT_FRAME_RE.match(line)
        if sm:
            rest = (sm.group("rest") or "").strip()
            func = rest[3:].strip() if rest.startswith("in ") else None
            frames.append(
                ParsedFrame(
                    file=sm.group("path").strip(),
                    lineno=int(sm.group("lineno")),
                    func=func,
                )
            )
    return frames


def _parse_block(title: str, buf: list[str]) -> ParsedFailure:
    text = "\n".join(buf)
    chained = any(mk in text for mk in _CHAIN_MARKERS)
    e_lines = [m.group(1) for line in buf if (m := _E_LINE_RE.match(line))]
    exc_type, message = _exc_from_e_lines(e_lines)

    frames = _frames_from_block(buf)
    # For a chained exception the LAST exception detail / frame group is the
    # outermost (primary) one -- _exc_from_e_lines already scans in order and
    # takes the first assertion/exception line; prefer the last for chained.
    if chained and e_lines:
        for raw in reversed(e_lines):
            s = raw.strip()
            m = _EXC_LINE_RE.match(s)
            if m:
                exc_type, message = (
                    m.group("exc"),
                    (m.group("msg") or "").strip() or None,
                )
                break

    calls: list[str] = []
    for raw in e_lines:
        for m in _ASSERT_CALL_RE.finditer(raw):
            name = m.group(1).split(".")[-1]
            if name not in calls:
                calls.append(name)

    return ParsedFailure(
        test_name=title.strip(),
        exception_type=exc_type,
        message=message,
        frames=frames,
        chained=chained,
        raw=text,
        assertion_calls=calls,
    )


def _parse_plain_traceback(text: str) -> list[ParsedFailure]:
    if "Traceback (most recent call last):" not in text:
        return []
    lines = text.splitlines()
    frames = [
        ParsedFrame(
            file=m.group("path"),
            lineno=int(m.group("lineno")),
            func=(m.group("func") or "").strip() or None,
        )
        for line in lines
        if (m := _PY_FRAME_RE.match(line))
    ]
    exc_type = message = None
    chained = any(mk in text for mk in _CHAIN_MARKERS)
    for line in reversed(lines):
        m = _EXC_LINE_RE.match(line.strip())
        if m and not line.startswith(" "):
            exc_type, message = m.group("exc"), (m.group("msg") or "").strip() or None
            break
    return [
        ParsedFailure(
            test_name="<unknown>",
            exception_type=exc_type,
            message=message,
            frames=frames,
            chained=chained,
            raw=text[:8000],
        )
    ]


def _parse_summary(lines: list[str]) -> list[tuple[str, str, str | None]]:
    """Return (kind, nodeid, message) from the short-summary section."""
    out: list[tuple[str, str, str | None]] = []
    in_summary = False
    for line in lines:
        if _SUMMARY_HDR_RE.match(line):
            in_summary = True
            continue
        if in_summary and _ANY_SECTION_RE.match(line):
            break
        if in_summary:
            m = _SUMMARY_LINE_RE.match(line.strip())
            if m:
                out.append((m.group(1), m.group(2), (m.group(3) or "").strip() or None))
    return out


def _match_summary(failure: ParsedFailure, summary) -> None:
    """Upgrade a block's test_name to the full nodeid and backfill its message
    from the short summary when they clearly correspond."""
    for _kind, nodeid, msg in summary:
        leaf = nodeid.rsplit("::", 1)[-1]
        if leaf == failure.test_name or nodeid.endswith(failure.test_name):
            failure.test_name = nodeid
            if not failure.message and msg:
                failure.message = msg
            return


def parse(raw_text: str) -> list[ParsedFailure]:
    text = raw_text or ""
    lines = text.splitlines()
    summary = _parse_summary(lines)

    failures: list[ParsedFailure] = []
    for body in _split_sections(lines):
        for title, buf in _split_blocks(body):
            failures.append(_parse_block(title, buf))

    if not failures:
        failures = _parse_plain_traceback(text)

    for f in failures:
        _match_summary(f, summary)

    seen = {f.test_name for f in failures}
    for kind, nodeid, msg in summary:
        if nodeid not in seen and not any(
            f.test_name.endswith(nodeid.rsplit("::", 1)[-1]) for f in failures
        ):
            failures.append(
                ParsedFailure(
                    test_name=nodeid,
                    exception_type=(
                        (msg or "").split(":", 1)[0].strip() or None
                        if msg and ":" in msg
                        else None
                    ),
                    message=msg,
                    frames=[],
                    chained=False,
                    raw=f"{kind} {nodeid} - {msg or ''}",
                )
            )

    if not failures:
        failures = [
            ParsedFailure(
                test_name="<unknown>",
                frames=[],
                raw=text[:8000],
            )
        ]
    return failures
