"""Pre-execution static safety scan for AI-generated test code
(docs/SECURITY_MODEL.md Section 2 "malicious tests / generated code", Section 3).

A generated test is untrusted code that AEGIS is about to *run*. Before it is
written into the workspace it is parsed and rejected if it does anything a unit
test has no business doing: ``eval`` / ``exec`` / ``compile`` / ``__import__``,
``os.system`` / ``subprocess`` / ``socket``, a hard-coded secret literal, or a
path that escapes the workspace. The Docker sandbox is still the real
containment boundary -- this is defence in depth that also works in the
Docker-less fake-sandbox path.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

from app.core.security.pathjail import PathJailError, safe_join
from app.core.security.redaction import contains_secret

_PROBE_ROOT = Path("__aegis_probe__").resolve()

# callables a generated test must never invoke (dotted or bare name)
_FORBIDDEN_CALLS: frozenset[str] = frozenset(
    {
        "eval",
        "exec",
        "compile",
        "__import__",
        "os.system",
        "os.popen",
        "os.exec",
        "os.spawn",
        "pty.spawn",
        "socket.socket",
        "socket.create_connection",
        "subprocess.run",
        "subprocess.call",
        "subprocess.Popen",
        "subprocess.check_call",
        "subprocess.check_output",
        "subprocess.getoutput",
        "ctypes.CDLL",
    }
)
# modules a generated test must never import
_FORBIDDEN_IMPORTS: frozenset[str] = frozenset(
    {"subprocess", "socket", "ctypes", "multiprocessing", "resource"}
)


@dataclass(frozen=True)
class SafetyFinding:
    path: str
    line: int
    rule: str
    detail: str


def _dotted(node: ast.expr | None) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = _dotted(node.value)
        return f"{base}.{node.attr}" if base else node.attr
    return None


class _UnsafeVisitor(ast.NodeVisitor):
    def __init__(self, path: str) -> None:
        self.path = path
        self.findings: list[SafetyFinding] = []

    def _add(self, line: int, rule: str, detail: str) -> None:
        self.findings.append(SafetyFinding(self.path, line, rule, detail))

    def visit_Call(self, node: ast.Call) -> None:  # noqa: N802
        name = _dotted(node.func) or ""
        short = name.split(".")[-1]
        if name in _FORBIDDEN_CALLS or short in {
            "eval",
            "exec",
            "compile",
            "__import__",
        }:
            self._add(node.lineno, "forbidden-call", f"call to {name or short}()")
        self.generic_visit(node)

    def visit_Import(self, node: ast.Import) -> None:  # noqa: N802
        for alias in node.names:
            if alias.name.split(".")[0] in _FORBIDDEN_IMPORTS:
                self._add(node.lineno, "forbidden-import", f"import {alias.name}")
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:  # noqa: N802
        if node.module and node.module.split(".")[0] in _FORBIDDEN_IMPORTS:
            self._add(node.lineno, "forbidden-import", f"from {node.module} import ...")
        self.generic_visit(node)

    def visit_Constant(self, node: ast.Constant) -> None:  # noqa: N802
        if isinstance(node.value, str) and contains_secret(node.value):
            self._add(node.lineno, "secret-literal", "hard-coded secret-shaped literal")
        self.generic_visit(node)


def scan_code(path: str, code: str) -> list[SafetyFinding]:
    """Findings for one generated file. A syntax error is itself a finding
    (an unrunnable test should never have been proposed)."""
    findings: list[SafetyFinding] = []
    # workspace-escape check on the declared path (probe root -- never touches disk)
    try:
        safe_join(_PROBE_ROOT, path)
    except PathJailError as exc:
        return [SafetyFinding(path, 0, "path-escape", str(exc))]
    try:
        tree = ast.parse(code, filename=path)
    except SyntaxError as exc:
        return [SafetyFinding(path, exc.lineno or 0, "syntax-error", str(exc))]
    v = _UnsafeVisitor(path)
    v.visit(tree)
    findings.extend(v.findings)
    return findings


def scan_generated_cases(cases) -> list[SafetyFinding]:
    """Findings across every generated case (objects with ``.path`` / ``.code``)."""
    out: list[SafetyFinding] = []
    for case in cases:
        out.extend(scan_code(case.path, case.code))
    return out
