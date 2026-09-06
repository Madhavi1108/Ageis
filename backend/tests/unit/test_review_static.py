"""Static-analysis layer (ruff)."""

from __future__ import annotations

from app.review.static_checks import run_static


def test_ruff_flags_shell_true_and_reports_tool(tmp_path):
    (tmp_path / "bad.py").write_text(
        "import subprocess\n"
        "def go(x):\n"
        "    return subprocess.run(x, shell=True)\n",
        encoding="utf-8",
    )
    findings, tools_run, gaps = run_static(tmp_path, ["bad.py"])

    assert "ruff" in tools_run
    sec = [f for f in findings if f.category == "SECURITY"]
    assert sec and all(f.severity == "HIGH" for f in sec)
    assert all(f.source == "STATIC" and f.file == "bad.py" for f in sec)
    # bandit / radon / mypy absence is a recorded gap, not a failure
    assert any("bandit" in g for g in gaps)


def test_clean_file_yields_no_findings(tmp_path):
    (tmp_path / "ok.py").write_text(
        "def add(a, b):\n    return a + b\n", encoding="utf-8"
    )
    findings, tools_run, _gaps = run_static(tmp_path, ["ok.py"])
    assert "ruff" in tools_run
    assert findings == []


def test_no_python_files_is_noop(tmp_path):
    findings, tools_run, gaps = run_static(tmp_path, ["README.md"])
    assert findings == []
