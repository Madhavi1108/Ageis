"""Typed loader for the Phase 24 gold-artifact files (``tests/e2e/gold/*.json``).

Gold lives *outside* the ingested acceptance repo on purpose -- it is test
scaffolding, not part of the project under test -- so it never perturbs the
per-stage ``*_acceptance_fixture.py`` integration tests.
"""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel

GOLD_DIR = Path(__file__).resolve().parent / "gold"


class GoldScenario(BaseModel):
    scenario: str
    title: str
    task_file: str
    kind: str  # BUG | FEATURE
    introduced_failure: bool
    expected_localization_files: list[str]
    expected_files_modified: list[str]
    expected_files_created: list[str]
    expected_symbols: list[str]
    expected_tests: list[str]
    expected_first_execution_failing: bool
    expected_repair_outcome: str | None  # REPAIRED | SAFE_STOP | None
    expected_verification_verdict: str | None  # VERIFIED | NOT_VERIFIED | None
    expected_terminal_state: str  # COMPLETED | NOT_COMPLETED
    prior_related_fix_message_contains: str | None


def load_gold(name: str) -> GoldScenario:
    """``name`` is a bare scenario key like ``"scenario_a"``."""
    return GoldScenario.model_validate_json((GOLD_DIR / f"{name}.json").read_text("utf-8"))


def all_gold() -> dict[str, GoldScenario]:
    return {p.stem: load_gold(p.stem) for p in sorted(GOLD_DIR.glob("*.json"))}
