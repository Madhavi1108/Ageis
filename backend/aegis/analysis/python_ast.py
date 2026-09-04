"""Reduced Python AST analysis: symbols (functions/classes) + import
classification. Full design: docs/REPOSITORY_ANALYSIS.md Section 2.

Uses stdlib `ast` only -- never imports or executes target code (Specification
Section 21, "never trust repository files"). A parse failure on one file is
recorded and does not stop analysis of the rest (docs/REPOSITORY_ANALYSIS.md
Section 2, "nothing is guessed").
"""
from __future__ import annotations

import ast
import sys
from dataclasses import dataclass, field

from aegis.repository.ingest import RepositoryFile, Snapshot

_STDLIB_MODULES = set(sys.stdlib_module_names) if hasattr(sys, "stdlib_module_names") else set()


@dataclass(frozen=True)
class Symbol:
    symbol_id: str  # "{relpath}::{qualname}"
    file_path: str
    kind: str  # "function" | "class"
    qualname: str
    lineno: int
    end_lineno: int
    docstring: str | None


@dataclass(frozen=True)
class FileAnalysis:
    file_path: str
    symbols: list[Symbol] = field(default_factory=list)
    imports: list[str] = field(default_factory=list)  # top-level module names
    parse_error: str | None = None


@dataclass(frozen=True)
class RepositoryAnalysis:
    files: dict[str, FileAnalysis] = field(default_factory=dict)

    def all_symbols(self) -> list[Symbol]:
        return [s for fa in self.files.values() for s in fa.symbols]

    def symbols_in(self, file_path: str) -> list[Symbol]:
        fa = self.files.get(file_path)
        return fa.symbols if fa else []


class _Visitor(ast.NodeVisitor):
    def __init__(self, file_path: str) -> None:
        self.file_path = file_path
        self.symbols: list[Symbol] = []
        self.imports: list[str] = []
        self._scope: list[str] = []

    def _qualname(self, name: str) -> str:
        return ".".join([*self._scope, name])

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:  # noqa: N802
        self._add(node, "function")
        self._scope.append(node.name)
        self.generic_visit(node)
        self._scope.pop()

    visit_AsyncFunctionDef = visit_FunctionDef  # noqa: N815 -- same handling

    def visit_ClassDef(self, node: ast.ClassDef) -> None:  # noqa: N802
        self._add(node, "class")
        self._scope.append(node.name)
        self.generic_visit(node)
        self._scope.pop()

    def _add(self, node: ast.AST, kind: str) -> None:
        qualname = self._qualname(node.name)  # type: ignore[attr-defined]
        self.symbols.append(
            Symbol(
                symbol_id=f"{self.file_path}::{qualname}",
                file_path=self.file_path,
                kind=kind,
                qualname=qualname,
                lineno=node.lineno,  # type: ignore[attr-defined]
                end_lineno=getattr(node, "end_lineno", node.lineno),  # type: ignore[attr-defined]
                docstring=ast.get_docstring(node),  # type: ignore[arg-type]
            )
        )

    def visit_Import(self, node: ast.Import) -> None:  # noqa: N802
        for alias in node.names:
            self.imports.append(alias.name.split(".")[0])

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:  # noqa: N802
        if node.module and node.level == 0:
            self.imports.append(node.module.split(".")[0])


def classify_import(module_name: str, local_module_names: set[str]) -> str:
    if module_name in local_module_names:
        return "LOCAL"
    if module_name in _STDLIB_MODULES:
        return "STDLIB"
    return "THIRD_PARTY"


def analyze_file(f: RepositoryFile) -> FileAnalysis:
    try:
        source = f.abs_path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=f.path)
    except (SyntaxError, UnicodeDecodeError) as exc:
        return FileAnalysis(file_path=f.path, parse_error=str(exc))
    visitor = _Visitor(f.path)
    visitor.visit(tree)
    return FileAnalysis(file_path=f.path, symbols=visitor.symbols, imports=visitor.imports)


def analyze(snapshot: Snapshot) -> RepositoryAnalysis:
    files = {f.path: analyze_file(f) for f in snapshot.python_files()}
    return RepositoryAnalysis(files=files)
