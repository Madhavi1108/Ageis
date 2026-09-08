"""Report serializer + the "numbers are generated, never hard-coded" doc scan
(docs/AEGIS_IMPLEMENTATION_PLAN.md Section 33 -- *Regression* testing).

Fast checks only: the Markdown/JSON/xlsx serializer over a synthetic result, and
structural invariants of the committed ``docs/BENCHMARK_RESULTS.md``. The
end-to-end "regenerate and diff" check lives in
``tests/integration/test_benchmark_pipeline.py`` (``@pytest.mark.benchmark``).
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from benchmarks.metrics import compute_all
from benchmarks.publish import GENERATED_MARKER as PUBLISH_MARKER
from benchmarks.report import GENERATED_MARKER, render_benchmark_markdown, write_reports
from benchmarks.schema import BenchmarkResult, TaskRun, TestEval

REPO_ROOT = Path(__file__).resolve().parents[3]
RESULTS_DOC = REPO_ROOT / "docs" / "BENCHMARK_RESULTS.md"


def _sample_result() -> BenchmarkResult:
    return BenchmarkResult(
        dataset="unit",
        dataset_digest="sha256:deadbeef",
        aegis_git_head="abc1234",
        runs=[
            TaskRun(
                task_id="fix-it", dataset="unit", task_type="BUG",
                terminal_state="COMPLETED", verification_verdict="VERIFIED",
                pipeline_verdict="PARTIAL", verification_label="CORRECT",
                gold_files=["m.py"], predicted_files=["m.py"], patch_generated=True,
                plan_steps_total=1, plan_steps_implemented=1, changed_files=["m.py"],
                tests_generated=1, tests_valid=1, replay_fidelity=1.0,
                test_eval=TestEval(fail_to_pass={"t::a": True}, pass_to_pass={"t::b": True}),
            ),
        ],
    )


def test_write_reports_emits_json_xlsx_markdown(tmp_path):
    paths = write_reports(_sample_result(), tmp_path)
    assert set(paths) == {"json", "xlsx", "markdown"}
    for p in paths.values():
        assert p.exists() and p.stat().st_size > 0

    data = json.loads(paths["json"].read_text(encoding="utf-8"))
    assert data["result"]["dataset"] == "unit"
    assert [m["number"] for m in data["metrics"]] == list(range(1, 17))


def test_markdown_has_generated_marker_and_all_16_rows():
    md = render_benchmark_markdown(_sample_result(), compute_all(_sample_result()))
    assert GENERATED_MARKER in md
    assert "do not edit" in md
    for n in range(1, 17):
        assert re.search(rf"^\| {n} \|", md, re.MULTILINE), f"metric row {n} missing"


def test_markdown_reports_unavailable_metrics_as_na_not_zero():
    # the sample has no reference agents / seeded faults -> #15, #6, #9 must be N/A
    md = render_benchmark_markdown(_sample_result(), compute_all(_sample_result()))
    for n in (6, 9, 15):
        row = re.search(rf"^\| {n} \|.*$", md, re.MULTILINE).group(0)
        assert "N/A" in row and "0.0" not in row


# --------------------------------------------------------------------------- #
# Committed docs/BENCHMARK_RESULTS.md -- structure only (fast)
# --------------------------------------------------------------------------- #


def test_results_doc_exists_and_is_machine_generated():
    assert RESULTS_DOC.exists(), "run `python -m benchmarks publish` and commit the result"
    text = RESULTS_DOC.read_text(encoding="utf-8")
    assert PUBLISH_MARKER in text
    assert "do not edit by hand" in text
    assert "Phase 25" in text


def test_results_doc_has_one_row_per_objective_metric():
    text = RESULTS_DOC.read_text(encoding="utf-8")
    combined = text.split("## 2", 1)[0]  # the combined table section
    for n in range(1, 17):
        assert re.search(rf"^\| {n} \| ", combined, re.MULTILINE), f"metric {n} missing from combined table"


def test_results_doc_states_the_false_complete_gate():
    text = RESULTS_DOC.read_text(encoding="utf-8")
    assert re.search(r"false-complete rate.*ceiling 2%", text, re.IGNORECASE | re.DOTALL)


def test_results_doc_carries_the_mandatory_limitations():
    text = RESULTS_DOC.read_text(encoding="utf-8").lower()
    for needle in ("mockprovider", "no docker", "simulated", "reference agent"):
        assert needle in text, f"limitations section missing {needle!r}"


def test_results_doc_has_no_stray_todo_or_placeholder():
    text = RESULTS_DOC.read_text(encoding="utf-8")
    assert "TODO" not in text
    assert "XXX" not in text
    assert "<value>" not in text
