"""AIProvider abstraction (docs/AI_AGENT_DESIGN.md Section 3, ADR-0005, ADR-0019).

``MockProvider`` is the CI default: deterministic, no network, no spend. It
serves canned responses registered by test/fixture code and, when nothing is
registered, a rule-based fallback -- the same honest low-confidence path the
pipeline takes with no provider at all.

``ClaudeProvider`` is real, gated behind ``RUN_LIVE_AI=1`` + ``ANTHROPIC_API_KEY``.
``OpenAIProvider`` / ``LocalProvider`` are interface-complete seams that refuse
to run until their request bodies are wired (a later phase); they never pretend
to work.
"""

from __future__ import annotations

import json
import os
import time
from typing import Any, Protocol

from pydantic import BaseModel

from app.ai.errors import AIProviderNotConfiguredError
from app.ai.prompt import render
from app.ai.request_log import log_ai_call
from app.ai.schema_guard import AIOutputInvalid, validate_with_repair


class AIProvider(Protocol):
    name: str

    def complete(
        self,
        *,
        template: str,
        variables: dict[str, Any],
        schema: type[BaseModel],
        tier: str = "frontier",
        timeout_s: float = 60.0,
        max_tokens: int = 4000,
        temperature: float = 0.0,
    ) -> BaseModel: ...


# --------------------------------------------------------------------------- #
# Rule-based fallback (no model available)
# --------------------------------------------------------------------------- #


def _fallback_response(template: str, variables: dict[str, Any]) -> dict[str, Any]:
    if template == "planning":
        candidates = variables.get("candidate_files_list") or []
        target = candidates[0] if candidates else None
        return {
            "problem_interpretation": "UNKNOWN -- no engineering-planning model available",
            "assumptions": [],
            "files_to_inspect": list(candidates),
            "files_to_modify": [target] if target else [],
            "symbols_to_modify": list(variables.get("candidate_symbols_list") or []),
            "dependencies": [],
            "steps": [
                {
                    "id": "s1",
                    "description": "best-effort automated fix at the top localisation candidate",
                    "test_intent": "re-run the task's existing failing tests and confirm they pass",
                    "evidence_refs": [],
                }
            ],
            "test_strategy": {"approach": "rely on the repository's existing tests"},
            "expected_behavior": "UNKNOWN",
            "regression_risks": ["no verified root cause; the fix may be ineffective"],
            "rollback_strategy": "revert the workspace to the original snapshot",
            "source": "RULE_BASED_FALLBACK",
            "confidence": {"value": 0.2, "basis": "UNKNOWN"},
            "evidence": [],
        }
    if template == "code_review":
        # no model available -> the deterministic static + rule layers are the
        # floor; the AI reviewer simply contributes nothing.
        return {"findings": []}
    raise ValueError(f"no rule-based fallback for template {template!r}")


# --------------------------------------------------------------------------- #
# Providers
# --------------------------------------------------------------------------- #


class MockProvider:
    name = "mock"

    def __init__(self) -> None:
        self._responses: dict[tuple[str, str], dict[str, Any]] = {}

    def register(self, template: str, task_key: str, raw: dict[str, Any]) -> None:
        self._responses[(template, task_key)] = raw

    def complete(
        self,
        *,
        template: str,
        variables: dict[str, Any],
        schema: type[BaseModel],
        tier: str = "frontier",
        timeout_s: float = 60.0,
        max_tokens: int = 4000,
        temperature: float = 0.0,
    ) -> BaseModel:
        started = time.monotonic()
        task_key = str(variables.get("task_key", ""))
        raw = self._responses.get((template, task_key))
        if raw is None:
            raw = _fallback_response(template, variables)
        try:
            result = validate_with_repair(raw, schema, repair_fn=None)
            outcome = "ok"
        except AIOutputInvalid:
            outcome = "schema_invalid"
            raise
        finally:
            log_ai_call(
                provider=self.name,
                model="mock",
                template=template,
                tier=tier,
                latency_ms=int((time.monotonic() - started) * 1000),
                prompt=f"mock:{template}:{task_key}",
                outcome=outcome,
            )
        return result


_TRANSIENT_MARKERS = ("rate limit", "overloaded", "timeout", "timed out", "503", "529")


class ClaudeProvider:
    name = "claude"

    def __init__(self, *, model: str, max_retries: int, retry_backoff_s: float) -> None:
        if os.environ.get("RUN_LIVE_AI") != "1":
            raise AIProviderNotConfiguredError(
                "ClaudeProvider requires RUN_LIVE_AI=1 (opt-in for live model calls)"
            )
        if not os.environ.get("ANTHROPIC_API_KEY"):
            raise AIProviderNotConfiguredError(
                "ClaudeProvider requires ANTHROPIC_API_KEY"
            )
        try:
            import anthropic  # type: ignore
        except ImportError as exc:  # pragma: no cover - depends on optional extra
            raise AIProviderNotConfiguredError(
                "ClaudeProvider needs the 'anthropic' package: pip install 'aegis-backend[live-ai]'"
            ) from exc
        self._client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
        self._model = model
        self._max_retries = max_retries
        self._retry_backoff_s = retry_backoff_s

    def complete(
        self,
        *,
        template: str,
        variables: dict[str, Any],
        schema: type[BaseModel],
        tier: str = "frontier",
        timeout_s: float = 60.0,
        max_tokens: int = 4000,
        temperature: float = 0.0,
    ) -> BaseModel:
        prompt = render(template, variables)
        started = time.monotonic()
        last_exc: Exception | None = None
        text = ""
        for attempt in range(self._max_retries + 1):
            try:
                resp = self._client.messages.create(
                    model=self._model,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    timeout=timeout_s,
                    messages=[{"role": "user", "content": prompt}],
                )
                text = "".join(getattr(b, "text", "") for b in resp.content)
                last_exc = None
                break
            except Exception as exc:  # noqa: BLE001 - provider SDKs raise many types
                last_exc = exc
                if attempt < self._max_retries and _is_transient(exc):
                    time.sleep(self._retry_backoff_s * (2**attempt))
                    continue
                break

        if last_exc is not None:
            log_ai_call(
                provider=self.name,
                model=self._model,
                template=template,
                tier=tier,
                latency_ms=int((time.monotonic() - started) * 1000),
                prompt=prompt,
                outcome="transport_error",
            )
            raise AIOutputInvalid(f"provider call failed: {last_exc}") from last_exc

        try:
            raw = json.loads(_strip_json_fence(text))
        except json.JSONDecodeError as exc:
            log_ai_call(
                provider=self.name,
                model=self._model,
                template=template,
                tier=tier,
                latency_ms=int((time.monotonic() - started) * 1000),
                prompt=prompt,
                outcome="non_json",
            )
            raise AIOutputInvalid(f"model did not return JSON: {exc}") from exc

        try:
            result = validate_with_repair(raw, schema, repair_fn=None)
            outcome = "ok"
        except AIOutputInvalid:
            outcome = "schema_invalid"
            raise
        finally:
            log_ai_call(
                provider=self.name,
                model=self._model,
                template=template,
                tier=tier,
                latency_ms=int((time.monotonic() - started) * 1000),
                prompt=prompt,
                outcome=outcome,
            )
        return result


class OpenAIProvider:
    name = "openai"

    def __init__(self, **_kwargs: Any) -> None:
        raise AIProviderNotConfiguredError(
            "OpenAIProvider is a declared seam; its request body is not wired yet "
            "(use ai_provider='mock' or 'claude')"
        )

    def complete(self, **_kwargs: Any) -> BaseModel:  # pragma: no cover
        raise AIProviderNotConfiguredError("OpenAIProvider is not implemented")


class LocalProvider:
    name = "local"

    def __init__(self, **_kwargs: Any) -> None:
        raise AIProviderNotConfiguredError(
            "LocalProvider is a declared seam; no local model backend is wired yet "
            "(use ai_provider='mock' or 'claude')"
        )

    def complete(self, **_kwargs: Any) -> BaseModel:  # pragma: no cover
        raise AIProviderNotConfiguredError("LocalProvider is not implemented")


def _is_transient(exc: Exception) -> bool:
    msg = str(exc).lower()
    return any(marker in msg for marker in _TRANSIENT_MARKERS)


def _strip_json_fence(text: str) -> str:
    t = text.strip()
    if t.startswith("```"):
        t = t.split("\n", 1)[1] if "\n" in t else t
        if t.endswith("```"):
            t = t[:-3]
    return t.strip()


def get_provider(settings) -> AIProvider | None:
    """Return the configured provider, or ``None`` for ``ai_provider="none"``
    (the caller then uses the deterministic rule-based fallback)."""
    name = settings.ai_provider
    if name == "none":
        return None
    if name == "mock":
        return MockProvider()
    if name == "claude":
        return ClaudeProvider(
            model=settings.ai_model,
            max_retries=settings.ai_max_retries,
            retry_backoff_s=settings.ai_retry_backoff_s,
        )
    if name == "openai":
        return OpenAIProvider()
    if name == "local":
        return LocalProvider()
    raise AIProviderNotConfiguredError(f"unknown ai_provider {name!r}")
