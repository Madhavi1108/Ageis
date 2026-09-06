"""Custom AST safety rules."""

from __future__ import annotations

from app.review.rules import run_rules


def _cats(findings):
    return {(f.category, f.severity) for f in findings}


def test_secret_literal_is_critical():
    src = 'TOKEN = "sk-abcdef0123456789abcdef0123"\n'
    f = run_rules({"a.py": src}, [], set())
    assert ("SECURITY", "CRITICAL") in _cats(f)
    assert all(x.file == "a.py" and x.line_start for x in f)


def test_eval_and_shell_true_are_high():
    src = (
        "import subprocess\n"
        "def go(x):\n"
        "    eval(x)\n"
        "    subprocess.run(x, shell=True)\n"
    )
    f = run_rules({"m.py": src}, [], {"subprocess"})
    sec = [x for x in f if x.category == "SECURITY"]
    assert len(sec) == 2
    assert all(x.severity == "HIGH" for x in sec)


def test_bare_except_low_and_broad_pass_medium():
    src = (
        "def a():\n    try:\n        x()\n    except:\n        y()\n"
        "def b():\n    try:\n        x()\n    except Exception:\n        pass\n"
    )
    cats = _cats(run_rules({"e.py": src}, [], set()))
    assert ("ERROR_HANDLING", "LOW") in cats
    assert ("ERROR_HANDLING", "MEDIUM") in cats


def test_new_dependency_flagged_when_not_known():
    f = run_rules({"x.py": "import requests\n"}, [], {"invoice"})
    assert ("DEPENDENCY_IMPACT", "MEDIUM") in _cats(f)
    # a known dep or stdlib is not flagged
    assert run_rules({"x.py": "import os\nimport requests\n"}, [], {"requests"}) == []


def test_test_deletion_from_edit_ops():
    ops = [{"path": "tests/test_thing.py", "op": "delete", "old": None, "new": None}]
    f = run_rules({}, ops, set())
    assert ("TEST_QUALITY", "HIGH") in _cats(f)

    ops2 = [
        {
            "path": "test_x.py",
            "op": "replace",
            "old": "def test_a():\n    assert 1\n",
            "new": "# gone\n",
        }
    ]
    assert ("TEST_QUALITY", "HIGH") in _cats(run_rules({}, ops2, set()))


def test_clean_code_has_no_findings():
    src = "def add(a, b):\n    return a + b\n"
    assert run_rules({"clean.py": src}, [], set()) == []
