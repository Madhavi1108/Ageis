"""Unit tests for the call resolver and graph builder. See
docs/AEGIS_IMPLEMENTATION_PLAN.md Section 13 "Unit: resolver on fixtures
(local call, imported call, aliased import, method call, unresolved
dynamic)". No DB, no filesystem -- build_graph is a pure function over
hand-built RawWalk/SymbolFact/DependencyFact/FileRef inputs.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.analysis.graph.builder import build_graph
from app.analysis.imports import DependencyFact
from app.analysis.python_ast import RawCall, RawImport, RawWalk
from app.analysis.symbols import SymbolFact


@dataclass(frozen=True)
class _File:
    id: str
    path: str
    is_test: bool = False


def _symbol(file_id, path, qualname, kind=None) -> SymbolFact:
    if kind is None:
        kind = "MODULE" if qualname == "" else "FUNCTION"
    return SymbolFact(
        file_id=file_id,
        symbol_id=f"{path}::{qualname}",
        kind=kind,
        qualname=qualname,
        signature=None,
        lineno=1,
        end_lineno=1,
        decorators=[],
        docstring=None,
        is_exported=True,
    )


def _edges_by_type(result, edge_type):
    return [e for e in result.edges if e.edge_type == edge_type]


def test_local_call_same_file_resolves():
    """A bare-name call to a function defined in the same file."""
    files = [_File("f1", "a.py")]
    walk = RawWalk(
        relpath="a.py",
        calls=[RawCall(caller_qualname="caller", callee_expr="helper", lineno=2)],
    )
    symbols = [
        _symbol("f1", "a.py", ""),  # MODULE
        _symbol("f1", "a.py", "caller"),
        _symbol("f1", "a.py", "helper"),
    ]
    result = build_graph(walks=[walk], symbols=symbols, dependencies=[], files=files)
    calls = _edges_by_type(result, "CALLS")
    assert len(calls) == 1
    assert calls[0].source_ref == "a.py::caller"
    assert calls[0].target_ref == "a.py::helper"
    assert calls[0].confidence == "RESOLVED"


def test_imported_call_from_import_resolves():
    """`from invoice import calculate_total` then a bare `calculate_total(...)` call."""
    files = [_File("f1", "checkout.py"), _File("f2", "invoice.py")]
    walk_checkout = RawWalk(
        relpath="checkout.py",
        imports=[RawImport(module="invoice", asname=None, level=0, imported_names=["calculate_total"], lineno=1)],
        calls=[RawCall(caller_qualname="process", callee_expr="calculate_total", lineno=3)],
    )
    walk_invoice = RawWalk(relpath="invoice.py")
    symbols = [
        _symbol("f1", "checkout.py", ""),
        _symbol("f1", "checkout.py", "process"),
        _symbol("f2", "invoice.py", ""),
        _symbol("f2", "invoice.py", "calculate_total"),
    ]
    deps = [DependencyFact(kind="IMPORT", from_file_id="f1", target="invoice", classification="LOCAL")]
    result = build_graph(walks=[walk_checkout, walk_invoice], symbols=symbols, dependencies=deps, files=files)
    calls = _edges_by_type(result, "CALLS")
    assert len(calls) == 1
    assert calls[0].source_ref == "checkout.py::process"
    assert calls[0].target_ref == "invoice.py::calculate_total"
    assert calls[0].confidence == "RESOLVED"


def test_aliased_import_attribute_call_resolves():
    """`import invoice as inv` then `inv.calculate_total(...)`."""
    files = [_File("f1", "order.py"), _File("f2", "invoice.py")]
    walk_order = RawWalk(
        relpath="order.py",
        imports=[RawImport(module="invoice", asname="inv", level=0, imported_names=[], lineno=1)],
        calls=[RawCall(caller_qualname="finalize", callee_expr="inv.calculate_total", lineno=3)],
    )
    walk_invoice = RawWalk(relpath="invoice.py")
    symbols = [
        _symbol("f1", "order.py", ""),
        _symbol("f1", "order.py", "finalize"),
        _symbol("f2", "invoice.py", ""),
        _symbol("f2", "invoice.py", "calculate_total"),
    ]
    result = build_graph(walks=[walk_order, walk_invoice], symbols=symbols, dependencies=[], files=files)
    calls = _edges_by_type(result, "CALLS")
    assert len(calls) == 1
    assert calls[0].target_ref == "invoice.py::calculate_total"
    assert calls[0].confidence == "RESOLVED"


def test_method_call_via_self_is_heuristic():
    """`self.baz()` inside a method -> resolved to Class.baz, labelled HEURISTIC
    (no type inference actually confirms `self` is that class)."""
    files = [_File("f1", "a.py")]
    walk = RawWalk(
        relpath="a.py",
        calls=[RawCall(caller_qualname="Foo.bar", callee_expr="self.baz", lineno=3)],
    )
    symbols = [
        _symbol("f1", "a.py", ""),
        _symbol("f1", "a.py", "Foo", kind="CLASS"),
        _symbol("f1", "a.py", "Foo.bar", kind="METHOD"),
        _symbol("f1", "a.py", "Foo.baz", kind="METHOD"),
    ]
    result = build_graph(walks=[walk], symbols=symbols, dependencies=[], files=files)
    calls = _edges_by_type(result, "CALLS")
    assert len(calls) == 1
    assert calls[0].source_ref == "a.py::Foo.bar"
    assert calls[0].target_ref == "a.py::Foo.baz"
    assert calls[0].confidence == "HEURISTIC"


def test_unresolved_dynamic_call_is_labelled_not_dropped():
    """A call to something not locally defined, not imported, and not a
    self/cls method -- e.g. a call through a variable or a third-party name --
    must still produce an edge, labelled UNRESOLVED, never RESOLVED."""
    files = [_File("f1", "a.py")]
    walk = RawWalk(
        relpath="a.py",
        calls=[RawCall(caller_qualname="caller", callee_expr="handler", lineno=2)],
    )
    symbols = [
        _symbol("f1", "a.py", ""),
        _symbol("f1", "a.py", "caller"),
    ]
    result = build_graph(walks=[walk], symbols=symbols, dependencies=[], files=files)
    calls = _edges_by_type(result, "CALLS")
    assert len(calls) == 1
    assert calls[0].confidence == "UNRESOLVED"
    assert calls[0].target_ref == "unresolved::handler"
    unresolved_nodes = [n for n in result.nodes if n.ref == "unresolved::handler"]
    assert len(unresolved_nodes) == 1
    assert unresolved_nodes[0].extra == {"unresolved": True}


def test_third_party_import_becomes_dependency_node():
    files = [_File("f1", "a.py")]
    deps = [DependencyFact(kind="IMPORT", from_file_id="f1", target="requests", classification="THIRD_PARTY")]
    symbols = [_symbol("f1", "a.py", "")]
    result = build_graph(walks=[RawWalk(relpath="a.py")], symbols=symbols, dependencies=deps, files=files)
    imports = _edges_by_type(result, "IMPORTS")
    assert len(imports) == 1
    assert imports[0].target_ref == "dep::requests"
    dep_nodes = [n for n in result.nodes if n.node_type == "DEPENDENCY"]
    assert len(dep_nodes) == 1
    assert dep_nodes[0].ref == "dep::requests"


def test_defines_edges_link_file_to_module_and_class_to_method():
    files = [_File("f1", "a.py")]
    symbols = [
        _symbol("f1", "a.py", ""),
        _symbol("f1", "a.py", "Foo", kind="CLASS"),
        _symbol("f1", "a.py", "Foo.bar", kind="METHOD"),
    ]
    result = build_graph(walks=[RawWalk(relpath="a.py")], symbols=symbols, dependencies=[], files=files)
    defines = {(e.source_ref, e.target_ref) for e in _edges_by_type(result, "DEFINES")}
    assert ("a.py", "a.py::") in defines  # FILE -> MODULE
    assert ("a.py::", "a.py::Foo") in defines  # MODULE -> CLASS
    assert ("a.py::Foo", "a.py::Foo.bar") in defines  # CLASS -> METHOD


def test_tests_edge_from_test_file_to_imported_local_module():
    files = [_File("f1", "test_invoice.py", is_test=True), _File("f2", "invoice.py")]
    walk_test = RawWalk(
        relpath="test_invoice.py",
        imports=[RawImport(module="invoice", asname=None, level=0, imported_names=["calculate_total"], lineno=1)],
    )
    walk_invoice = RawWalk(relpath="invoice.py")
    symbols = [_symbol("f1", "test_invoice.py", ""), _symbol("f2", "invoice.py", "")]
    result = build_graph(walks=[walk_test, walk_invoice], symbols=symbols, dependencies=[], files=files)
    tests_edges = _edges_by_type(result, "TESTS")
    assert len(tests_edges) == 1
    assert tests_edges[0].source_ref == "test_invoice.py"
    assert tests_edges[0].target_ref == "invoice.py"


def test_test_function_node_type_is_test_not_function():
    files = [_File("f1", "test_invoice.py", is_test=True)]
    symbols = [
        _symbol("f1", "test_invoice.py", ""),
        _symbol("f1", "test_invoice.py", "test_something"),
    ]
    result = build_graph(walks=[RawWalk(relpath="test_invoice.py")], symbols=symbols, dependencies=[], files=files)
    test_node = next(n for n in result.nodes if n.ref == "test_invoice.py::test_something")
    assert test_node.node_type == "TEST"
