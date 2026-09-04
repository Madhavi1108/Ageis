"""Canned MockProvider answers for the walking skeleton's one seeded
acceptance task (test-repositories/aegis-acceptance, Specification Section
39's worked example). MockProvider itself stays generic (docs/AI_AGENT_DESIGN.md
Section 3) -- this module is the one place that "knows" about this specific
demo scenario, used by both the CLI and the test suite.

Deliberately absent: any registration for the "unfixable" fixture
(test-repositories/fixtures/unfixable) -- it is meant to exercise
MockProvider's generic rule-based fallback (see provider.py:_fallback_response),
not a scripted answer.
"""
from __future__ import annotations

from aegis.ai.provider import MockProvider

ACCEPTANCE_TASK_KEY = "aegis-acceptance"


def register_walking_skeleton_scenarios(provider: MockProvider) -> None:
    provider.register(
        "planning",
        ACCEPTANCE_TASK_KEY,
        {
            "problem_interpretation": (
                "calculate_total() does not cap the discount rate, so a discount above 50% is "
                "applied in full instead of being capped at 50%"
            ),
            "assumptions": ["discount is expressed as a fraction in [0, 1]"],
            "files_to_inspect": ["invoice.py", "test_invoice.py"],
            "files_to_modify": ["invoice.py"],
            "symbols_to_modify": ["invoice.py::calculate_total"],
            "dependencies": [],
            "steps": [
                {
                    "id": "s1",
                    "description": "cap the discount at 0.5 before applying it to the price",
                    "test_intent": "a discount above 50% behaves the same as exactly 50%",
                    "evidence_refs": ["invoice.py::calculate_total"],
                }
            ],
            "test_strategy": {
                "approach": "existing test_invoice.py already covers the boundary condition"
            },
            "expected_behavior": "calculate_total(100.0, 0.9) == 50.0",
            "regression_risks": ["calculate_total(100.0, 0.0) must remain 100.0"],
            "rollback_strategy": "revert invoice.py to its original content",
            "source": "AI",
            "confidence": {"value": 0.9, "basis": "FACT"},
            "evidence": [
                {
                    "kind": "file",
                    "ref": "invoice.py",
                    "detail": "contains calculate_total() with the described bug",
                }
            ],
        },
    )
    provider.register(
        "implementation",
        ACCEPTANCE_TASK_KEY,
        {
            "edit_ops": [
                {
                    "path": "invoice.py",
                    "op": "replace",
                    "anchor": "return price * (1 - discount)",
                    "old": "return price * (1 - discount)",
                    "new": "return price * (1 - min(discount, 0.5))",
                    "plan_step_id": "s1",
                    "rationale": "cap the discount at 50% before applying it, per the plan",
                    "evidence": [
                        {
                            "kind": "line_range",
                            "ref": "invoice.py:11-12",
                            "detail": "the unguarded discount application",
                        }
                    ],
                }
            ]
        },
    )
