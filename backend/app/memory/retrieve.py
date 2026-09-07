"""Rank engineering-memory rows for a query into ``MemoryHit``s
(docs/AEGIS_IMPLEMENTATION_PLAN.md Section 28, ADR-0016).

``similarity`` blends: normalized lexical score (``index.MemoryIndex``), symbol
overlap between the query's identifiers and the row's ``touched_symbols``, a
recency decay, and a flat same-repository boost. Deterministic; ties break on
``task_id``. Every hit carries provenance and the "historical -- verify" label.
"""

from __future__ import annotations

from datetime import datetime, timezone

from app.analysis.mapping.text import split_identifier
from app.core.config import Settings
from app.memory import MEMORY_LABEL
from app.memory.index import IndexDoc, MemoryIndex
from app.schemas.memory import MemoryHit

_LEXICAL_W = 0.55
_SYMBOL_W = 0.30
_RECENCY_W = 0.15


def _clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)


def _issue_summary(text: str) -> str:
    line = " ".join((text or "").split())
    return line[:200]


def retrieve(
    rows: list,
    *,
    query_text: str,
    repository_id: str | None,
    exclude_task_id: str | None,
    settings: Settings,
    top_k: int | None = None,
) -> list[MemoryHit]:
    rows = [r for r in rows if r.task_id != exclude_task_id]
    if not rows:
        return []

    index = MemoryIndex.build(
        [
            IndexDoc(
                task_id=r.task_id,
                text=" ".join(
                    [r.issue_text_sanitized, r.fix_summary]
                    + list(r.touched_symbols or [])
                    + list(r.touched_files or [])
                ),
            )
            for r in rows
        ]
    )
    ranked = index.query(query_text, limit=len(rows))
    max_score = max((s for _, s in ranked), default=0.0)
    lexical: dict[str, float] = {
        tid: (s / max_score if max_score > 0 else 0.0) for tid, s in ranked
    }

    query_syms = split_identifier(query_text)
    now = datetime.now(timezone.utc)
    half_life = settings.memory_recency_half_life_days

    hits: list[MemoryHit] = []
    for r in rows:
        row_syms = split_identifier(" ".join(r.touched_symbols or []))
        symbol_overlap = (
            len(query_syms & row_syms) / max(1, len(query_syms))
            if query_syms
            else 0.0
        )
        lex = lexical.get(r.task_id, 0.0)
        # recency + same-repo are boosts on a real content match, never a
        # standalone reason to surface an unrelated task.
        if lex <= 0.0 and symbol_overlap <= 0.0:
            continue

        age_days = max(0.0, (now - _aware(r.created_at)).total_seconds() / 86_400.0)
        recency = 0.5 ** (age_days / half_life)
        same_repo = repository_id is not None and r.repository_id == repository_id

        similarity = _clamp(
            _LEXICAL_W * lex
            + _SYMBOL_W * symbol_overlap
            + _RECENCY_W * recency
            + (settings.memory_same_repo_boost if same_repo else 0.0)
        )
        if similarity < settings.memory_min_similarity:
            continue

        created = _aware(r.created_at)
        hits.append(
            MemoryHit(
                task_id=r.task_id,
                repository_id=r.repository_id,
                outcome=r.outcome,
                verification_verdict=r.verification_verdict,
                issue_summary=_issue_summary(r.issue_text_sanitized),
                fix_summary=r.fix_summary,
                touched_symbols=list(r.touched_symbols or []),
                touched_files=list(r.touched_files or []),
                similarity=round(similarity, 6),
                same_repository=same_repo,
                provenance=(
                    f"task {r.task_id} ({r.outcome}, {created:%Y-%m-%d})"
                ),
                label=MEMORY_LABEL,
                created_at=created,
            )
        )

    hits.sort(key=lambda h: (-h.similarity, h.task_id))
    return hits[: (top_k or settings.memory_retrieval_top_k)]
