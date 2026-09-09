"""Phase 28 docs gate: the 30-point acceptance contract is complete and its
evidence exists.

Parses docs/ACCEPTANCE_CONTRACT.md: Part 1 must have 30 criteria rows, Part 2
must have 20 absolute-rule rows, and every evidence path (before a ``::`` node
id) must exist in the repo.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
CONTRACT = REPO_ROOT / "docs" / "ACCEPTANCE_CONTRACT.md"

_PATH_RE = re.compile(r"`([^`]+)`")


def _rows(section_text: str) -> list[list[str]]:
    out = []
    for line in section_text.splitlines():
        if not line.startswith("| ") or set(line.strip()) <= {"|", "-", " "}:
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if cells and cells[0] in ("#", "Rule", "Criterion"):
            continue
        out.append(cells)
    return out


_TEXT = CONTRACT.read_text(encoding="utf-8")
_PART1 = _TEXT.split("## Part 1")[1].split("## Part 2")[0]
_PART2 = _TEXT.split("## Part 2")[1].split("\n## ")[0]
_CRITERIA = _rows(_PART1)
_RULES = _rows(_PART2)


def test_thirty_criteria() -> None:
    assert len(_CRITERIA) == 30, f"expected 30 criteria rows, got {len(_CRITERIA)}"
    nums = [int(r[0]) for r in _CRITERIA if r[0].isdigit()]
    assert nums == list(range(1, 31))


def test_twenty_absolute_rules() -> None:
    assert len(_RULES) == 20, f"expected 20 rule rows, got {len(_RULES)}"


def _evidence_paths(row: list[str]) -> list[str]:
    cell = row[-1]
    paths = []
    for m in _PATH_RE.finditer(cell):
        tok = m.group(1).split("::", 1)[0].strip()
        if "/" in tok and not tok.startswith(("http", "-")):
            paths.append(tok)
    return paths


@pytest.mark.parametrize(
    "row",
    _CRITERIA + _RULES,
    ids=[r[0] for r in _CRITERIA] + [f"rule{r[0][:12]}" for r in _RULES],
)
def test_evidence_paths_exist(row: list[str]) -> None:
    paths = _evidence_paths(row)
    assert paths, f"row {row[0]!r} cites no concrete evidence path"
    for p in paths:
        assert (REPO_ROOT / p).exists(), f"row {row[0]!r}: missing evidence {p}"
