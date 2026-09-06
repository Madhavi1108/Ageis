"""AI code reviewer (docs/AEGIS_IMPLEMENTATION_PLAN.md Section 24, step 3).

Schema-constrained, evidence-required. A finding without a concrete ``file`` +
integer ``line_start`` is forced to ``INFO`` (Section 24). No provider -> ``[]``:
the deterministic static + rule layers are the floor. A schema-invalid response
yields ``[]`` + a gap note rather than failing the whole review.
"""

from __future__ import annotations

from aegis.schemas.common import Confidence, Evidence
from app.ai.provider import AIProvider
from app.ai.routing import tier_for
from app.ai.schema_guard import AIOutputInvalid
from app.review._finding import RawFinding
from app.schemas.review import ReviewFindingsAI

_TEMPLATE = "code_review"


def ai_review(
    *,
    diff_text: str,
    files_src: dict[str, str],
    provider: AIProvider | None,
    settings,
    task_key: str,
) -> tuple[list[RawFinding], list[str]]:
    if provider is None:
        return [], []
    if len(diff_text.encode("utf-8")) > settings.review_max_diff_bytes:
        return [], ["diff exceeds review_max_diff_bytes; AI review skipped"]

    joined = "\n\n".join(f"### {p}\n{s}" for p, s in sorted(files_src.items()))
    variables = {
        "task_key": task_key,
        "diff": diff_text or "(no diff)",
        "changed_files": joined or "(no changed files)",
    }
    try:
        result = provider.complete(
            template=_TEMPLATE,
            variables=variables,
            schema=ReviewFindingsAI,
            tier=tier_for("code_review"),
            timeout_s=settings.review_ai_timeout_s,
            max_tokens=settings.review_ai_max_tokens,
        )
    except AIOutputInvalid as exc:
        return [], [f"AI review produced no schema-valid output: {exc}"]
    assert isinstance(result, ReviewFindingsAI)

    out: list[RawFinding] = []
    for f in result.findings:
        has_anchor = bool(f.file) and isinstance(f.line_start, int)
        severity = f.severity if has_anchor else "INFO"
        out.append(
            RawFinding(
                source="AI",
                category=f.category,
                severity=severity,
                description=f.description,
                recommendation=f.recommendation or "(no recommendation given)",
                file=f.file,
                line_start=f.line_start,
                line_end=f.line_end,
                evidence=list(f.evidence)
                or [
                    Evidence(
                        kind="line_range",
                        ref=f"{f.file}:{f.line_start}",
                        detail="AI reviewer finding",
                    )
                ],
                confidence=f.confidence or Confidence(value=0.5, basis="INFERENCE"),
            )
        )
    return out, []
