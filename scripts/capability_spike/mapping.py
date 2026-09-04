"""Throwaway lexical + symbol-name issue->code localization for the capability spike.

This is a deliberately small precursor to the real hybrid retriever described in
docs/REPOSITORY_ANALYSIS.md #5 (lexical + symbol + graph + history + memory +
semantic, fused with reciprocal-rank fusion). The spike only needs enough
signal to rank a handful of files in a tiny fixture repo, so it implements just
the lexical + symbol-name pieces, deterministically, with no external deps.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

_TOKEN_RE = re.compile(r"[a-zA-Z_][a-zA-Z0-9_]*")

_STOPWORDS = {
    "the", "a", "an", "is", "are", "to", "of", "and", "or", "in", "on", "for",
    "should", "it", "instead", "that", "this", "so", "be", "as", "when",
    "with", "than", "but", "not", "does", "do", "currently", "still",
}


def _tokenize(text: str) -> list[str]:
    return [t.lower() for t in _TOKEN_RE.findall(text) if t.lower() not in _STOPWORDS]


@dataclass
class Candidate:
    path: str
    score: float
    evidence: list[str]


def rank_files(problem_statement: str, repo_dir: Path, *,
                exclude_prefixes: tuple[str, ...] = ("test_",)) -> list[Candidate]:
    """Rank .py files in repo_dir by lexical + symbol-name overlap with the issue text.

    Returns candidates sorted by descending score. Every candidate carries at
    least one evidence string, matching the "no evidence-free candidate" rule
    in docs/REPOSITORY_ANALYSIS.md #5.
    """
    issue_tokens = set(_tokenize(problem_statement))
    candidates: list[Candidate] = []

    for path in sorted(repo_dir.glob("*.py")):
        if any(path.name.startswith(p) for p in exclude_prefixes):
            continue
        text = path.read_text(encoding="utf-8")
        file_tokens = _tokenize(text) + _tokenize(path.stem)

        # Lexical overlap: count of issue tokens that appear in the file.
        overlap = issue_tokens & set(file_tokens)
        lexical_score = float(len(overlap))

        # Symbol-name boost: a `def name(...)` whose name appears in the issue text
        # scores extra -- this stands in for the real system's symbol-name retriever.
        symbol_boost = 0.0
        evidence: list[str] = []
        for m in re.finditer(r"^def\s+([a-zA-Z_][a-zA-Z0-9_]*)", text, flags=re.M):
            name = m.group(1)
            name_tokens = set(_tokenize(name.replace("_", " ")))
            if name_tokens & issue_tokens:
                symbol_boost += 2.0
                evidence.append(f"symbol '{name}' mentioned in issue text")

        if overlap:
            evidence.append(f"lexical overlap: {sorted(overlap)}")

        score = lexical_score + symbol_boost
        if score > 0:
            candidates.append(Candidate(path=path.name, score=score, evidence=evidence))

    candidates.sort(key=lambda c: (-c.score, c.path))
    return candidates
