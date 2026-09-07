"""Phase 19 unit: per-file churn aggregation."""

from __future__ import annotations

from app.git.churn import compute_churn
from app.git.history import extract_commits
from tests.unit.test_git_history import _multi_commit_repo


def test_churn_counts_commits_and_authors(tmp_path):
    facts = extract_commits(_multi_commit_repo(tmp_path), max_depth=50)
    churn = compute_churn(facts)

    inv = churn["invoice.py"]
    assert inv.commit_count == 3
    assert inv.distinct_authors == 2  # Ada + Ben
    assert inv.insertions >= 3
    assert inv.last_authored_at is not None

    test = churn["test_invoice.py"]
    assert test.commit_count == 2
    assert test.distinct_authors == 1  # Ada only

    assert churn["README.md"].commit_count == 1


def test_churn_empty_input():
    assert compute_churn([]) == {}
