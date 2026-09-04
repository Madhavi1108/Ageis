"""Single-file Python AST parsing. Walks the tree once per file and collects everything
downstream modules (symbols.py, imports.py, entrypoints.py, testdetect.py) need, so a file
is never re-parsed per concern.

Never raises: a genuine syntax error or undecodable file is caught and reported on the
returned RawWalk's `parse_error`, mirroring backend/aegis/analysis/python_ast.py's
`analyze_file` resilience pattern (ported and extended here, not reused directly --
that package operates on its own in-memory Snapshot type, this one on real DB rows).
"""

from __future__ import annotations

import ast
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class RawDef:
    kind: str  # "MODULE" | "CLASS" | "FUNCTION" | "METHOD"
    qualname: str
    lineno: int
    end_lineno: int
    decorators: list[str]
    docstring: str | None
    signature: str | None
    is_top_level: bool


@dataclass(frozen=True)
class RawImport:
    module: (
        str | None
    )  # None only for `from . import x` (bare relative, no module name)
    asname: str | None
    level: int  # 0 = absolute, >0 = relative (number of leading dots)
    imported_names: list[
        str
    ]  # names imported via `from X import a, b`; empty for `import X`
    lineno: int


@dataclass(frozen=True)
class RawWalk:
    relpath: str
    parse_error: str | None = None
    module_docstring: str | None = None
    dunder_all: list[str] | None = None
    has_main_guard: bool = False
    defs: list[RawDef] = field(default_factory=list)
    imports: list[RawImport] = field(default_factory=list)
    # (assigned_name, dotted call target) for module-level `name = Call(...)` assignments,
    # e.g. ("app", "FastAPI") -- feeds entrypoints.py's ASGI/WSGI detection.
    module_level_calls: list[tuple[str, str]] = field(default_factory=list)
    uses_unittest_import: bool = False
    testcase_class_qualnames: list[str] = field(default_factory=list)
    has_argparse_call: bool = False
    click_decorated_qualnames: list[str] = field(default_factory=list)


def _dotted_name(node: ast.expr) -> str | None:
    """Render a Name or Attribute chain (e.g. `click.command`) as a dotted string."""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = _dotted_name(node.value)
        return f"{base}.{node.attr}" if base else node.attr
    return None


def _render_param(a: ast.arg, default: ast.expr | None = None, prefix: str = "") -> str:
    text = prefix + a.arg
    if a.annotation is not None:
        text += ": " + ast.unparse(a.annotation)
    if default is not None:
        text += (" = " if a.annotation else "=") + ast.unparse(default)
    return text


def _render_signature(node: ast.FunctionDef | ast.AsyncFunctionDef) -> str | None:
    try:
        args = node.args
        posonly = list(args.posonlyargs)
        combined = posonly + list(args.args)
        defaults = list(args.defaults)
        n, d = len(combined), len(defaults)

        parts: list[str] = []
        for idx, a in enumerate(combined):
            default_idx = idx - (n - d)
            default = defaults[default_idx] if default_idx >= 0 else None
            parts.append(_render_param(a, default))
            if posonly and idx == len(posonly) - 1:
                parts.append("/")

        if args.vararg:
            parts.append(_render_param(args.vararg, prefix="*"))
        elif args.kwonlyargs:
            parts.append("*")

        for a, default in zip(args.kwonlyargs, args.kw_defaults):
            parts.append(_render_param(a, default))

        if args.kwarg:
            parts.append(_render_param(args.kwarg, prefix="**"))

        signature = "(" + ", ".join(parts) + ")"
        if node.returns is not None:
            signature += " -> " + ast.unparse(node.returns)
        return signature
    except Exception:
        # Defensive: signature is a nice-to-have, never worth failing the whole file over.
        return None


def _is_main_guard(node: ast.If) -> bool:
    test = node.test
    if (
        not isinstance(test, ast.Compare)
        or len(test.ops) != 1
        or not isinstance(test.ops[0], ast.Eq)
    ):
        return False
    left, right = test.left, test.comparators[0]

    def _is_dunder_name(n: ast.expr) -> bool:
        return isinstance(n, ast.Name) and n.id == "__name__"

    def _is_main_const(n: ast.expr) -> bool:
        return isinstance(n, ast.Constant) and n.value == "__main__"

    return (_is_dunder_name(left) and _is_main_const(right)) or (
        _is_dunder_name(right) and _is_main_const(left)
    )


class _Visitor(ast.NodeVisitor):
    """Ported from backend/aegis/analysis/python_ast.py::_Visitor, extended with a
    container-kind stack (to distinguish METHOD from FUNCTION) and collection of
    imports, __all__, the __main__ guard, module-level calls, and unittest/click usage.
    """

    def __init__(self, relpath: str, module_docstring: str | None) -> None:
        self.relpath = relpath
        self.defs: list[RawDef] = [
            RawDef(
                kind="MODULE",
                qualname="",
                lineno=1,
                end_lineno=1,
                decorators=[],
                docstring=module_docstring,
                signature=None,
                is_top_level=True,
            )
        ]
        self.imports: list[RawImport] = []
        self.dunder_all: list[str] | None = None
        self.has_main_guard = False
        self.module_level_calls: list[tuple[str, str]] = []
        self.uses_unittest_import = False
        self.testcase_class_qualnames: list[str] = []
        self.has_argparse_call = False
        self.click_decorated_qualnames: list[str] = []

        self._scope: list[str] = []
        self._container_stack: list[str] = []  # "class" | "function"

    def _qualname(self, name: str) -> str:
        return ".".join([*self._scope, name])

    def _decorator_strings(self, decorator_list: list[ast.expr]) -> list[str]:
        rendered = []
        for d in decorator_list:
            try:
                rendered.append(ast.unparse(d))
            except Exception:
                pass
        return rendered

    def visit_Module(self, node: ast.Module) -> None:  # noqa: N802
        for stmt in node.body:
            if (
                isinstance(stmt, ast.If)
                and self._container_stack == []
                and _is_main_guard(stmt)
            ):
                self.has_main_guard = True
            if isinstance(stmt, ast.Assign) and self._is_dunder_all(stmt):
                self.dunder_all = self._extract_dunder_all(stmt)
            if isinstance(stmt, ast.Assign):
                self._record_module_level_call(stmt)
        self.generic_visit(node)

    @staticmethod
    def _is_dunder_all(stmt: ast.Assign) -> bool:
        return (
            len(stmt.targets) == 1
            and isinstance(stmt.targets[0], ast.Name)
            and stmt.targets[0].id == "__all__"
        )

    @staticmethod
    def _extract_dunder_all(stmt: ast.Assign) -> list[str] | None:
        value = stmt.value
        if not isinstance(value, (ast.List, ast.Tuple)):
            return None
        names = []
        for elt in value.elts:
            if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                names.append(elt.value)
            else:
                return None  # non-literal element -- fall through to the next rule
        return names

    def _record_module_level_call(self, stmt: ast.Assign) -> None:
        if len(stmt.targets) != 1 or not isinstance(stmt.targets[0], ast.Name):
            return
        if not isinstance(stmt.value, ast.Call):
            return
        target = _dotted_name(stmt.value.func)
        if target:
            self.module_level_calls.append((stmt.targets[0].id, target))

    def visit_Import(self, node: ast.Import) -> None:  # noqa: N802
        for alias in node.names:
            if alias.name == "unittest" or alias.name.startswith("unittest."):
                self.uses_unittest_import = True
            self.imports.append(
                RawImport(
                    module=alias.name,
                    asname=alias.asname,
                    level=0,
                    imported_names=[],
                    lineno=node.lineno,
                )
            )

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:  # noqa: N802
        if node.module == "unittest" or (
            node.module and node.module.startswith("unittest.")
        ):
            self.uses_unittest_import = True
        self.imports.append(
            RawImport(
                module=node.module,
                asname=None,
                level=node.level,
                imported_names=[a.name for a in node.names],
                lineno=node.lineno,
            )
        )

    def _kind_for_def(self) -> str:
        return (
            "METHOD"
            if self._container_stack and self._container_stack[-1] == "class"
            else "FUNCTION"
        )

    def _visit_function(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        decorators = self._decorator_strings(node.decorator_list)
        is_top_level = not self._container_stack
        self.defs.append(
            RawDef(
                kind=self._kind_for_def(),
                qualname=self._qualname(node.name),
                lineno=node.lineno,
                end_lineno=node.end_lineno or node.lineno,
                decorators=decorators,
                docstring=ast.get_docstring(node),
                signature=_render_signature(node),
                is_top_level=is_top_level,
            )
        )
        if any(
            d in ("click.command", "click.group")
            or d.startswith("click.command(")
            or d.startswith("click.group(")
            for d in decorators
        ):
            self.click_decorated_qualnames.append(self._qualname(node.name))

        self._scope.append(node.name)
        self._container_stack.append("function")
        self.generic_visit(node)
        self._container_stack.pop()
        self._scope.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:  # noqa: N802
        self._visit_function(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:  # noqa: N802
        self._visit_function(node)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:  # noqa: N802
        is_top_level = not self._container_stack
        qualname = self._qualname(node.name)
        self.defs.append(
            RawDef(
                kind="CLASS",
                qualname=qualname,
                lineno=node.lineno,
                end_lineno=node.end_lineno or node.lineno,
                decorators=self._decorator_strings(node.decorator_list),
                docstring=ast.get_docstring(node),
                signature=None,
                is_top_level=is_top_level,
            )
        )
        base_names = [_dotted_name(b) for b in node.bases]
        if any(b and b.endswith("TestCase") for b in base_names):
            self.testcase_class_qualnames.append(qualname)

        self._scope.append(node.name)
        self._container_stack.append("class")
        self.generic_visit(node)
        self._container_stack.pop()
        self._scope.pop()

    def visit_Call(self, node: ast.Call) -> None:  # noqa: N802
        target = _dotted_name(node.func)
        if target in ("argparse.ArgumentParser", "ArgumentParser"):
            self.has_argparse_call = True
        self.generic_visit(node)


def parse_and_walk(abs_path: Path, relpath: str) -> RawWalk:
    """Read + parse one file, returning a RawWalk. Never raises -- a syntax error or
    decode failure is captured on RawWalk.parse_error, and every other field is left at
    its empty default so callers can treat a failed file uniformly."""
    try:
        source = abs_path.read_text(encoding="utf-8", errors="strict")
        tree = ast.parse(source, filename=relpath)
    except (SyntaxError, UnicodeDecodeError, ValueError) as exc:
        return RawWalk(relpath=relpath, parse_error=str(exc))

    module_docstring = ast.get_docstring(tree)
    visitor = _Visitor(relpath, module_docstring)
    visitor.visit(tree)

    return RawWalk(
        relpath=relpath,
        module_docstring=module_docstring,
        dunder_all=visitor.dunder_all,
        has_main_guard=visitor.has_main_guard,
        defs=visitor.defs,
        imports=visitor.imports,
        module_level_calls=visitor.module_level_calls,
        uses_unittest_import=visitor.uses_unittest_import,
        testcase_class_qualnames=visitor.testcase_class_qualnames,
        has_argparse_call=visitor.has_argparse_call,
        click_decorated_qualnames=visitor.click_decorated_qualnames,
    )
