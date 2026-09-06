"""Root-cause analysis for the repair loop (docs/AEGIS_IMPLEMENTATION_PLAN.md
Section 22, step 2; docs/AI_AGENT_DESIGN.md Section 5).

AI when a provider is configured (``template="rca"``, schema-validated,
evidence-required); a deterministic heuristic fallback otherwise. The fallback
NEVER emits a bare ``FACT`` -- it returns a single ``HYPOTHESIS`` plus
``open_questions`` (Section 21: missing information is UNKNOWN, not a guessed
fact).
"""

from __future__ import annotations

import json
from typing import Any

from aegis.schemas.common import Confidence, Evidence
from app.ai.provider import AIProvider
from app.ai.routing import tier_for
from app.schemas.failure import FailureAnalysis
from app.schemas.repair import Hypothesis, RootCauseAnalysis

_TEMPLATE = "rca"


def _fa_summary(fa: FailureAnalysis) -> str:
    return json.dumps(
        {
            "classification": fa.classification,
            "failures": [
                {
                    "test_name": f.test_name,
                    "failure_type": f.failure_type,
                    "exception_type": f.exception_type,
                    "message": f.message,
                    "frames": [
                        {
                            "file": fr.file,
                            "lineno": fr.lineno,
                            "symbol_id": fr.symbol_id,
                            "in_diff": fr.in_diff,
                        }
                        for fr in f.frames
                    ],
                }
                for f in fa.failures
            ],
            "facts": fa.facts,
            "inferences": fa.inferences,
        },
        indent=2,
    )


def _code_context(fa: FailureAnalysis) -> str:
    slices = fa.evidence.get("code_slices", []) if isinstance(fa.evidence, dict) else []
    return (
        "\n\n".join(
            f"# {s.get('file')}:{s.get('lineno')}\n{s.get('slice') or ''}"
            for s in slices
        )
        or "(no code slices available)"
    )


def build_fallback_rca(fa: FailureAnalysis) -> RootCauseAnalysis:
    primary = fa.classification.get("primary_symbol_id") or "<unknown symbol>"
    first = fa.failures[0] if fa.failures else None
    evidence: list[Evidence] = []
    if first is not None:
        evidence.append(
            Evidence(
                kind="test",
                ref=first.test_name,
                detail=f"{first.failure_type}: {first.message or '(no message)'}",
            )
        )
    return RootCauseAnalysis(
        hypotheses=[
            Hypothesis(
                statement=(
                    f"The failing test exercises {primary}; the defect is most "
                    "likely there, but no root-cause model was available to confirm it."
                ),
                label="HYPOTHESIS",
                evidence=evidence,
                rank=0,
            )
        ],
        most_likely_index=0,
        open_questions=[
            f"What minimal change to {primary} makes the failing assertion pass "
            "without breaking the existing tests?"
        ],
        confidence=Confidence(value=0.2, basis="UNKNOWN"),
        evidence=evidence,
    )


def analyze(
    *,
    failure_analysis: FailureAnalysis,
    provider: AIProvider | None,
    settings: Any,
    task_key: str,
) -> RootCauseAnalysis:
    if provider is None:
        return build_fallback_rca(failure_analysis)

    diff_text = ""
    if isinstance(failure_analysis.evidence, dict):
        diff_text = "\n".join(failure_analysis.evidence.get("diff_hunks", []))

    variables = {
        "task_key": task_key,
        "failure_analysis": _fa_summary(failure_analysis),
        "code_context": _code_context(failure_analysis),
        "diff": diff_text or "(no diff available)",
    }
    result = provider.complete(
        template=_TEMPLATE,
        variables=variables,
        schema=RootCauseAnalysis,
        tier=tier_for("root_cause"),
        timeout_s=settings.ai_rca_timeout_s,
        max_tokens=settings.ai_repair_max_tokens,
    )
    assert isinstance(result, RootCauseAnalysis)
    return result
