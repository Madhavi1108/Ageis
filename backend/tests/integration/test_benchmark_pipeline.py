"""Integration coverage for the Phase 25 benchmark harness
(docs/AEGIS_IMPLEMENTATION_PLAN.md Section 33 -- *Integration* and *Acceptance*).

``@pytest.mark.benchmark`` -- slow (drives the real ``app/`` orchestrator over
every task in a dataset, with the mock provider + fake sandbox). Opt in with
``pytest -m benchmark``; the default suite skips it.

Covers:
  * the runner over the 3-task ``micro`` set produces the smoke metrics and is
    **reproducible** (two runs agree on every deterministic metric);
  * the ``seeded`` set actually exercises metrics #6 and #9 and the SAFE_STOP
    path (they are ``N/A`` on ``micro``);
  * ``benchmarks publish`` writes a ``docs/BENCHMARK_RESULTS.md`` whose combined
    table is consistent with a freshly computed one.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from benchmarks.metrics import compute_all
from benchmarks.publish import render_results_doc, run_all
from benchmarks.runner import run_dataset

pytestmark = pytest.mark.benchmark

# metrics whose value is not deterministic across runs (wall-clock based)
_NONDETERMINISTIC = {14}


def _values(result):
    return {m.number: (m.value, m.n, m.basis) for m in compute_all(result)}


def test_micro_smoke_outcomes_and_reproducibility(tmp_path):
    first = run_dataset("micro", workdir=tmp_path / "a")
    second = run_dataset("micro", workdir=tmp_path / "b")

    assert [r.task_id for r in first.runs] == ["discount-cap", "celsius", "add-tax"]
    assert all(r.error is None for r in first.runs)
    # every micro task lands COMPLETED and ground-truth green
    for r in first.runs:
        assert r.terminal_state == "COMPLETED", (r.task_id, r.terminal_state)
        assert r.test_eval.verified_fixed, r.task_id
    # celsius is the introduced-then-repaired one
    celsius = next(r for r in first.runs if r.task_id == "celsius")
    assert celsius.entered_repair and celsius.repair_outcome == "REPAIRED"

    va, vb = _values(first), _values(second)
    for number, a in va.items():
        if number in _NONDETERMINISTIC:
            continue
        assert a == vb[number], f"metric #{number} not reproducible: {a} vs {vb[number]}"

    m = {mm.number: mm for mm in compute_all(first)}
    assert m[12].value == 1.0            # completion rate
    assert m[1].basis == "FACT"          # localization measured
    assert m[8].value == 1.0            # scope compliance
    assert m[6].value is None and m[9].value is None  # not exercised by micro


def test_seeded_set_exercises_regression_and_defect_detection(tmp_path):
    result = run_dataset("seeded", workdir=tmp_path / "seeded")
    by_id = {r.task_id: r for r in result.runs}
    assert set(by_id) == {"mean-empty", "eval-defect", "port-default"}
    assert all(r.error is None for r in result.runs)

    # #6 -- the canned fix silently breaks a pass_to_pass test and is caught
    assert by_id["mean-empty"].is_seeded_regression
    assert by_id["mean-empty"].regression_flagged
    assert by_id["mean-empty"].test_eval.broke_a_pass_to_pass

    # #9 -- the planted eval() call is flagged by the reviewer
    assert by_id["eval-defect"].seeded_defect_kind == "eval_exec"
    assert by_id["eval-defect"].review_flagged_defect
    assert any("SECURITY" in f for f in by_id["eval-defect"].review_findings)

    # SAFE_STOP -- the ineffective repair proposal stalls the bounded loop
    port = by_id["port-default"]
    assert port.entered_repair and port.repair_outcome == "SAFE_STOP"
    assert not port.test_eval.verified_fixed
    assert port.terminal_state != "COMPLETED"  # never signed off

    m = {mm.number: mm for mm in compute_all(result)}
    assert m[6].value == 1.0 and m[6].basis == "FACT"
    assert m[9].value == 1.0 and m[9].basis == "FACT"
    assert m[5].value == 0.0            # the only repairing task SAFE_STOPs
    # no false-complete: every INCORRECT-labeled task stayed out of VERIFIED
    assert "false-complete rate = 0.0" in m[10].note


def test_publish_doc_matches_a_fresh_render(tmp_path):
    results = run_all(workdir=tmp_path / "work")
    rendered = render_results_doc(results)

    committed = (Path(__file__).resolve().parents[3] / "docs" / "BENCHMARK_RESULTS.md")
    assert committed.exists()

    def _metric_lines(text: str) -> list[str]:
        # the combined table rows, minus the CI parenthetical (bootstrap seed is
        # fixed but keep this robust) -- compare metric name + n + formula shape
        out = []
        for line in text.split("## 2", 1)[0].splitlines():
            if line.startswith("| ") and "|" in line[2:]:
                cells = [c.strip() for c in line.strip("|").split("|")]
                if cells and cells[0].isdigit():
                    out.append((cells[0], cells[1], cells[3], cells[4]))  # #, name, n, formula
        return out

    assert _metric_lines(rendered) == _metric_lines(committed.read_text(encoding="utf-8")), (
        "docs/BENCHMARK_RESULTS.md is stale -- run `python -m benchmarks publish`"
    )
