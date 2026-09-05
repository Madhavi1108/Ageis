"""Symbol-name retriever: match issue tokens against symbol qualnames.

An issue that says "fix ``calculate_total()``" or "the discount cap in the
invoice module" should surface ``invoice.py::calculate_total`` directly, with
the matched qualname as evidence. Matching is on the identifier's word parts
(``calculate_total`` -> {calculate, total}); a full-token match of the
qualname's last segment scores highest, a partial word-overlap scores lower.
Exported symbols get a small boost (a public name in the issue is a stronger
signal than an internal helper).
"""

from __future__ import annotations

from aegis.schemas.common import Evidence

from app.analysis.mapping.candidate import RetrievedCandidate, RetrieverResult
from app.analysis.mapping.inputs import SymbolDoc
from app.analysis.mapping.text import split_identifier, tokenize

_NAME = "symbol"


def retrieve(issue_text: str, symbols: list[SymbolDoc]) -> RetrieverResult:
    issue_tokens = set(tokenize(issue_text))
    if not issue_tokens:
        return RetrieverResult(name=_NAME, candidates=[])

    # Aggregate to one candidate per file, keeping its best-matching symbols.
    per_path_score: dict[str, float] = {}
    per_path_syms: dict[str, list[str]] = {}
    per_path_ev: dict[str, Evidence] = {}

    for s in symbols:
        last = s.qualname.split(".")[-1].split("::")[-1]
        parts = split_identifier(s.qualname)
        if not parts:
            continue
        overlap = parts & issue_tokens
        if not overlap:
            continue

        exact_last = last.lower() in issue_tokens
        score = (3.0 if exact_last else 0.0) + len(overlap)
        if s.is_exported:
            score += 0.5

        if score > per_path_score.get(s.path, 0.0):
            per_path_score[s.path] = score
            per_path_ev[s.path] = Evidence(
                kind="symbol",
                ref=s.symbol_id,
                detail=(
                    f"issue names symbol {s.qualname!r}"
                    if exact_last
                    else f"issue words {sorted(overlap)} overlap symbol {s.qualname!r}"
                ),
            )
        per_path_syms.setdefault(s.path, [])
        if s.qualname not in per_path_syms[s.path]:
            per_path_syms[s.path].append(s.qualname)

    candidates = [
        RetrievedCandidate(
            path=path,
            score=per_path_score[path],
            evidence=[per_path_ev[path]],
            symbols=per_path_syms.get(path, []),
        )
        for path in per_path_score
    ]
    candidates.sort(key=lambda c: (-c.score, c.path))
    return RetrieverResult(name=_NAME, candidates=candidates)
