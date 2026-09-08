"""Fixtures + auto-marking for the Phase 26 threat suite (docs/SECURITY_MODEL.md).

Every test under ``tests/security/`` is tagged ``@pytest.mark.security`` by the
``pytest_collection_modifyitems`` hook below (no per-file ``pytestmark`` needed).
The suite runs in normal CI -- it is not deselected.
"""

from __future__ import annotations

import os
import stat
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import Settings
from app.models.base import Base

REPO_ROOT = Path(__file__).resolve().parents[3]


def pytest_collection_modifyitems(items) -> None:
    for item in items:
        item.add_marker(pytest.mark.security)


@pytest.fixture
def db_session(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'security.db'}")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine, expire_on_commit=False)()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def security_settings(tmp_path) -> Settings:
    return Settings(
        ingestion_local_roots=[str(REPO_ROOT / "test-repositories"), str(tmp_path)],
        artifacts_root=str(tmp_path / "artifacts"),
        sandbox_mode="fake",
        _env_file=None,
    )


@pytest.fixture
def malicious_repo(tmp_path) -> Path:
    """A hostile source tree built on the fly (never committed).

    Contains a git pre-commit hook payload, a test that opens a socket, a test
    that forks, a symlink pointing outside the tree, and an oversized file.
    """
    root = tmp_path / "aegis-malicious"
    root.mkdir()
    (root / "app.py").write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")
    (root / "test_app.py").write_text(
        "from app import add\n\n\ndef test_add():\n    assert add(1, 2) == 3\n",
        encoding="utf-8",
    )

    hooks = root / ".git" / "hooks"
    hooks.mkdir(parents=True)
    hook = hooks / "pre-commit"
    hook.write_text("#!/bin/sh\ntouch /tmp/aegis_pwned\n", encoding="utf-8")
    try:
        hook.chmod(hook.stat().st_mode | stat.S_IEXEC)
    except OSError:
        pass

    (root / "test_socket.py").write_text(
        "import socket\n\n\ndef test_exfil():\n"
        "    s = socket.socket()\n    s.settimeout(0.1)\n"
        "    s.connect(('example.com', 80))\n",
        encoding="utf-8",
    )
    (root / "test_fork.py").write_text(
        "import os\n\n\ndef test_forkbomb():\n"
        "    for _ in range(3):\n        os.fork()\n",
        encoding="utf-8",
    )
    (root / "big.txt").write_text("A" * (3 * 1024 * 1024), encoding="utf-8")

    outside = tmp_path / "outside_secret.txt"
    outside.write_text("top secret", encoding="utf-8")
    link = root / "escape_link"
    try:
        os.symlink(outside, link)
    except (OSError, NotImplementedError):
        pass  # Windows without privilege -- the traversal tests still cover this

    return root
