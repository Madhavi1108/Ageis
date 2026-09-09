"""Deterministic AI-context windowing (Phase 27, docs/EXECUTION_MODEL.md §6-§7,
docs/AEGIS_IMPLEMENTATION_PLAN.md §35).

A prompt's context is assembled from labelled sections with an explicit priority.
When the estimated token count exceeds the budget, the lowest-priority sections
are dropped (and, as a last resort, the single largest remaining low-priority
section is hard-truncated) -- in a fixed order, so the same inputs always yield
the same prompt. Every drop/truncation is reported so the caller can record it
as provenance (never a silent, unprovenanced cut -- the §37 rule).

Token estimate is ``ceil(len(text) / 4)`` -- good enough to bound context size
without a tokenizer dependency; it is intentionally conservative (over-counts).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

_CHARS_PER_TOKEN = 4
#: placeholder a dropped section's variable is set to, so templates still render
DROPPED_PLACEHOLDER = "(omitted: exceeded the AI context budget)"


def estimate_tokens(text: str) -> int:
    return math.ceil(len(text) / _CHARS_PER_TOKEN) if text else 0


@dataclass(frozen=True)
class ContextSection:
    name: str
    text: str
    #: lower = more important. Priority 0 is never dropped or truncated.
    priority: int = 5


@dataclass
class FitResult:
    kept: dict[str, str] = field(default_factory=dict)
    dropped: list[str] = field(default_factory=list)
    truncated: list[str] = field(default_factory=list)
    estimated_tokens: int = 0

    @property
    def changed(self) -> bool:
        return bool(self.dropped or self.truncated)

    def note(self) -> str:
        """One-line provenance string, or '' when nothing was cut."""
        bits: list[str] = []
        if self.dropped:
            bits.append(f"context sections omitted (over budget): {', '.join(self.dropped)}")
        if self.truncated:
            bits.append(f"context sections truncated: {', '.join(self.truncated)}")
        return "; ".join(bits)


def fit_context(sections: list[ContextSection], budget_tokens: int) -> FitResult:
    """Return the sections that fit ``budget_tokens``.

    ``kept`` always has an entry for *every* input section name (a dropped
    section maps to ``DROPPED_PLACEHOLDER``) so a template render never fails on
    a missing variable.
    """
    # stable, deterministic order: least important (highest priority number)
    # first among drop candidates; ties broken by name.
    ordered = sorted(sections, key=lambda s: (s.priority, s.name))
    kept_text = {s.name: s.text for s in ordered}
    result = FitResult(kept=dict(kept_text))

    total = sum(estimate_tokens(s.text) for s in ordered)
    if total <= budget_tokens:
        result.estimated_tokens = total
        return result

    # drop whole sections, most-droppable first (priority > 0 only)
    for s in sorted(sections, key=lambda s: (-s.priority, s.name)):
        if total <= budget_tokens:
            break
        if s.priority == 0:
            continue
        total -= estimate_tokens(kept_text[s.name])
        kept_text[s.name] = DROPPED_PLACEHOLDER
        total += estimate_tokens(DROPPED_PLACEHOLDER)
        result.dropped.append(s.name)

    # last resort: hard-truncate the largest still-present droppable section
    if total > budget_tokens:
        candidates = [
            s
            for s in sections
            if s.priority > 0 and s.name not in result.dropped
        ]
        candidates.sort(key=lambda s: (-estimate_tokens(kept_text[s.name]), s.name))
        for s in candidates:
            if total <= budget_tokens:
                break
            over_tokens = total - budget_tokens
            cut_chars = min(len(kept_text[s.name]), (over_tokens + 1) * _CHARS_PER_TOKEN)
            new_text = (
                kept_text[s.name][: len(kept_text[s.name]) - cut_chars].rstrip()
                + f"\n…[{cut_chars} chars omitted: AI context budget]"
            )
            total -= estimate_tokens(kept_text[s.name])
            total += estimate_tokens(new_text)
            kept_text[s.name] = new_text
            result.truncated.append(s.name)

    result.kept = kept_text
    result.estimated_tokens = total
    return result
