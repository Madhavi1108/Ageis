"""Phase 24 -- the controlled acceptance repository has all nine required
properties, its Python is importable, its baseline test state is the seeded bug,
its gold-artifact files are schema-valid, and its Git history builds to a tree
identical to the on-disk fixture (docs/AEGIS_IMPLEMENTATION_PLAN.md Section 32).
"""

from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path

import pytest

from tests.e2e._acceptance_repo import build_acceptance_git_repo
from tests.e2e._gold import GoldScenario, all_gold

ROOT = Path(__file__).resolve().parents[3]
ACC = ROOT / "test-repositories" / "aegis-acceptance"
UNFIX = ROOT / "test-repositories" / "aegis-acceptance-unfixable"


def _py_files(root: Path) -> list[Path]:
    return sorted(p for p in root.rglob("*.py") if "__pycache__" not in p.parts)


@pytest.mark.parametrize("root", [ACC, UNFIX], ids=["acceptance", "unfixable"])
def test_all_python_parses(root: Path):
    for p in _py_files(root):
        ast.parse(p.read_text(encoding="utf-8"), filename=str(p))


def test_baseline_test_state_is_the_seeded_bug(tmp_path):
    """On the raw fixture: the no-discount test passes and the discount-cap test
    fails -- the reproducible bug the pipeline must fix."""
    work = tmp_path / "acc"
    work.mkdir()
    for p in _py_files(ACC):
        (work / p.name).write_text(p.read_text(encoding="utf-8"), encoding="utf-8")
    res = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "test_invoice.py", "--no-header"],
        cwd=work,
        capture_output=True,
        text=True,
    )
    assert res.returncode != 0, res.stdout
    assert "test_no_discount PASSED" in res.stdout or "1 passed" in res.stdout
    assert "test_discount_capped_at_50_percent" in res.stdout
    assert "failed" in res.stdout


def test_nine_required_properties():
    names = {p.name for p in ACC.iterdir()}
    modules = {p.name for p in _py_files(ACC) if not p.name.startswith("test_")}

    # 1 multiple Python modules
    assert len(modules) >= 4
    # 2 dependency relationships (checkout + order_service both import invoice)
    assert "from invoice import" in (ACC / "checkout.py").read_text()
    assert "import invoice" in (ACC / "order_service.py").read_text()
    # 3 existing tests
    assert (ACC / "test_invoice.py").exists()
    # 4 intentionally incomplete behaviour + 5 a reproducible bug
    assert "does not cap" in (ACC / "invoice.py").read_text().lower()
    # 6 at least one feature request
    assert (ACC / "task_feature.md").exists()
    # 7 test gaps: checkout.py / order_service.py have no dedicated test file
    assert not (ACC / "test_checkout.py").exists()
    assert not (ACC / "test_order_service.py").exists()
    # 8 realistic architecture: a config module distinct from logic
    assert (ACC / "config.py").exists()
    # 9 a bug task alongside the feature task
    assert (ACC / "task.md").exists()
    assert "task.md" in names and "task_feature.md" in names


def test_gold_files_are_schema_valid():
    gold = all_gold()
    assert set(gold) == {"scenario_a", "scenario_b", "scenario_c"}
    for g in gold.values():
        assert isinstance(g, GoldScenario)
        assert g.expected_files_modified
        assert g.kind in {"BUG", "FEATURE"}


def test_crafted_git_history_builds_to_the_fixture_tree(tmp_path):
    dest = tmp_path / "acc"
    build_acceptance_git_repo(dest, source=ACC)

    log = subprocess.run(
        ["git", "-C", str(dest), "log", "--format=%s"], capture_output=True, text=True
    ).stdout.splitlines()
    assert len(log) == 4
    assert any("rounding drift" in line.lower() for line in log)  # the prior related fix

    for p in _py_files(ACC) + [ACC / "task.md", ACC / "task_feature.md"]:
        rel = p.relative_to(ACC)
        assert (dest / rel).read_text(encoding="utf-8") == p.read_text(encoding="utf-8")

    # invoice.py was touched by more than one commit (churn / blame signal)
    touched = subprocess.run(
        ["git", "-C", str(dest), "log", "--format=%H", "--", "invoice.py"],
        capture_output=True,
        text=True,
    ).stdout.split()
    assert len(touched) >= 2
