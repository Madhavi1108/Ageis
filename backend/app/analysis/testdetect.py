"""Test-framework and test-command detection.

See docs/REPOSITORY_ANALYSIS.md Section 3. "record UNKNOWN rather than guess": plain
`test_*.py` naming is compatible with pytest but is not proof of it -- a positive
signal requires actual config (pytest.ini / [tool.pytest.ini_options] / conftest.py) or
AST evidence (a `unittest.TestCase` subclass / `import unittest`).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.analysis.python_ast import RawWalk


@dataclass(frozen=True)
class TestSetup:
    framework: str | None
    command: str | None
    evidence: list[str]


def _has_pytest_ini_options(pyproject_toml_dict: dict | None) -> bool:
    if not pyproject_toml_dict:
        return False
    return "ini_options" in pyproject_toml_dict.get("tool", {}).get("pytest", {})


def detect_test_setup(
    root: Path, walks: list[RawWalk], pyproject: dict | None
) -> TestSetup:
    evidence: list[str] = []

    has_pytest_ini = (root / "pytest.ini").exists()
    has_pytest_section = _has_pytest_ini_options(pyproject)
    has_conftest = any(
        (root / w.relpath).name == "conftest.py" or w.relpath.endswith("/conftest.py")
        for w in walks
    )
    has_tox_ini = (root / "tox.ini").exists()
    has_noxfile = (root / "noxfile.py").exists()

    uses_unittest = any(
        w.uses_unittest_import or w.testcase_class_qualnames for w in walks
    )

    framework: str | None = None
    if has_pytest_ini or has_pytest_section or has_conftest:
        framework = "pytest"
        if has_pytest_ini:
            evidence.append("pytest.ini present")
        if has_pytest_section:
            evidence.append("pyproject.toml [tool.pytest.ini_options] present")
        if has_conftest:
            evidence.append("conftest.py present")
    elif uses_unittest:
        framework = "unittest"
        evidence.append("unittest.TestCase subclass or `import unittest` found")

    command: str | None = None
    if has_pytest_ini or has_pytest_section:
        command = "pytest"
    elif has_tox_ini:
        command = "tox"
        evidence.append("tox.ini present")
    elif has_noxfile:
        command = "nox"
        evidence.append("noxfile.py present")
    elif framework == "pytest":
        command = "pytest"
    elif framework == "unittest":
        command = "python -m unittest"

    return TestSetup(framework=framework, command=command, evidence=evidence)
