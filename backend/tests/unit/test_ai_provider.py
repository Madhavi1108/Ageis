"""MockProvider canned + fallback paths; get_provider selection; seams."""

from __future__ import annotations

import pytest

from app.ai.errors import AIProviderNotConfiguredError
from app.ai.provider import MockProvider, get_provider
from app.ai.schema_guard import AIOutputInvalid
from app.schemas.plan import EngineeringPlanAI


class _Settings:
    ai_provider = "mock"
    ai_model = "claude-sonnet-5"
    ai_max_retries = 2
    ai_retry_backoff_s = 0.0


def test_mock_returns_registered_response():
    p = MockProvider()
    raw = {
        "problem_interpretation": "x",
        "assumptions": [],
        "files_to_inspect": [],
        "files_to_modify": ["a.py"],
        "symbols_to_modify": [],
        "dependencies": [],
        "steps": [
            {"id": "s1", "description": "d", "test_intent": "t", "evidence_refs": []}
        ],
        "test_strategy": {},
        "expected_behavior": "e",
        "regression_risks": [],
        "rollback_strategy": "revert",
        "source": "AI",
        "confidence": {"value": 0.7, "basis": "INFERENCE"},
        "evidence": [],
    }
    p.register("planning", "k1", raw)
    out = p.complete(
        template="planning",
        variables={"task_key": "k1"},
        schema=EngineeringPlanAI,
    )
    assert isinstance(out, EngineeringPlanAI)
    assert out.files_to_modify == ["a.py"]


def test_mock_falls_back_when_nothing_registered():
    p = MockProvider()
    out = p.complete(
        template="planning",
        variables={"task_key": "unknown", "candidate_files_list": ["invoice.py"]},
        schema=EngineeringPlanAI,
    )
    assert out.source == "RULE_BASED_FALLBACK"
    assert out.files_to_modify == ["invoice.py"]
    assert out.confidence.value <= 0.3


def test_mock_invalid_registered_response_raises():
    p = MockProvider()
    p.register("planning", "bad", {"not": "a plan"})
    with pytest.raises(AIOutputInvalid):
        p.complete(
            template="planning",
            variables={"task_key": "bad"},
            schema=EngineeringPlanAI,
        )


def test_get_provider_selection():
    s = _Settings()
    assert isinstance(get_provider(s), MockProvider)

    s.ai_provider = "none"
    assert get_provider(s) is None

    s.ai_provider = "openai"
    with pytest.raises(AIProviderNotConfiguredError):
        get_provider(s)

    s.ai_provider = "local"
    with pytest.raises(AIProviderNotConfiguredError):
        get_provider(s)


def test_claude_requires_opt_in(monkeypatch):
    monkeypatch.delenv("RUN_LIVE_AI", raising=False)
    s = _Settings()
    s.ai_provider = "claude"
    with pytest.raises(AIProviderNotConfiguredError):
        get_provider(s)
