"""Testing agent (docs/AI_AGENT_DESIGN.md Section 2,
docs/AEGIS_IMPLEMENTATION_PLAN.md Section 19).

Pure functions over already-loaded inputs -- the service
(app/services/testing.py) does the DB / provider / workspace wiring.

* ``build_case_matrix``  -- for each target symbol, the case kinds the
                            prompt asks the model to cover.
* ``propose_test_cases`` -- ask the configured provider to fill the
                            TestCasesAI schema.
* ``write_into_workspace``-- materialize each case's file into an RW
                            workspace (create only -- Phase 11 never edits an
                            existing file's content).
"""

from __future__ import annotations

from typing import Any

from app.ai.provider import AIProvider
from app.ai.routing import tier_for
from app.implementation.workspace_rw import RWWorkspace
from app.schemas.testing import TestCaseAI, TestCaseKind, TestCasesAI

_TEST_SYNTHESIS_TEMPLATE = "test_synthesis"
_CASE_KINDS: tuple[TestCaseKind, ...] = (
    "EDGE",
    "NEGATIVE",
    "BOUNDARY",
    "REGRESSION",
    "ISSUE_SPECIFIC",
)


def build_case_matrix(target_symbols: list[str]) -> list[dict[str, str]]:
    """One row per (symbol, kind) -- the minimum case-kind coverage the
    prompt asks for per changed public function (policy: at least one
    boundary case and one negative case per symbol)."""
    return [
        {"target_symbol": symbol, "kind": kind}
        for symbol in target_symbols
        for kind in _CASE_KINDS
    ]


def propose_test_cases(
    *,
    task_key: str,
    problem_interpretation: str,
    target_symbols: list[str],
    test_framework: str | None,
    existing_test_paths: list[str],
    provider: AIProvider,
    timeout_s: float,
    max_tokens: int,
) -> list[TestCaseAI]:
    matrix = build_case_matrix(target_symbols)
    variables: dict[str, Any] = {
        "task_key": task_key,
        "problem_interpretation": problem_interpretation,
        "target_symbols": "\n".join(target_symbols) or "(none)",
        "test_framework": test_framework or "pytest (assumed -- UNKNOWN in analysis)",
        "existing_test_paths": "\n".join(existing_test_paths) or "(none)",
        "case_matrix": "\n".join(
            f"- {row['target_symbol']}: {row['kind']}" for row in matrix
        )
        or "(none)",
        # list form for the MockProvider rule-based fallback (not templated)
        "target_symbols_list": target_symbols,
    }
    result = provider.complete(
        template=_TEST_SYNTHESIS_TEMPLATE,
        variables=variables,
        schema=TestCasesAI,
        tier=tier_for("test_synthesis"),
        timeout_s=timeout_s,
        max_tokens=max_tokens,
    )
    assert isinstance(result, TestCasesAI)
    return result.test_cases


def write_into_workspace(ws: RWWorkspace, cases: list[TestCaseAI]) -> None:
    """Create each case's file in the RW workspace. Never overwrites an
    existing path -- callers must have already deduplicated
    (app.testing.catalog.deduplicate) against files already in the
    workspace."""
    for case in cases:
        target = ws.path_for(case.path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(case.code, encoding="utf-8")
