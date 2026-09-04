"""Reduced issue->code mapping: lexical + symbol-name overlap (no embeddings,
no code graph, no Git history, no memory -- those are Phase 5/7/19/20's job).
Full design: docs/REPOSITORY_ANALYSIS.md Section 5.

Every candidate carries at least one concrete Evidence item -- the "no
evidence-free candidate" rule (docs/REPOSITORY_ANALYSIS.md Section 5) is
enforced structurally here, not just documented.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from aegis.analysis.python_ast import RepositoryAnalysis
from aegis.repository.ingest import Snapshot
from aegis.schemas.common import Evidence

_TOKEN_RE = re.compile(r"[a-zA-Z_][a-zA-Z0-9_]*")
_STOPWORDS = {
    "the",
    "a",
    "an",
    "is",
    "are",
    "to",
    "of",
    "and",
    "or",
    "in",
    "on",
    "for",
    "should",
    "it",
    "instead",
    "that",
    "this",
    "so",
    "be",
    "as",
    "when",
    "with",
    "than",
    "but",
    "not",
    "does",
    "do",
    "currently",
    "still",
    "this",
}


def _tokenize(text: str) -> set[str]:
    return {t.lower() for t in _TOKEN_RE.findall(text) if t.lower() not in _STOPWORDS}


@dataclass(frozen=True)
class Candidate:
    path: str
    score: float
    evidence: list[Evidence] = field(default_factory=list)


def rank_files(
    issue_text: str, snapshot: Snapshot, analysis: RepositoryAnalysis
) -> list[Candidate]:
    """Rank non-test Python files by lexical + symbol-name overlap with the
    issue text. Returns candidates sorted by descending score; a file with no
    overlap at all is omitted (never returned as an evidence-free guess).
    """
    issue_tokens = _tokenize(issue_text)
    candidates: list[Candidate] = []

    for f in snapshot.python_files():
        if f.is_test:
            continue
        source = f.abs_path.read_text(encoding="utf-8")
        file_tokens = _tokenize(source) | _tokenize(f.path)
        overlap = issue_tokens & file_tokens

        evidence: list[Evidence] = []
        score = float(len(overlap))
        if overlap:
            evidence.append(
                Evidence(
                    kind="file",
                    ref=f.path,
                    detail=f"lexical overlap with issue text: {sorted(overlap)}",
                )
            )

        for sym in analysis.symbols_in(f.path):
            name_tokens = _tokenize(sym.qualname.replace("_", " "))
            if name_tokens & issue_tokens:
                score += 2.0
                evidence.append(
                    Evidence(
                        kind="symbol",
                        ref=sym.symbol_id,
                        detail=f"symbol name mentioned in issue text: {sym.qualname}",
                    )
                )

        if score > 0:
            candidates.append(Candidate(path=f.path, score=score, evidence=evidence))

    candidates.sort(key=lambda c: (-c.score, c.path))
    return candidates
