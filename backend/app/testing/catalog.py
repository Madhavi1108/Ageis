"""Static validity check + de-duplication for generated test cases
(docs/AEGIS_IMPLEMENTATION_PLAN.md Section 19).

Only a syntax check (``ast.parse``) runs here -- actually importing/collecting
a test module executes it, which Absolute Rule 9 ("never execute untrusted
code on the host") forbids outside the Phase 12 Docker sandbox. "Full
collection happens in the Phase 12 sandbox" (the plan's own wording) is this
constraint, not an oversight.
"""

from __future__ import annotations

import ast

from app.schemas.testing import TestCaseAI


def check_syntax(code: str) -> str | None:
    """Return an error message if ``code`` does not parse as Python, else
    None."""
    try:
        ast.parse(code)
    except SyntaxError as exc:
        return f"{exc.__class__.__name__}: {exc.msg} (line {exc.lineno})"
    return None


def existing_test_names(test_file_sources: dict[str, str]) -> set[str]:
    """Every top-level ``test_*`` function name already defined across the
    snapshot's existing test files (``{path: source}``). A source that fails
    to parse contributes nothing -- it's not this pass's job to flag pre-
    existing syntax errors."""
    names: set[str] = set()
    for source in test_file_sources.values():
        try:
            tree = ast.parse(source)
        except SyntaxError:
            continue
        for node in tree.body:
            if isinstance(node, ast.FunctionDef) and node.name.startswith("test"):
                names.add(node.name)
    return names


def deduplicate(
    cases: list[TestCaseAI], *, existing_names: set[str], existing_paths: set[str]
) -> tuple[list[TestCaseAI], list[TestCaseAI]]:
    """Split ``cases`` into (kept, dropped). A case is dropped if its name
    collides with an existing test function, or its path collides with an
    existing file (Phase 11 only ever creates new files -- see TestCaseAI's
    docstring)."""
    kept: list[TestCaseAI] = []
    dropped: list[TestCaseAI] = []
    seen_names: set[str] = set()
    seen_paths: set[str] = set()
    for case in cases:
        if (
            case.name in existing_names
            or case.path in existing_paths
            or case.name in seen_names
            or case.path in seen_paths
        ):
            dropped.append(case)
            continue
        kept.append(case)
        seen_names.add(case.name)
        seen_paths.add(case.path)
    return kept, dropped
