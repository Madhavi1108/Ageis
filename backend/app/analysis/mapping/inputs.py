"""Plain, DB-free inputs the pure retrievers operate on.

The mapper (mapper.py) does all the DB / workspace IO and hands these value
objects to lexical.py / symbol_match.py so those stay unit-testable without a
session or a real checkout on disk.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FileDoc:
    path: str
    text: str
    is_test: bool


@dataclass(frozen=True)
class SymbolDoc:
    path: str
    symbol_id: str
    qualname: str
    kind: str
    signature: str | None
    docstring: str | None
    is_exported: bool
