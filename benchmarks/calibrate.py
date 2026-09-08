"""Scoring-model calibration check (docs/METRICS.md Section 5, EVAL_HARNESS Section 6).

Runs the train/held-out protocol against the curated labeled-verification set,
compares each PCS/CRS constant's implied direction to the ``model_registry``
value, and concludes whether a re-fit is warranted. On the curated deterministic
set the honest answer is always **no**: the labeled sample is far too small for a
statistically meaningful fit, so ``scoring-model v1.0.0`` is retained.

A real calibration needs live-provider runs over a few hundred labeled tasks
(EVAL_HARNESS §1); this module is the seam for that, not a substitute.
"""

from __future__ import annotations

import json
from pathlib import Path

from app.scoring.model_registry import SCORING_MODEL_VERSION
from benchmarks.schema import BenchmarkResult

#: below this many labeled data points a weight/bound re-fit is not defensible
MIN_LABELED_FOR_REFIT = 50


def _split(labeled: list, frac: float = 0.7) -> tuple[list, list]:
    cut = max(1, int(len(labeled) * frac)) if labeled else 0
    return labeled[:cut], labeled[cut:]


def calibrate(result: BenchmarkResult) -> dict:
    labeled = [
        r for r in result.runs
        if r.error is None and r.verification_label is not None
    ]
    train, held_out = _split(labeled)

    tp = sum(r.verification_label == "CORRECT" and r.verification_verdict == "VERIFIED" for r in labeled)
    tn = sum(r.verification_label == "INCORRECT" and r.verification_verdict != "VERIFIED" for r in labeled)
    fp = sum(r.verification_label == "INCORRECT" and r.verification_verdict == "VERIFIED" for r in labeled)
    fn = sum(r.verification_label == "CORRECT" and r.verification_verdict != "VERIFIED" for r in labeled)
    fc_rate = fp / (fp + tn) if (fp + tn) else 0.0

    sufficient = len(train) >= MIN_LABELED_FOR_REFIT
    verdict = "REFIT" if sufficient else "INSUFFICIENT_DATA"

    constants = [
        "PCS_WEIGHTS", "CRS_WEIGHTS", "RHP_WEIGHTS",
        "PCS_SECURITY_GATE", "PCS_HARD_CAP", "UNAVAILABLE_PRIOR_GOOD", "UNAVAILABLE_PRIOR_RISK",
    ]
    per_constant = [
        {
            "constant": c,
            "current_source": "docs/METRICS.md §2 (via app/scoring/model_registry.py)",
            "labeled_n": len(labeled),
            "verdict": verdict,
        }
        for c in constants
    ]

    conclusion = (
        f"{SCORING_MODEL_VERSION} RETAINED — {len(labeled)} labeled data points "
        f"(train={len(train)}, held_out={len(held_out)}) is below the "
        f"{MIN_LABELED_FOR_REFIT}-point threshold for a statistically meaningful re-fit. "
        "A real calibration requires live-provider runs over the full benchmark + labeled "
        "verification sets (EVAL_HARNESS §1)."
    )

    return {
        "model_version": SCORING_MODEL_VERSION,
        "action": "RETAIN",
        "labeled_n": len(labeled),
        "train_n": len(train),
        "held_out_n": len(held_out),
        "confusion": {"tp": tp, "tn": tn, "fp": fp, "fn": fn},
        "false_complete_rate": round(fc_rate, 4),
        "per_constant": per_constant,
        "conclusion": conclusion,
    }


def write_calibration_report(result: BenchmarkResult, out_dir: Path) -> Path:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    report = calibrate(result)
    path = out_dir / "calibration_report.json"
    path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return path
