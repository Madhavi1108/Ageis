"""Shared tokenizer + stopword set for the mapping retrievers.

Lifted from the Phase 1 skeleton (backend/aegis/analysis/mapping.py) rather than
imported: app/ only depends on aegis.schemas.*, and the skeleton module is a
"reduced implementation behind a stable contract" that later phases replace, not
extend (docs/AEGIS_IMPLEMENTATION_PLAN.md Section 9). Keeping a copy here keeps
the app-side mapper self-contained.
"""

from __future__ import annotations

import re

_TOKEN_RE = re.compile(r"[a-zA-Z_][a-zA-Z0-9_]*")

# Common English filler plus a few issue-writing verbs that carry no localizing
# signal ("should", "currently", ...). Kept deliberately small: an over-large
# stoplist silently drops real identifiers.
STOPWORDS = frozenset(
    {
        "the",
        "a",
        "an",
        "is",
        "are",
        "was",
        "were",
        "be",
        "been",
        "being",
        "to",
        "of",
        "and",
        "or",
        "in",
        "on",
        "for",
        "at",
        "by",
        "with",
        "from",
        "as",
        "it",
        "its",
        "this",
        "that",
        "these",
        "those",
        "when",
        "then",
        "than",
        "but",
        "not",
        "no",
        "so",
        "if",
        "we",
        "i",
        "you",
        "should",
        "would",
        "could",
        "will",
        "can",
        "does",
        "do",
        "did",
        "done",
        "instead",
        "currently",
        "still",
        "also",
        "there",
        "here",
        "into",
        "out",
        "up",
        "down",
        "about",
        "after",
        "before",
        "above",
        "below",
    }
)


def tokenize(text: str) -> list[str]:
    """Lowercased identifier-like tokens, stopwords removed, order preserved
    (order matters for FTS phrase construction and for stable de-duping)."""
    seen: set[str] = set()
    out: list[str] = []
    for raw in _TOKEN_RE.findall(text):
        t = raw.lower()
        if t in STOPWORDS or len(t) < 2:
            continue
        if t not in seen:
            seen.add(t)
            out.append(t)
    return out


def split_identifier(name: str) -> set[str]:
    """Break a qualname / dotted path into its lowercased word parts:
    ``invoice.calculate_total`` -> {invoice, calculate, total}."""
    parts: set[str] = set()
    for chunk in re.split(r"[.\-/:]+", name):
        for piece in chunk.split("_"):
            # split camelCase too
            for sub in re.findall(r"[A-Z]+(?![a-z])|[A-Z][a-z]*|[a-z]+|[0-9]+", piece):
                s = sub.lower()
                if s and s not in STOPWORDS and len(s) >= 2:
                    parts.add(s)
    return parts
