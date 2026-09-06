"""Structured prompt assembly (docs/AI_AGENT_DESIGN.md Section 8, ADR-0005).

Rules enforced here:

1. Templates live in ``app/ai/prompts/<name>.md`` -- no inline prompt strings in
   agent code.
2. The instruction body is static. Untrusted content (issue text, repo paths,
   code) is substituted **only** into ``{{PLACEHOLDER}}`` markers, and every
   such marker in a template file sits inside a delimited
   ``<data name="...">...</data>`` block. ``render`` refuses to run if a
   template places a marker outside a data block, so untrusted values can never
   reach the instruction body.
3. A missing variable is an error (no silent blank), an unused variable is
   ignored.
"""

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

_PROMPTS_DIR = Path(__file__).parent / "prompts"
_MARKER_RE = re.compile(r"\{\{([A-Z0-9_]+)\}\}")
_DATA_BLOCK_RE = re.compile(r"<data\b[^>]*>.*?</data>", re.DOTALL)


class PromptTemplateError(ValueError):
    """A template is malformed or a required variable was not supplied."""


@lru_cache(maxsize=32)
def _load(template_name: str) -> str:
    path = _PROMPTS_DIR / f"{template_name}.md"
    if not path.is_file():
        raise PromptTemplateError(f"no prompt template {template_name!r} at {path}")
    text = path.read_text(encoding="utf-8")
    _assert_markers_inside_data_blocks(template_name, text)
    return text


def _assert_markers_inside_data_blocks(template_name: str, text: str) -> None:
    safe_spans = [m.span() for m in _DATA_BLOCK_RE.finditer(text)]
    for marker in _MARKER_RE.finditer(text):
        start = marker.start()
        if not any(a <= start < b for a, b in safe_spans):
            raise PromptTemplateError(
                f"template {template_name!r}: placeholder {marker.group(0)} is "
                "outside a <data> block -- untrusted content must never touch the "
                "instruction body"
            )


def render(template_name: str, variables: dict[str, object]) -> str:
    text = _load(template_name)
    needed = {m.group(1) for m in _MARKER_RE.finditer(text)}
    missing = needed - {k.upper() for k in variables}
    if missing:
        raise PromptTemplateError(
            f"template {template_name!r} needs variables {sorted(missing)}"
        )
    upper = {k.upper(): v for k, v in variables.items()}
    return _MARKER_RE.sub(lambda m: str(upper[m.group(1)]), text)
