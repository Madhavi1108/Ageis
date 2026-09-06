"""Merge, de-duplicate, normalise and order review findings
(docs/AEGIS_IMPLEMENTATION_PLAN.md Section 24, step 4).
"""

from __future__ import annotations

import re

from aegis.schemas.common import Confidence, Evidence

from app.review._finding import RawFinding
from app.schemas.review import ReviewFinding

_SEV_RANK = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3, "INFO": 4}
_SOURCE_RANK = {"RULE": 0, "STATIC": 1, "AI": 2}
_VALID_SEV = set(_SEV_RANK)
_VALID_CAT = {
    "CORRECTNESS",
    "SCOPE",
    "SECURITY",
    "MAINTAINABILITY",
    "ARCHITECTURE",
    "PERFORMANCE",
    "ERROR_HANDLING",
    "TEST_QUALITY",
    "REGRESSION_RISK",
    "DEPENDENCY_IMPACT",
}


def _norm_sev(sev: str) -> str:
    s = (sev or "").upper()
    return s if s in _VALID_SEV else "LOW"


def _norm_cat(cat: str) -> str:
    c = (cat or "").upper()
    return c if c in _VALID_CAT else "MAINTAINABILITY"


def _key(description: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (description or "").lower()).strip()[:60]


def scope_findings(
    changed_files: set[str], allowed_scope: set[str]
) -> list[RawFinding]:
    out: list[RawFinding] = []
    for path in sorted(changed_files - allowed_scope):
        out.append(
            RawFinding(
                source="RULE",
                category="SCOPE",
                severity="HIGH",
                description=f"changed file {path!r} is outside the plan's declared scope",
                recommendation="restrict the change to the planned files, or justify the scope",
                file=path,
                line_start=1,
                evidence=[
                    Evidence(kind="file", ref=path, detail="not in allowed scope")
                ],
                confidence=Confidence(value=1.0, basis="FACT"),
            )
        )
    return out


def aggregate(raw: list[RawFinding]) -> list[ReviewFinding]:
    best: dict[tuple, RawFinding] = {}
    for f in raw:
        f.severity = _norm_sev(f.severity)
        f.category = _norm_cat(f.category)
        k = (f.file, f.line_start, f.category, _key(f.description))
        cur = best.get(k)
        if cur is None:
            best[k] = f
            continue
        # keep the higher severity; on a tie prefer the more authoritative source
        if _SEV_RANK[f.severity] < _SEV_RANK[cur.severity] or (
            f.severity == cur.severity
            and _SOURCE_RANK.get(f.source, 3) < _SOURCE_RANK.get(cur.source, 3)
        ):
            best[k] = f

    merged = sorted(
        best.values(),
        key=lambda f: (
            _SEV_RANK[f.severity],
            f.file or "",
            f.line_start or 0,
            f.category,
        ),
    )
    return [
        ReviewFinding(
            source=f.source,
            category=f.category,
            severity=f.severity,
            file=f.file,
            line_start=f.line_start,
            line_end=f.line_end,
            description=f.description,
            recommendation=f.recommendation or "(no recommendation)",
            evidence=f.evidence,
            confidence=f.confidence,
            status="OPEN",
        )
        for f in merged
    ]


def blocking(findings: list[ReviewFinding]) -> bool:
    return any(
        f.status == "OPEN" and f.severity in ("CRITICAL", "HIGH") for f in findings
    )
