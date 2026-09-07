"""Phase 19 unit: the four Spec Section 15 history questions."""

from __future__ import annotations

from app.git.history import extract_commits
from app.git.queries import (
    area_changed_recently,
    commits_after,
    is_related_fix,
    similar_fix_before,
)
from app.git.queries import tests_changed_with as co_changed_tests
from tests.unit.test_git_history import _multi_commit_repo


def _facts(tmp_path):
    return extract_commits(_multi_commit_repo(tmp_path), max_depth=50)


def test_is_related_fix():
    assert is_related_fix("fix: clamp discount")
    assert is_related_fix("Resolve regression in totals")
    assert not is_related_fix("add a new feature")


def test_area_changed_recently(tmp_path):
    facts = _facts(tmp_path)
    hits = area_changed_recently(facts, {"invoice.py"}, within_days=3650)
    assert len(hits) == 3
    assert area_changed_recently(facts, {"nonexistent.py"}, within_days=3650) == []


def test_commits_after(tmp_path):
    facts = _facts(tmp_path)  # newest-first
    oldest_sha = facts[-1].sha
    after = commits_after(facts, oldest_sha)
    assert [f.message.splitlines()[0] for f in after] == [
        "add readme",
        "fix: clamp discount at 0.5",
        "tweak invoice rounding",
    ]
    assert commits_after(facts, "deadbeef") == []


def test_similar_fix_before(tmp_path):
    facts = _facts(tmp_path)
    fixes = similar_fix_before(facts, {"invoice.py"})
    assert len(fixes) == 1
    assert fixes[0].message.startswith("fix: clamp discount")
    assert similar_fix_before(facts, {"README.md"}) == []


def test_co_changed_tests(tmp_path):
    facts = _facts(tmp_path)
    assert co_changed_tests(facts, "invoice.py") == {"test_invoice.py"}
    assert co_changed_tests(facts, "README.md") == set()
