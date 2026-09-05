"""Code constants for ``mapping-model v1.0.0`` must equal docs/METRICS.md Section 4.

A weight change without a doc + version bump fails here (docs/AEGIS_
IMPLEMENTATION_PLAN.md Section 8 regression gate: "a CI job fails if a later
phase changes a scoring constant ... without bumping the relevant *_version").
"""

from __future__ import annotations

import re
from pathlib import Path

from app.analysis.mapping.fuse import (
    MAPPING_MODEL_VERSION,
    MAPPING_MODEL_WEIGHTS,
    RRF_K,
)

METRICS_MD = Path(__file__).resolve().parents[3] / "docs" / "METRICS.md"

# docs row label (first cell, lowercased prefix) -> code weight key
_ROW_TO_KEY = {
    "lexical": "lexical",
    "symbol-name match": "symbol",
    "graph proximity": "graph",
    "git-history": "git_history",
    "engineering memory": "memory",
    "semantic": "semantic",
}


def _parse_section_4() -> tuple[dict[str, float], int, str]:
    text = METRICS_MD.read_text(encoding="utf-8")
    section = text.split("## 4. ")[1].split("\n## ")[0]
    heading = section.splitlines()[0]

    k_match = re.search(r"k\s*=\s*(\d+)", section)
    assert k_match, "Section 4 must state the RRF k constant"
    k = int(k_match.group(1))

    weights: dict[str, float] = {}
    for line in section.splitlines():
        if not line.startswith("| "):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) < 2 or cells[0].lower() in ("retriever", "---", ""):
            continue
        label = cells[0].lower()
        for prefix, key in _ROW_TO_KEY.items():
            if label.startswith(prefix):
                try:
                    weights[key] = float(cells[1])
                except ValueError:
                    pass
                break
    return weights, k, heading


def test_weights_match_docs():
    doc_weights, doc_k, heading = _parse_section_4()
    assert doc_weights == MAPPING_MODEL_WEIGHTS
    assert doc_k == RRF_K
    assert "mapping-model v1.0.0" in heading
    assert MAPPING_MODEL_VERSION == "mapping-model v1.0.0"
