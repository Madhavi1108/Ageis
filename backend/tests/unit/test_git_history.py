"""Phase 19 unit: commit-history extraction + the ``_multi_commit_repo``
helper reused by the churn / queries / blame tests.
"""

from __future__ import annotations

from pathlib import Path

import git
import pytest

from app.git.history import extract_commits

_ACTORS = [
    git.Actor("Ada", "ada@example.com"),
    git.Actor("Ben", "ben@example.com"),
]


def _multi_commit_repo(tmp_path: Path) -> git.Repo:
    """A repo with a small, deterministic history:

    c1  add invoice.py + test_invoice.py            (Ada)
    c2  edit invoice.py                              (Ben)
    c3  "fix: clamp discount" invoice.py + test      (Ada)   <- related fix
    c4  add README.md                                (Ben)
    """
    root = tmp_path / "repo"
    root.mkdir()
    repo = git.Repo.init(root)

    def commit(msg: str, actor: git.Actor, files: dict[str, str]) -> None:
        for name, text in files.items():
            (root / name).write_text(text, encoding="utf-8")
        repo.index.add(list(files))
        repo.index.commit(msg, author=actor, committer=actor)

    commit("add invoice", _ACTORS[0], {
        "invoice.py": "def total(p, d):\n    return p * (1 - d)\n",
        "test_invoice.py": "def test_total():\n    assert True\n",
    })
    commit("tweak invoice rounding", _ACTORS[1], {
        "invoice.py": "def total(p, d):\n    return round(p * (1 - d), 2)\n",
    })
    commit("fix: clamp discount at 0.5", _ACTORS[0], {
        "invoice.py": "def total(p, d):\n    d = min(d, 0.5)\n    return round(p * (1 - d), 2)\n",
        "test_invoice.py": "def test_total():\n    assert True\n\ndef test_clamp():\n    assert True\n",
    })
    commit("add readme", _ACTORS[1], {"README.md": "# demo\n"})
    return repo


@pytest.fixture
def multi_commit_repo(tmp_path):
    return _multi_commit_repo(tmp_path)


def test_extract_commits_newest_first_with_stats(multi_commit_repo):
    facts = extract_commits(multi_commit_repo, max_depth=50)
    assert [f.message.splitlines()[0] for f in facts] == [
        "add readme",
        "fix: clamp discount at 0.5",
        "tweak invoice rounding",
        "add invoice",
    ]
    fix = facts[1]
    assert "invoice.py" in fix.files_changed
    assert "test_invoice.py" in fix.files_changed
    assert fix.insertions >= 1
    assert fix.author_email == "ada@example.com"
    assert facts[0].authored_at is not None


def test_extract_commits_honours_max_depth(multi_commit_repo):
    facts = extract_commits(multi_commit_repo, max_depth=2)
    assert len(facts) == 2


def test_extract_commits_on_empty_repo(tmp_path):
    empty = git.Repo.init(tmp_path / "empty")
    assert extract_commits(empty, max_depth=10) == []
