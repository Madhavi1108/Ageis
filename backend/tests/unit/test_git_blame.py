"""Phase 19 unit: git blame hunks (author emails hashed by the caller)."""

from __future__ import annotations

import hashlib

from app.git.blame import blame_file
from tests.unit.test_git_history import _multi_commit_repo


def _hash(email: str) -> str:
    return hashlib.sha256(f"salt:{email}".encode()).hexdigest()


def test_blame_returns_hashed_hunks(tmp_path):
    repo = _multi_commit_repo(tmp_path)
    hunks = blame_file(repo, "invoice.py", hash_email=_hash)

    assert hunks, "expected at least one blame hunk"
    assert hunks[0].lineno_start == 1
    total_lines = sum(h.line_count for h in hunks)
    assert total_lines == 3  # the final invoice.py has 3 lines
    # emails never appear raw -- only 64-hex digests
    for h in hunks:
        assert len(h.author_email_hash) == 64
        assert "@" not in h.author_email_hash
    assert _hash("ada@example.com") in {h.author_email_hash for h in hunks}


def test_blame_unknown_path_is_empty(tmp_path):
    repo = _multi_commit_repo(tmp_path)
    assert blame_file(repo, "does_not_exist.py", hash_email=_hash) == []
