"""Live-provider smoke (opt-in). Runs only with RUN_LIVE_AI=1 + ANTHROPIC_API_KEY
(docs/AEGIS_IMPLEMENTATION_PLAN.md Section 5.2)."""

from __future__ import annotations

import os

import pytest

from app.ai.provider import ClaudeProvider
from app.schemas.plan import EngineeringPlanAI

pytestmark = [
    pytest.mark.live_ai,
    pytest.mark.skipif(
        os.environ.get("RUN_LIVE_AI") != "1" or not os.environ.get("ANTHROPIC_API_KEY"),
        reason="live AI opt-in (set RUN_LIVE_AI=1 and ANTHROPIC_API_KEY)",
    ),
]


def test_claude_returns_a_schema_valid_plan():
    provider = ClaudeProvider(
        model="claude-sonnet-5", max_retries=2, retry_backoff_s=0.5
    )
    out = provider.complete(
        template="planning",
        variables={
            "task_key": "live-smoke",
            "task_text": "Cap the discount at 50% in calculate_total in the invoice module.",
            "candidate_files": "invoice.py",
            "candidate_symbols": "invoice.py::calculate_total",
            "impact_summary": "changed_files=['invoice.py']; callers=['checkout.py::process_checkout']",
            "memory_hits": "(none)",
        },
        schema=EngineeringPlanAI,
    )
    assert isinstance(out, EngineeringPlanAI)
    assert out.files_to_modify
    assert out.steps and all(s.test_intent for s in out.steps)
