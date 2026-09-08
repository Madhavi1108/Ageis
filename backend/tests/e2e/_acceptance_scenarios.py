"""Canned MockProvider answers for the three Phase 24 acceptance scenarios
(docs/AEGIS_IMPLEMENTATION_PLAN.md Section 32, docs/ACCEPTANCE_SCENARIOS.md).

This is the ``app/``-side analogue of ``backend/aegis/ai/scenarios.py``: the one
place that "knows" the seeded demo scenarios, keyed by task id (every AI service
passes ``task_key=task_id`` in its prompt variables). MockProvider itself stays
generic -- it has no rule-based fallback for ``implementation`` / ``test_synthesis``
/ ``rca`` / ``repair``, so every scenario must register those explicitly or the
pipeline raises at the implement stage.

Scenario A -- BUG, introduced-then-repaired: the first implementation caps the
discount at the wrong constant (0.6), the generated boundary test fails in the
sandbox, and the repair loop supplies the correct constant (0.5) -> GREEN.

Scenario B -- FEATURE, file creation: the implementation creates ``tax.py`` and
wires it into ``order_service.finalize_order``; the generated test passes first
time.

Scenario C -- UNFIXABLE: the canned implementation and repair proposals are
deliberately ineffective, so the bounded loop stalls on a repeated failure
signature and SAFE_STOPs.
"""

from __future__ import annotations

from app.ai.provider import MockProvider

_CONF_FACT = {"value": 0.9, "basis": "FACT"}
_CONF_INFER = {"value": 0.75, "basis": "INFERENCE"}


# --------------------------------------------------------------------------- #
# Scenario A -- discount-cap bug, introduced then repaired
# --------------------------------------------------------------------------- #

_A_PLAN = {
    "problem_interpretation": (
        "calculate_total() applies discounts above the configured maximum (0.5) in "
        "full; it must clamp the discount to the maximum before applying it"
    ),
    "assumptions": ["discount is a fraction in [0, 1]"],
    "files_to_inspect": ["invoice.py", "config.py", "test_invoice.py"],
    "files_to_modify": ["invoice.py"],
    "symbols_to_modify": ["invoice.py::calculate_total"],
    "dependencies": [],
    "steps": [
        {
            "id": "s1",
            "description": "clamp discount to the configured maximum before applying it",
            "test_intent": "a discount above the maximum behaves like exactly the maximum",
            "evidence_refs": ["invoice.py::calculate_total"],
        }
    ],
    "test_strategy": {"approach": "add a boundary test at discount = 0.9 expecting the 0.5 result"},
    "expected_behavior": "calculate_total(100.0, 0.9) == 50.0",
    "regression_risks": ["calculate_total(100.0, 0.0) must stay 100.0"],
    "rollback_strategy": "revert invoice.py to the snapshot version",
    "source": "AI",
    "confidence": _CONF_FACT,
    "evidence": [{"kind": "file", "ref": "invoice.py", "detail": "unclamped discount"}],
}

# deliberately wrong constant -> the boundary test fails
_A_IMPL = {
    "edit_ops": [
        {
            "path": "invoice.py",
            "op": "replace",
            "anchor": "return price * (1 - discount)",
            "old": "return price * (1 - discount)",
            "new": "return price * (1 - min(discount, 0.6))",
            "plan_step_id": "s1",
            "rationale": "clamp the discount before applying it",
            "evidence": [],
        }
    ]
}

_A_TESTS = {
    "test_cases": [
        {
            "name": "test_discount_at_or_above_max",
            "path": "test_discount_cap_boundary.py",
            "target_symbol": "invoice.py::calculate_total",
            "kind": "BOUNDARY",
            "rationale": "a 90% discount must be charged as a 50% discount",
            "code": (
                "from invoice import calculate_total\n\n\n"
                "def test_discount_at_or_above_max():\n"
                "    assert calculate_total(100.0, 0.9) == 50.0\n"
            ),
            "evidence": [],
        }
    ]
}

_A_RCA = {
    "hypotheses": [
        {
            "statement": "the discount clamp uses 0.6, above the configured maximum of 0.5",
            "label": "HYPOTHESIS",
            "evidence": [{"kind": "file", "ref": "invoice.py", "detail": "min(discount, 0.6)"}],
            "rank": 0,
        }
    ],
    "most_likely_index": 0,
    "open_questions": [],
    "confidence": _CONF_INFER,
    "evidence": [],
}

_A_REPAIR = {
    "target_hypothesis": "the discount clamp uses 0.6, above the configured maximum of 0.5",
    "edit_ops": [
        {
            "path": "invoice.py",
            "op": "replace",
            "anchor": "return price * (1 - min(discount, 0.6))",
            "old": "return price * (1 - min(discount, 0.6))",
            "new": "return price * (1 - min(discount, 0.5))",
            "plan_step_id": "repair",
            "rationale": "use the configured maximum discount (0.5)",
            "evidence": [],
        }
    ],
    "expected_effect": "calculate_total(100.0, 0.9) becomes 50.0",
    "risk_notes": [],
    "confidence": _CONF_FACT,
    "evidence": [],
}


# --------------------------------------------------------------------------- #
# Scenario B -- add order-level tax (new file)
# --------------------------------------------------------------------------- #

_B_PLAN = {
    "problem_interpretation": (
        "orders are finalized without tax; add a tax module and apply it on top of "
        "the discounted total in order_service.finalize_order()"
    ),
    "assumptions": ["tax rate is a fraction; 0.1 is acceptable as the default for this task"],
    "files_to_inspect": ["order_service.py", "invoice.py"],
    "files_to_modify": ["order_service.py"],
    "symbols_to_modify": ["order_service.py::finalize_order"],
    "dependencies": [],
    "steps": [
        {
            "id": "s1",
            "description": "create tax.py with apply_tax(subtotal, rate)",
            "test_intent": "apply_tax adds the rate to the subtotal",
            "evidence_refs": [],
        },
        {
            "id": "s2",
            "description": "call apply_tax on the discounted total in finalize_order",
            "test_intent": "finalize_order returns a tax-inclusive amount",
            "evidence_refs": ["order_service.py::finalize_order"],
        },
    ],
    "test_strategy": {"approach": "unit-test the new tax.py module"},
    "expected_behavior": "apply_tax(100.0, 0.1) == 110.0 (to 2 dp)",
    "regression_risks": ["finalize_order callers now receive a larger amount"],
    "rollback_strategy": "delete tax.py and revert order_service.py",
    "source": "AI",
    "confidence": _CONF_FACT,
    "evidence": [],
}

_B_IMPL = {
    "edit_ops": [
        {
            "path": "tax.py",
            "op": "create",
            "anchor": None,
            "new": (
                '"""Order-level tax."""\n\n\n'
                "def apply_tax(subtotal, rate):\n"
                "    return subtotal * (1 + rate)\n"
            ),
            "plan_step_id": "s1",
            "rationale": "new tax module",
            "evidence": [],
        },
        {
            "path": "order_service.py",
            "op": "replace",
            "anchor": "import invoice\n",
            "old": "import invoice\n",
            "new": "import invoice\nimport tax\n",
            "plan_step_id": "s2",
            "rationale": "make the tax helper available (anchor includes the newline so it "
            "does not also match the `import invoice` mention in the module docstring)",
            "evidence": [],
        },
        {
            "path": "order_service.py",
            "op": "replace",
            "anchor": "    return invoice.calculate_total(price, discount)",
            "old": "    return invoice.calculate_total(price, discount)",
            "new": "    return tax.apply_tax(invoice.calculate_total(price, discount), 0.1)",
            "plan_step_id": "s2",
            "rationale": "apply tax on top of the discounted total",
            "evidence": [],
        },
    ]
}

_B_TESTS = {
    "test_cases": [
        {
            "name": "test_apply_tax_adds_rate",
            "path": "test_tax.py",
            "target_symbol": "tax.py::apply_tax",
            "kind": "ISSUE_SPECIFIC",
            "rationale": "the new helper adds the rate to the subtotal",
            "code": (
                "from tax import apply_tax\n\n\n"
                "def test_apply_tax_adds_rate():\n"
                "    assert round(apply_tax(100.0, 0.1), 2) == 110.0\n"
                "    assert apply_tax(0.0, 0.2) == 0.0\n"
            ),
            "evidence": [],
        }
    ]
}


# --------------------------------------------------------------------------- #
# Scenario C -- unfixable rounding bug
# --------------------------------------------------------------------------- #

_C_PLAN = {
    "problem_interpretation": (
        "round_half_away() delegates to round() (banker's rounding); halves must go "
        "away from zero"
    ),
    "assumptions": ["callers expect half-away-from-zero rounding"],
    "files_to_inspect": ["rounding.py"],
    "files_to_modify": ["rounding.py"],
    "symbols_to_modify": ["rounding.py::round_half_away"],
    "dependencies": [],
    "steps": [
        {
            "id": "s1",
            "description": "replace round() with explicit half-away-from-zero rounding",
            "test_intent": "round_half_away(2.5) == 3",
            "evidence_refs": ["rounding.py::round_half_away"],
        }
    ],
    "test_strategy": {"approach": "boundary test at exactly .5"},
    "expected_behavior": "round_half_away(2.5) == 3",
    "regression_risks": ["round_half_away(2.4) must stay 2"],
    "rollback_strategy": "revert rounding.py to the snapshot version",
    "source": "AI",
    "confidence": _CONF_INFER,
    "evidence": [],
}

# applies cleanly, changes nothing meaningful
_C_IMPL = {
    "edit_ops": [
        {
            "path": "rounding.py",
            "op": "replace",
            "anchor": "    return round(value)",
            "old": "    return round(value)",
            "new": "    result = round(value)\n    return result",
            "plan_step_id": "s1",
            "rationale": "extract the result (no behaviour change -- deliberately ineffective)",
            "evidence": [],
        }
    ]
}

_C_TESTS = {
    "test_cases": [
        {
            "name": "test_half_rounds_away_from_zero",
            "path": "test_round_half_away_boundary.py",
            "target_symbol": "rounding.py::round_half_away",
            "kind": "BOUNDARY",
            "rationale": "2.5 must round to 3",
            "code": (
                "from rounding import round_half_away\n\n\n"
                "def test_half_rounds_away_from_zero():\n"
                "    assert round_half_away(2.5) == 3\n"
            ),
            "evidence": [],
        }
    ]
}

_C_RCA = {
    "hypotheses": [
        {
            "statement": "round() uses banker's rounding; 2.5 -> 2",
            "label": "HYPOTHESIS",
            "evidence": [{"kind": "file", "ref": "rounding.py", "detail": "return round(value)"}],
            "rank": 0,
        }
    ],
    "most_likely_index": 0,
    "open_questions": ["what precision do downstream money calculations require?"],
    "confidence": _CONF_INFER,
    "evidence": [],
}

# also ineffective -> the failure signature repeats -> SAFE_STOP
_C_REPAIR = {
    "target_hypothesis": "round() uses banker's rounding; 2.5 -> 2",
    "edit_ops": [
        {
            "path": "rounding.py",
            "op": "replace",
            "anchor": "    result = round(value)\n    return result",
            "old": "    result = round(value)\n    return result",
            "new": "    result = round(value)  # TODO: half-away-from-zero\n    return result",
            "plan_step_id": "repair",
            "rationale": "annotate the implicated line (no verified fix available)",
            "evidence": [],
        }
    ],
    "expected_effect": "none guaranteed",
    "risk_notes": ["no verified root cause"],
    "confidence": {"value": 0.2, "basis": "UNKNOWN"},
    "evidence": [],
}


# --------------------------------------------------------------------------- #
# Registration
# --------------------------------------------------------------------------- #

_SCENARIOS = {
    "A": {"planning": _A_PLAN, "implementation": _A_IMPL, "test_synthesis": _A_TESTS,
          "rca": _A_RCA, "repair": _A_REPAIR},
    "B": {"planning": _B_PLAN, "implementation": _B_IMPL, "test_synthesis": _B_TESTS},
    "C": {"planning": _C_PLAN, "implementation": _C_IMPL, "test_synthesis": _C_TESTS,
          "rca": _C_RCA, "repair": _C_REPAIR},
}

#: extra task-scope allowlist a scenario needs (scenario B creates a new file)
SCENARIO_ALLOWED_PATHS = {
    "A": None,
    "B": ["order_service.py", "tax.py"],
    "C": None,
}


def register_scenario(provider: MockProvider, scenario: str, task_id: str) -> None:
    for template, raw in _SCENARIOS[scenario].items():
        provider.register(template, task_id, raw)
