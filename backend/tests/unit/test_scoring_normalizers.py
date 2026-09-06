"""Signal-collector helpers: diff-line counting, added-branch counting,
the impact-bundle adapter, and clamp bounds/monotonicity.
"""

from __future__ import annotations

from app.scoring._signal import clamp
from app.scoring.signals import _added_branch_count, _bundle_signal, _count_diff_lines


def test_clamp_bounds_and_monotonic():
    assert clamp(-1.0) == 0.0
    assert clamp(2.0) == 1.0
    assert clamp(0.3, 0.2, 1.0) == 0.3
    assert clamp(0.1, 0.2, 1.0) == 0.2
    xs = [clamp(i / 10) for i in range(-3, 14)]
    assert xs == sorted(xs)


def test_count_diff_lines_ignores_headers():
    diff = (
        "--- a/x.py\n"
        "+++ b/x.py\n"
        "@@ -1,2 +1,3 @@\n"
        " keep\n"
        "-old line\n"
        "+new line 1\n"
        "+new line 2\n"
    )
    assert _count_diff_lines(diff) == 3


def test_added_branch_count_counts_new_branches():
    ops = [{"old": "return x", "new": "if x:\n    return x\nreturn 0"}]
    count, reason = _added_branch_count(ops)
    assert reason is None
    assert count == 1


def test_added_branch_count_unparseable_reports_reason():
    count, reason = _added_branch_count([{"old": None, "new": ")("}])
    assert count is None
    assert reason


def test_bundle_signal_available_and_unavailable():
    good = _bundle_signal(
        {"files_changed": {"value": 3.0, "normalized": 0.3, "basis": "FACT"}},
        "files_changed",
        prior=0.0,
    )
    assert good.available and good.normalized == 0.3 and good.basis == "FACT"

    missing = _bundle_signal(
        {"inverse_coverage": {"value": None, "normalized": None,
                              "basis": "INFERENCE",
                              "unavailable_reason": "no executed coverage"}},
        "inverse_coverage",
        prior=0.0,
    )
    assert not missing.available
    assert missing.normalized == 0.0
    assert missing.unavailable_reason == "no executed coverage"
