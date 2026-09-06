"""Code constants for ``scoring-model v1.0.0`` must equal docs/METRICS.md
Section 2 (2.1 PCS, 2.2 CRS, 2.3 RHP, 2.5 unavailable-signal priors).

A weight / threshold change without a doc + version bump fails here
(docs/AEGIS_IMPLEMENTATION_PLAN.md Section 8 regression gate; ADR-0017).
Mirrors tests/unit/test_mapping_model_version_sync.py.
"""

from __future__ import annotations

import re
from pathlib import Path

from app.scoring.model_registry import (
    CRS_CLASSIFICATION,
    CRS_WEIGHTS,
    PCS_CLASSIFICATION,
    PCS_HARD_CAP,
    PCS_SECURITY_GATE,
    PCS_WEIGHTS,
    RHP_WEIGHTS,
    SCORING_MODEL_VERSION,
    UNAVAILABLE_PRIOR_GOOD,
    UNAVAILABLE_PRIOR_RISK,
)

METRICS_MD = Path(__file__).resolve().parents[3] / "docs" / "METRICS.md"

_RHP_ROW_TO_KEY = {
    "maintainability index": "maintainability",
    "test coverage": "test_coverage",
    "inverse dependency coupling": "inverse_dependency_coupling",
    "churn stability": "churn_stability",
    "documentation ratio": "documentation_ratio",
    "ci presence": "ci_presence",
}


def _section(heading: str) -> str:
    text = METRICS_MD.read_text(encoding="utf-8")
    return text.split(f"### {heading} ")[1].split("\n### ")[0].split("\n---")[0]


def _table_weights(section: str, weight_col: int) -> dict[str, float]:
    weights: dict[str, float] = {}
    for line in section.splitlines():
        if not line.startswith("| "):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        label = cells[0].strip("`").strip().lower()
        if label in ("signal", "") or set(label) == {"-"}:
            continue
        try:
            weights[label] = float(cells[weight_col])
        except (ValueError, IndexError):
            pass
    return weights


def test_version_string_matches_doc_heading():
    text = METRICS_MD.read_text(encoding="utf-8")
    heading = text.split("## 2. ")[1].splitlines()[0]
    assert "scoring-model v1.0.0" in heading
    assert SCORING_MODEL_VERSION == "scoring-model v1.0.0"


def test_pcs_weights_match_docs():
    doc = _table_weights(_section("2.1"), weight_col=2)
    assert doc == PCS_WEIGHTS


def test_crs_weights_match_docs():
    doc = _table_weights(_section("2.2"), weight_col=2)
    assert doc == CRS_WEIGHTS


def test_rhp_weights_match_docs():
    section = _section("2.3")
    doc: dict[str, float] = {}
    for label, key in _RHP_ROW_TO_KEY.items():
        m = re.search(re.escape(label) + r"\s*`(0\.\d+)`", section, re.IGNORECASE)
        assert m, f"docs/METRICS.md 2.3 must state a weight for {label!r}"
        doc[key] = float(m.group(1))
    assert doc == RHP_WEIGHTS


def test_pcs_thresholds_and_gates_match_docs():
    section = _section("2.1")
    assert re.search(r"`>=\s*85`\s*HIGH", section)
    assert re.search(r"`70[-–]84`\s*MEDIUM", section)
    assert re.search(r"`50[-–]69`\s*LOW", section)
    assert PCS_CLASSIFICATION == {"HIGH": 85, "MEDIUM": 70, "LOW": 50}
    assert re.search(r"caps `PCS` at `40`", section)
    assert PCS_HARD_CAP == 40
    assert "`1.0`" in section and "`0.6`" in section and "`0.0`" in section
    assert PCS_SECURITY_GATE == {
        "clean": 1.0,
        "medium_open": 0.6,
        "high_unresolved": 0.0,
    }


def test_crs_threshold_bands_match_docs():
    section = _section("2.2")
    assert re.search(r"`0[-–]24`\s*LOW", section)
    assert re.search(r"`25[-–]49`\s*MEDIUM", section)
    assert re.search(r"`50[-–]74`\s*HIGH", section)
    assert re.search(r"`75[-–]100`\s*CRITICAL", section)
    assert CRS_CLASSIFICATION == {"LOW": 24, "MEDIUM": 49, "HIGH": 74}


def test_unavailable_priors_match_docs():
    section = _section("2.5")
    good = re.search(r"`UNAVAILABLE_PRIOR_GOOD`\s*\|\s*`(0\.\d+)`", section)
    risk = re.search(r"`UNAVAILABLE_PRIOR_RISK`\s*\|\s*`(0\.\d+|0)`", section)
    assert good and float(good.group(1)) == UNAVAILABLE_PRIOR_GOOD == 0.5
    assert risk and float(risk.group(1)) == UNAVAILABLE_PRIOR_RISK == 0.0
