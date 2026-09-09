"""Phase 28 docs gate: every relative Markdown link resolves.

Scans README / CONTRIBUTING / CHANGELOG / docs/**.md for `[text](target)` and
bare-path links. A relative file target must exist; a same-file `#anchor` must
match a heading. `http(s)://` and `mailto:` are skipped. Renaming or deleting a
linked doc without fixing the referrers fails here.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]

_LINK = re.compile(r"\[[^\]]*\]\(([^)]+)\)")
_HEADING = re.compile(r"^#{1,6}\s+(.*?)\s*#*\s*$", re.MULTILINE)


def _docs() -> list[Path]:
    files = [REPO_ROOT / n for n in ("README.md", "CONTRIBUTING.md", "CHANGELOG.md")]
    files += sorted((REPO_ROOT / "docs").rglob("*.md"))
    return [f for f in files if f.is_file()]


def _slug(heading: str) -> str:
    s = heading.strip().lower()
    s = re.sub(r"`", "", s)
    s = re.sub(r"[^\w\s-]", "", s)
    return re.sub(r"\s+", "-", s)


def _anchors(text: str) -> set[str]:
    return {_slug(m.group(1)) for m in _HEADING.finditer(text)}


_CASES = [
    (f, m.group(1).strip())
    for f in _docs()
    for m in _LINK.finditer(f.read_text(encoding="utf-8"))
]


@pytest.mark.parametrize(
    ("md_file", "target"),
    _CASES,
    ids=[f"{f.relative_to(REPO_ROOT)}->{t}" for f, t in _CASES],
)
def test_link_resolves(md_file: Path, target: str) -> None:
    if target.startswith(("http://", "https://", "mailto:")):
        pytest.skip("external link")

    path_part, _, anchor = target.partition("#")

    if not path_part:  # same-file anchor
        anchors = _anchors(md_file.read_text(encoding="utf-8"))
        assert _slug(anchor) in anchors, f"{md_file.name}: no heading for #{anchor}"
        return

    resolved = (md_file.parent / path_part).resolve()
    assert resolved.exists(), f"{md_file.relative_to(REPO_ROOT)} -> missing {path_part}"

    if anchor and resolved.suffix == ".md":
        anchors = _anchors(resolved.read_text(encoding="utf-8"))
        assert _slug(anchor) in anchors, f"{resolved.name}: no heading for #{anchor}"


def test_found_some_links() -> None:
    assert len(_CASES) > 20  # guard against the scanner silently matching nothing
