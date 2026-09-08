"""Build the AEGIS acceptance repository *with crafted Git history* into a
throwaway directory (Phase 24, docs/AEGIS_IMPLEMENTATION_PLAN.md Section 32).

The on-disk fixture ``test-repositories/aegis-acceptance/`` is plain files (no
``.git``) so the ~20 existing ``.git``-less integration tests are unaffected.
This helper replays a scripted multi-commit history whose final working tree is
byte-identical to that fixture, so the full pipeline -- including Phase 19 Git
intelligence and Phase 20 memory -- runs against real history.

Commit history (main scenario):

  1. Initial billing skeleton                       invoice.py, checkout.py
  2. Add order finalization and currency helpers    order_service.py, utils.py,
                                                    test_invoice.py
  3. Fix rounding drift in calculate_total()        invoice.py   <- prior related fix
  4. Add MAX_DISCOUNT config and a boundary test    config.py, task*.md,
                                                    test_invoice.py (known-failing case)

``scripts/build_acceptance_repo.py`` is a thin CLI wrapper around this.
"""

from __future__ import annotations

import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path

import git

_EXCLUDE = {".git", "__pycache__", ".pytest_cache", "gold"}

# An earlier, pre-"prior-fix" formulation of calculate_total -- superseded by
# commit 3 so the *final* file still matches the on-disk fixture exactly.
_EARLY_INVOICE = '''\
"""Invoice total calculation."""


def calculate_total(price, discount):
    return price - (price * discount)
'''

_EARLY_TEST_INVOICE = '''\
from invoice import calculate_total


def test_no_discount():
    assert calculate_total(100.0, 0.0) == 100.0
'''


def _actor(n: int) -> git.Actor:
    names = ["Dana Rivera", "Sam Okafor", "Priya Shah", "Lee Nakamura"]
    return git.Actor(names[n % len(names)], f"{names[n % len(names)].split()[0].lower()}@example.com")


def _commit(repo: git.Repo, paths: list[str], message: str, *, day: int) -> None:
    repo.index.add(paths)
    when = (datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc) + timedelta(days=day)).strftime(
        "%Y-%m-%d %H:%M:%S +0000"
    )
    actor = _actor(day)
    repo.index.commit(message, author=actor, committer=actor, author_date=when, commit_date=when)


def _write(root: Path, rel: str, text: str) -> None:
    target = root / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8", newline="\n")


def _copy_from_source(source: Path, dest: Path, rel: str) -> None:
    _write(dest, rel, (source / rel).read_text(encoding="utf-8"))


def build_acceptance_git_repo(dest: Path, *, source: Path) -> Path:
    """Materialize ``source`` into ``dest`` with a crafted commit history.

    Returns ``dest``. The final working tree equals ``source`` (excluding
    ``.git`` / caches / the out-of-tree ``gold`` dir, which lives under
    ``backend/tests/e2e/gold`` and is never part of the ingested repo).
    """
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    repo = git.Repo.init(dest)
    with repo.config_writer() as cw:
        cw.set_value("user", "name", "AEGIS Acceptance")
        cw.set_value("user", "email", "acceptance@aegis.test")
        cw.set_value("commit", "gpgsign", "false")

    src_files = sorted(
        str(p.relative_to(source)).replace("\\", "/")
        for p in source.rglob("*")
        if p.is_file() and not (_EXCLUDE & set(p.relative_to(source).parts))
    )
    has_history_variant = (source / "invoice.py").exists() and (source / "checkout.py").exists()

    if not has_history_variant:
        # Simple two-commit history for the unfixable variant (or any repo that
        # is not the billing scenario): everything, then a "known-failing test".
        first = [f for f in src_files if not f.startswith("test_")]
        for rel in first:
            _copy_from_source(source, dest, rel)
        _commit(repo, first, "Initial commit", day=0)
        rest = [f for f in src_files if f.startswith("test_")]
        for rel in rest:
            _copy_from_source(source, dest, rel)
        _commit(repo, rest or first, "Add tests (one deliberately failing)", day=3)
        return dest

    # --- billing scenario: four crafted commits -------------------------- #
    _write(dest, "invoice.py", _EARLY_INVOICE)
    _copy_from_source(source, dest, "checkout.py")
    _commit(repo, ["invoice.py", "checkout.py"], "Initial billing skeleton", day=0)

    _copy_from_source(source, dest, "order_service.py")
    _copy_from_source(source, dest, "utils.py")
    _write(dest, "test_invoice.py", _EARLY_TEST_INVOICE)
    _commit(
        repo,
        ["order_service.py", "utils.py", "test_invoice.py"],
        "Add order finalization and currency helpers",
        day=9,
    )

    _copy_from_source(source, dest, "invoice.py")
    _commit(
        repo,
        ["invoice.py"],
        "Fix rounding drift in calculate_total() discount math\n\n"
        "The discount was applied as price - price*discount, which drifts on\n"
        "repeated application. Use price * (1 - discount) instead.",
        day=21,
    )

    tail = [
        f
        for f in src_files
        if f not in {"invoice.py", "checkout.py", "order_service.py", "utils.py"}
    ]
    for rel in tail:
        _copy_from_source(source, dest, rel)
    _commit(
        repo,
        tail,
        "Add MAX_DISCOUNT config and a boundary test for the discount cap\n\n"
        "test_discount_capped_at_50_percent currently FAILS: calculate_total()\n"
        "still applies discounts above the configured maximum in full.",
        day=28,
    )
    return dest
