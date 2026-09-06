"""Custom AST safety rules for code review (docs/AEGIS_IMPLEMENTATION_PLAN.md
Section 24, step 2). Deterministic, no external tools. Every finding cites a
``file`` and a ``line_start``.

Rules: secret literal, eval/exec, subprocess(shell=True), bare except,
except-Exception-pass, test deletion (from the edit-ops), and a new
third-party import.
"""

from __future__ import annotations

import ast
import sys

from aegis.schemas.common import Confidence, Evidence

from app.core.security import contains_secret
from app.review._finding import RawFinding

_STDLIB = set(getattr(sys, "stdlib_module_names", ()))
_LOCAL_HINTS = {"app", "aegis", "tests", "conftest"}


def _ev(file: str, line: int, detail: str) -> list[Evidence]:
    return [Evidence(kind="line_range", ref=f"{file}:{line}", detail=detail)]


def _f(**kw) -> RawFinding:
    kw.setdefault("source", "RULE")
    kw.setdefault("confidence", Confidence(value=0.9, basis="FACT"))
    return RawFinding(**kw)


class _Visitor(ast.NodeVisitor):
    def __init__(self, file: str, known_deps: set[str]) -> None:
        self.file = file
        self.known_deps = known_deps
        self.findings: list[RawFinding] = []

    # --- secret literals ---
    def visit_Constant(self, node: ast.Constant) -> None:  # noqa: N802
        if isinstance(node.value, str) and contains_secret(node.value):
            self.findings.append(
                _f(
                    category="SECURITY",
                    severity="CRITICAL",
                    description="a hard-coded secret-shaped string literal was added",
                    recommendation="move the value to configuration / a secret store",
                    file=self.file,
                    line_start=node.lineno,
                    evidence=_ev(
                        self.file, node.lineno, "matches a known secret pattern"
                    ),
                )
            )
        self.generic_visit(node)

    # --- eval / exec / subprocess(shell=True) ---
    def visit_Call(self, node: ast.Call) -> None:  # noqa: N802
        name = _dotted(node.func)
        if name in ("eval", "exec"):
            self.findings.append(
                _f(
                    category="SECURITY",
                    severity="HIGH",
                    description=f"use of {name}() on constructed input",
                    recommendation=f"replace {name}() with an explicit, safe alternative",
                    file=self.file,
                    line_start=node.lineno,
                    evidence=_ev(self.file, node.lineno, f"{name}() call"),
                )
            )
        if (
            name
            and name.split(".")[-1]
            in ("run", "call", "Popen", "check_call", "check_output")
            and "subprocess" in (name or "")
        ):
            for kw in node.keywords:
                if kw.arg == "shell" and _is_true(kw.value):
                    self.findings.append(
                        _f(
                            category="SECURITY",
                            severity="HIGH",
                            description="subprocess call with shell=True",
                            recommendation="pass an argument list and shell=False",
                            file=self.file,
                            line_start=node.lineno,
                            evidence=_ev(self.file, node.lineno, "shell=True keyword"),
                        )
                    )
        self.generic_visit(node)

    # --- bare / broad except ---
    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> None:  # noqa: N802
        if node.type is None:
            self.findings.append(
                _f(
                    category="ERROR_HANDLING",
                    severity="LOW",
                    description="bare 'except:' catches everything, including exits",
                    recommendation="catch a specific exception type",
                    file=self.file,
                    line_start=node.lineno,
                    evidence=_ev(self.file, node.lineno, "bare except"),
                )
            )
        elif _dotted(node.type) in ("Exception", "BaseException") and _only_pass(
            node.body
        ):
            self.findings.append(
                _f(
                    category="ERROR_HANDLING",
                    severity="MEDIUM",
                    description="broad 'except Exception' with a silent 'pass'",
                    recommendation="handle or log the error, or narrow the type",
                    file=self.file,
                    line_start=node.lineno,
                    evidence=_ev(self.file, node.lineno, "except Exception: pass"),
                )
            )
        self.generic_visit(node)

    # --- new third-party imports ---
    def visit_Import(self, node: ast.Import) -> None:  # noqa: N802
        for alias in node.names:
            self._check_import(alias.name.split(".")[0], node.lineno)
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:  # noqa: N802
        if node.level == 0 and node.module:
            self._check_import(node.module.split(".")[0], node.lineno)
        self.generic_visit(node)

    def _check_import(self, top: str, line: int) -> None:
        if not top or top in _STDLIB or top in _LOCAL_HINTS or top in self.known_deps:
            return
        self.findings.append(
            _f(
                category="DEPENDENCY_IMPACT",
                severity="MEDIUM",
                description=f"import of '{top}', which is not a known project dependency",
                recommendation=(
                    f"confirm '{top}' is intended and add it to the project's "
                    "declared dependencies"
                ),
                file=self.file,
                line_start=line,
                evidence=_ev(self.file, line, f"import {top}"),
            )
        )


def _dotted(node: ast.expr | None) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = _dotted(node.value)
        return f"{base}.{node.attr}" if base else node.attr
    return None


def _is_true(node: ast.expr) -> bool:
    return isinstance(node, ast.Constant) and node.value is True


def _only_pass(body: list[ast.stmt]) -> bool:
    return len(body) == 1 and isinstance(body[0], ast.Pass)


def run_rules(
    files_src: dict[str, str],
    edit_ops: list[dict],
    known_deps: set[str],
) -> list[RawFinding]:
    findings: list[RawFinding] = []

    for path, src in sorted(files_src.items()):
        try:
            tree = ast.parse(src, filename=path)
        except SyntaxError:
            continue
        v = _Visitor(path, known_deps)
        v.visit(tree)
        findings.extend(v.findings)

    findings.extend(_test_deletion(edit_ops))

    findings.sort(key=lambda f: (f.file or "", f.line_start or 0, f.category))
    return findings


def _test_deletion(edit_ops: list[dict]) -> list[RawFinding]:
    out: list[RawFinding] = []
    for op in edit_ops:
        path = op.get("path", "")
        is_test_file = "test" in path.split("/")[-1].lower() and path.endswith(".py")
        removed_test = "def test_" in (op.get("old") or "") and "def test_" not in (
            op.get("new") or ""
        )
        if op.get("op") == "delete" and is_test_file:
            out.append(
                _f(
                    category="TEST_QUALITY",
                    severity="HIGH",
                    description=f"a delete edit removes the test file {path!r}",
                    recommendation="do not delete tests; adjust or add instead",
                    file=path,
                    line_start=1,
                    evidence=_ev(path, 1, "delete op on a test file"),
                )
            )
        elif removed_test:
            out.append(
                _f(
                    category="TEST_QUALITY",
                    severity="HIGH",
                    description=f"an edit to {path!r} removes a 'def test_' without replacing it",
                    recommendation="keep test coverage; update the test rather than deleting it",
                    file=path,
                    line_start=1,
                    evidence=_ev(path, 1, "test function removed by an edit op"),
                )
            )
    return out
