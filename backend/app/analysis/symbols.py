"""Turn a file's RawWalk into persistable SymbolFact rows.

See docs/REPOSITORY_ANALYSIS.md Section 2 (symbol_id scheme, is_exported rule).
"""

from __future__ import annotations

from dataclasses import dataclass

from app.analysis.python_ast import RawDef, RawWalk

_ROUTE_DECORATOR_SUFFIXES = (
    "route",
    "get",
    "post",
    "put",
    "patch",
    "delete",
    "websocket",
)


@dataclass(frozen=True)
class SymbolFact:
    file_id: str
    symbol_id: str
    kind: str
    qualname: str
    signature: str | None
    lineno: int
    end_lineno: int
    decorators: list[str]
    docstring: str | None
    is_exported: bool


def _is_route_decorator(decorator: str) -> bool:
    # e.g. "app.get" from "app.get('/x')" (ast.unparse of the Call includes the args,
    # so match the callable-name prefix rather than the whole string).
    name = decorator.split("(", 1)[0]
    return any(
        name == suffix or name.endswith(f".{suffix}")
        for suffix in _ROUTE_DECORATOR_SUFFIXES
    )


def _is_exported(d: RawDef, dunder_all: list[str] | None) -> bool:
    name = d.qualname.rsplit(".", 1)[-1] if d.qualname else ""
    if dunder_all is not None:
        return name in dunder_all
    if d.is_top_level and d.kind in ("FUNCTION", "CLASS") and not name.startswith("_"):
        return True
    if any(_is_route_decorator(dec) for dec in d.decorators):
        return True
    return False


def symbols_from_walk(walk: RawWalk, file_id: str) -> list[SymbolFact]:
    facts: list[SymbolFact] = []
    for d in walk.defs:
        symbol_id = f"{walk.relpath}::{d.qualname}"
        facts.append(
            SymbolFact(
                file_id=file_id,
                symbol_id=symbol_id,
                kind=d.kind,
                qualname=d.qualname,
                signature=d.signature,
                lineno=d.lineno,
                end_lineno=d.end_lineno,
                decorators=d.decorators,
                docstring=d.docstring,
                is_exported=_is_exported(d, walk.dunder_all),
            )
        )
    return facts
