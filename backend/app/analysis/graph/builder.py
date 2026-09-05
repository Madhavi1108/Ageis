"""Build the code graph from a snapshot's already-computed analysis facts. See
docs/AEGIS_IMPLEMENTATION_PLAN.md Section 13.

A pure function: no DB session, no filesystem access. Everything it needs
(the per-file AST walks, the symbol/dependency facts, and a minimal file
record) is passed in -- it is called from app/analysis/analyze.py right after
symbols and dependencies are persisted for a snapshot, reusing that same pass
rather than re-parsing. This also makes it directly unit-testable with
hand-built inputs (tests/unit/test_graph_builder.py), matching the plan's own
"Unit: resolver on fixtures" requirement.

Node kinds actually produced: FILE, MODULE, CLASS, FUNCTION, TEST, DEPENDENCY
(the remaining Specification node kinds -- REPO, COMMIT, ISSUE, PATCH -- are
schema-only until later phases populate them). Edge kinds actually produced:
IMPORTS, DEFINES, TESTS, CALLS. The remaining edge kinds (MODIFIES,
DEPENDS_ON, CHANGED_BY, RELATED_TO, FIXED_BY, AFFECTS) are schema-only too.

Call resolution is intentionally modest: bare-name and dotted-alias lookups
against the same file's defs and this file's own import table, plus a
self/cls -> enclosing-class heuristic. No type inference. Every resolution
carries one of three confidence labels -- RESOLVED, HEURISTIC, UNRESOLVED --
and an UNRESOLVED call is never asserted as a fact (Specification Section 21).

Known, documented limitations (not silent gaps):
  - Only top-level, single-file modules are resolved (``Path(path).stem ->
    path``); sub-package imports (``import pkg.sub``) are UNRESOLVED.
  - ``from X import a as b`` calling ``b(...)`` is UNRESOLVED: RawImport (see
    app/analysis/python_ast.py) only records the original name ``a``, not the
    alias, and this phase does not extend that Phase-4 file to add it.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from app.analysis.imports import DependencyFact
from app.analysis.python_ast import RawCall, RawWalk
from app.analysis.symbols import SymbolFact


class FileRef(Protocol):
    """The minimal shape builder.py needs from a RepositoryFile row -- kept
    as a Protocol (not an import of the ORM model) so unit tests can pass
    plain objects with no DB involved at all."""

    id: str
    path: str
    is_test: bool


@dataclass(frozen=True)
class NodeFact:
    node_type: str  # FILE | MODULE | CLASS | FUNCTION | TEST | DEPENDENCY
    ref: str  # file path, "{path}::{qualname}" symbol_id, or "dep::{target}"
    label: str
    extra: dict | None = None


@dataclass(frozen=True)
class EdgeFact:
    edge_type: str  # IMPORTS | DEFINES | TESTS | CALLS
    source_ref: str
    target_ref: str
    confidence: str | None = None  # only meaningful for CALLS
    evidence: dict | None = None


@dataclass(frozen=True)
class GraphBuildResult:
    nodes: list[NodeFact] = field(default_factory=list)
    edges: list[EdgeFact] = field(default_factory=list)


def _node_type_for_symbol(kind: str, qualname: str, file_is_test: bool) -> str:
    if kind == "MODULE":
        return "MODULE"
    if kind == "CLASS":
        return "CLASS"
    leaf = qualname.rsplit(".", 1)[-1]
    if file_is_test and leaf.startswith("test"):
        return "TEST"
    return "FUNCTION"


def _import_index(walk: RawWalk) -> tuple[dict[str, str], dict[str, str]]:
    """Per-file import lookup tables built from RawImport, not DependencyFact
    (DependencyFact drops the asname -- see app/analysis/imports.py).

    Returns (alias_to_module, name_to_module):
      alias_to_module: `import X` -> {"X": "X"}; `import X as Y` -> {"Y": "X"}
      name_to_module:  `from X import a, b` -> {"a": "X", "b": "X"}
    """
    alias_to_module: dict[str, str] = {}
    name_to_module: dict[str, str] = {}
    for imp in walk.imports:
        if not imp.imported_names:
            if imp.module:
                alias = imp.asname or imp.module.split(".")[0]
                alias_to_module[alias] = imp.module
        else:
            module = imp.module or ""
            for name in imp.imported_names:
                name_to_module[name] = module
    return alias_to_module, name_to_module


def _resolve_call(
    *,
    caller_qualname: str,
    callee_expr: str,
    file_symbol_index: dict[str, str],
    alias_to_module: dict[str, str],
    name_to_module: dict[str, str],
    module_to_path: dict[str, str],
    symbols_by_path: dict[str, dict[str, str]],
) -> tuple[str, str | None]:
    """Returns (confidence, target_symbol_id). target_symbol_id is None iff
    confidence == "UNRESOLVED"."""
    parts = callee_expr.split(".")

    if len(parts) == 1:
        name = parts[0]
        if name in file_symbol_index:
            return "RESOLVED", file_symbol_index[name]
        if name in name_to_module:
            target_path = module_to_path.get(name_to_module[name].lstrip("."))
            if target_path:
                target_id = symbols_by_path.get(target_path, {}).get(name)
                if target_id:
                    return "RESOLVED", target_id
        return "UNRESOLVED", None

    head, *rest = parts
    remainder = ".".join(rest)

    if head in ("self", "cls"):
        # Heuristic: assume the call targets a method on the enclosing class.
        # No type inference is performed, hence HEURISTIC not RESOLVED.
        enclosing_class = caller_qualname.split(".")[0] if "." in caller_qualname else None
        if enclosing_class:
            candidate = f"{enclosing_class}.{remainder}"
            target_id = file_symbol_index.get(candidate)
            if target_id:
                return "HEURISTIC", target_id
        return "UNRESOLVED", None

    if head in alias_to_module:
        target_path = module_to_path.get(alias_to_module[head].lstrip("."))
        if target_path:
            target_id = symbols_by_path.get(target_path, {}).get(remainder)
            if target_id:
                return "RESOLVED", target_id
        return "UNRESOLVED", None

    return "UNRESOLVED", None


def build_graph(
    *,
    walks: list[RawWalk],
    symbols: list[SymbolFact],
    dependencies: list[DependencyFact],
    files: list[FileRef],
) -> GraphBuildResult:
    nodes: list[NodeFact] = []
    edges: list[EdgeFact] = []
    seen_refs: set[str] = set()

    def add_node(node_type: str, ref: str, label: str, extra: dict | None = None) -> None:
        if ref not in seen_refs:
            nodes.append(NodeFact(node_type=node_type, ref=ref, label=label, extra=extra))
            seen_refs.add(ref)

    file_by_path = {f.path: f for f in files}
    file_path_by_id = {f.id: f.path for f in files}
    walk_by_path = {w.relpath: w for w in walks}
    # Only single-file, top-level modules are resolvable (documented limitation).
    module_to_path = {Path(f.path).stem: f.path for f in files if "/" not in f.path}

    symbols_by_path: dict[str, dict[str, str]] = {}
    symbols_by_file_id: dict[str, list[SymbolFact]] = {}
    for s in symbols:
        path = file_path_by_id.get(s.file_id)
        if path is None:
            continue
        symbols_by_path.setdefault(path, {})[s.qualname] = s.symbol_id
        symbols_by_file_id.setdefault(s.file_id, []).append(s)

    # --- FILE nodes ---
    for f in files:
        add_node("FILE", f.path, f.path)

    # --- symbol nodes + DEFINES edges ---
    for f in files:
        path = f.path
        module_symbol_id = f"{path}::"
        for s in symbols_by_file_id.get(f.id, []):
            node_type = _node_type_for_symbol(s.kind, s.qualname, f.is_test)
            add_node(node_type, s.symbol_id, s.qualname or path, extra={"kind": s.kind, "file": path})
            if s.kind == "MODULE":
                add_node("MODULE", module_symbol_id, path, extra={"kind": "MODULE", "file": path})
                edges.append(EdgeFact(edge_type="DEFINES", source_ref=path, target_ref=module_symbol_id))
                continue
            if "." in s.qualname:
                parent_qualname = s.qualname.rsplit(".", 1)[0]
                parent_id = symbols_by_path.get(path, {}).get(parent_qualname, module_symbol_id)
            else:
                parent_id = module_symbol_id
            edges.append(EdgeFact(edge_type="DEFINES", source_ref=parent_id, target_ref=s.symbol_id))

    # --- IMPORTS edges (file -> file for resolved locals, file -> dependency node otherwise) ---
    for d in dependencies:
        if d.from_file_id is None:
            continue
        path = file_path_by_id.get(d.from_file_id)
        if path is None:
            continue
        if d.classification == "LOCAL":
            target_path = module_to_path.get(d.target.lstrip("."))
            if target_path and target_path in file_by_path and target_path != path:
                edges.append(EdgeFact(edge_type="IMPORTS", source_ref=path, target_ref=target_path))
                continue
        dep_ref = f"dep::{d.target}"
        add_node("DEPENDENCY", dep_ref, d.target, extra={"classification": d.classification})
        edges.append(EdgeFact(edge_type="IMPORTS", source_ref=path, target_ref=dep_ref))

    # --- TESTS edges (test file -> the local file(s) it imports) ---
    for f in files:
        if not f.is_test:
            continue
        walk = walk_by_path.get(f.path)
        if walk is None:
            continue
        for imp in walk.imports:
            if imp.level != 0 or not imp.module:
                continue  # relative-import resolution for TESTS linkage is out of scope
            target_path = module_to_path.get(imp.module.split(".")[0])
            if target_path and target_path in file_by_path and target_path != f.path:
                edges.append(EdgeFact(edge_type="TESTS", source_ref=f.path, target_ref=target_path))

    # --- CALLS edges ---
    for f in files:
        walk = walk_by_path.get(f.path)
        if walk is None or not walk.calls:
            continue
        file_symbol_index = symbols_by_path.get(f.path, {})
        alias_to_module, name_to_module = _import_index(walk)
        for call in walk.calls:
            if not call.callee_expr:
                continue
            caller_id = file_symbol_index.get(call.caller_qualname)
            if caller_id is None:
                continue  # caller itself wasn't captured as a symbol (shouldn't happen)
            confidence, target_id = _resolve_call(
                caller_qualname=call.caller_qualname,
                callee_expr=call.callee_expr,
                file_symbol_index=file_symbol_index,
                alias_to_module=alias_to_module,
                name_to_module=name_to_module,
                module_to_path=module_to_path,
                symbols_by_path=symbols_by_path,
            )
            if target_id is None:
                target_id = f"unresolved::{call.callee_expr}"
                add_node("FUNCTION", target_id, call.callee_expr, extra={"unresolved": True})
            edges.append(
                EdgeFact(
                    edge_type="CALLS",
                    source_ref=caller_id,
                    target_ref=target_id,
                    confidence=confidence,
                    evidence={"lineno": call.lineno, "expr": call.callee_expr},
                )
            )

    return GraphBuildResult(nodes=nodes, edges=edges)
