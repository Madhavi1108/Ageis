"""A tiny, AIProvider-shaped shim for the capability spike.

Mirrors the shape of the real docs/AI_AGENT_DESIGN.md #3 AIProvider (a
`complete()`-style call that returns a structured edit-op), reduced to exactly
what the spike needs: given a task, produce {file, find, replace, prepend?}.

MockProvider is deterministic and requires no network or API key -- it is the
CI-default path and the one this repository's verification relies on. A real
provider is wired for the live run (docs/CAPABILITY_SPIKE.md #5.2) but is not
exercised by this repository's tests: it needs a real API key and is
explicitly out of scope for Phase 0 (see docs/CAPABILITY_SPIKE.md).
"""
from __future__ import annotations

import json
import os
from typing import Any, Protocol


class EditOp(Protocol):
    file: str
    find: str
    replace: str


class SpikeProvider(Protocol):
    name: str

    def get_edit(self, task: dict[str, Any]) -> dict[str, str]: ...


class MockProvider:
    """Deterministic: returns the task's own `mock_fix` field.

    This is intentionally not "the model figured it out" -- it is a wiring
    proof. See docs/CAPABILITY_SPIKE.md #5.1: mock numbers prove the harness,
    not AEGIS's real localization/repair capability.
    """

    name = "mock"

    def get_edit(self, task: dict[str, Any]) -> dict[str, str]:
        fix = task.get("mock_fix")
        if not fix:
            raise ValueError(
                f"task '{task.get('id')}' has no mock_fix; MockProvider needs one"
            )
        return fix


class _LiveProviderBase:
    """Shared plumbing for real providers: build a schema-constrained prompt,
    call the SDK, parse a JSON edit-op. Requires the provider SDK and an API
    key; raises a clear error otherwise rather than silently falling back to
    the mock (never fabricate a live result -- Specification Rule 43/55)."""

    name = "live-base"
    api_key_env = ""

    def _require_key(self) -> str:
        key = os.environ.get(self.api_key_env, "")
        if not key:
            raise RuntimeError(
                f"{self.name}: set {self.api_key_env} to run the live capability "
                f"spike (see docs/CAPABILITY_SPIKE.md #5.2)."
            )
        return key

    def _prompt(self, task: dict[str, Any], file_contents: dict[str, str]) -> str:
        files_block = "\n\n".join(
            f"--- {path} ---\n{content}" for path, content in file_contents.items()
        )
        return (
            "You are proposing a minimal, correct code fix.\n"
            f"Issue:\n{task['problem_statement']}\n\n"
            f"Candidate files:\n{files_block}\n\n"
            "Return ONLY a JSON object: "
            '{"file": "<path>", "find": "<exact snippet to replace>", '
            '"replace": "<replacement>", "prepend": "<optional text to add at top>"}'
        )

    def get_edit(self, task: dict[str, Any], file_contents: dict[str, str]) -> dict[str, str]:
        raise NotImplementedError


class ClaudeProvider(_LiveProviderBase):
    name = "claude"
    api_key_env = "ANTHROPIC_API_KEY"

    def get_edit(self, task: dict[str, Any], file_contents: dict[str, str]) -> dict[str, str]:
        self._require_key()
        try:
            import anthropic  # type: ignore
        except ImportError as exc:
            raise RuntimeError(
                "ClaudeProvider requires the 'anthropic' package "
                "(pip install anthropic) for the live spike run."
            ) from exc
        client = anthropic.Anthropic()
        resp = client.messages.create(
            model=os.environ.get("AEGIS_SPIKE_MODEL", "claude-sonnet-5"),
            max_tokens=1024,
            temperature=0.0,
            messages=[{"role": "user", "content": self._prompt(task, file_contents)}],
        )
        text = "".join(block.text for block in resp.content if hasattr(block, "text"))
        return json.loads(text)


class OpenAIProvider(_LiveProviderBase):
    name = "openai"
    api_key_env = "OPENAI_API_KEY"

    def get_edit(self, task: dict[str, Any], file_contents: dict[str, str]) -> dict[str, str]:
        self._require_key()
        try:
            import openai  # type: ignore
        except ImportError as exc:
            raise RuntimeError(
                "OpenAIProvider requires the 'openai' package "
                "(pip install openai) for the live spike run."
            ) from exc
        client = openai.OpenAI()
        resp = client.chat.completions.create(
            model=os.environ.get("AEGIS_SPIKE_MODEL", "gpt-4o"),
            temperature=0.0,
            messages=[{"role": "user", "content": self._prompt(task, file_contents)}],
        )
        text = resp.choices[0].message.content
        return json.loads(text)


def get_provider(name: str):
    return {
        "mock": MockProvider,
        "claude": ClaudeProvider,
        "openai": OpenAIProvider,
    }[name]()
