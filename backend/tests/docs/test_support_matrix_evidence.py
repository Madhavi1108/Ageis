"""Phase 28 docs gate: every SUPPORTED / PARTIALLY_SUPPORTED row in the MVP
support matrix cites evidence that exists.

Parses docs/MVP_DEFINITION.md §2. The Evidence cell must name a repo path (a
test file, or a doc) that exists -- so a capability can't be claimed with a
dangling or fabricated citation. It does not run the test (the suite does that).
UNSUPPORTED rows may cite `-`.
"""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
MVP = REPO_ROOT / "docs" / "MVP_DEFINITION.md"


def _matrix_rows() -> list[tuple[str, str, str]]:
    text = MVP.read_text(encoding="utf-8")
    section = text.split("## 2. Support matrix")[1].split("\n## ")[0]
    rows = []
    for line in section.splitlines():
        if (
            not line.startswith("| ")
            or line.startswith("| Capability")
            or set(line.strip()) <= {"|", "-", " "}
        ):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 3:
            continue
        rows.append((cells[0], cells[1], cells[2]))
    return rows


_ROWS = _matrix_rows()


def test_matrix_parsed() -> None:
    assert len(_ROWS) >= 25, f"only parsed {len(_ROWS)} matrix rows"


@pytest.mark.parametrize(
    ("capability", "status", "evidence"),
    _ROWS,
    ids=[r[0] for r in _ROWS],
)
def test_supported_rows_have_real_evidence(
    capability: str, status: str, evidence: str
) -> None:
    if status == "UNSUPPORTED":
        return
    assert status.startswith(
        ("SUPPORTED", "PARTIALLY_SUPPORTED")
    ), f"{capability!r}: unexpected status {status!r}"
    # strip a ::node id and surrounding backticks
    raw = evidence.strip().strip("`")
    path_part = raw.split("::", 1)[0]
    assert path_part and path_part != "-", f"{capability!r}: no evidence cited"
    assert (
        REPO_ROOT / path_part
    ).exists(), f"{capability!r}: evidence path does not exist: {path_part}"
