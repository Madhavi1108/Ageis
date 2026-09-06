"""Finding aggregation: normalise, de-dup, scope, order, blocking."""

from __future__ import annotations

from aegis.schemas.common import Confidence
from app.review._finding import RawFinding
from app.review.aggregate import aggregate, blocking, scope_findings


def _raw(source, cat, sev, file="a.py", line=1, desc="an issue"):
    return RawFinding(
        source=source,
        category=cat,
        severity=sev,
        description=desc,
        recommendation="fix it",
        file=file,
        line_start=line,
        confidence=Confidence(value=0.8, basis="FACT"),
    )


def test_dedup_prefers_static_over_ai_on_same_anchor():
    out = aggregate(
        [
            _raw("AI", "SECURITY", "HIGH"),
            _raw("STATIC", "SECURITY", "HIGH"),
        ]
    )
    assert len(out) == 1
    assert out[0].source == "STATIC"


def test_dedup_keeps_higher_severity():
    out = aggregate(
        [
            _raw("STATIC", "SECURITY", "LOW"),
            _raw("AI", "SECURITY", "CRITICAL"),
        ]
    )
    assert len(out) == 1
    assert out[0].severity == "CRITICAL"


def test_sorted_by_severity_then_location():
    out = aggregate(
        [
            _raw("RULE", "MAINTAINABILITY", "LOW", file="z.py", line=9, desc="z"),
            _raw("RULE", "SECURITY", "CRITICAL", file="a.py", line=2, desc="c"),
            _raw("RULE", "SECURITY", "HIGH", file="a.py", line=5, desc="h"),
        ]
    )
    assert [f.severity for f in out] == ["CRITICAL", "HIGH", "LOW"]


def test_unknown_severity_and_category_normalised():
    out = aggregate([_raw("AI", "WHATEVER", "SCARY")])
    assert out[0].severity == "LOW"
    assert out[0].category == "MAINTAINABILITY"


def test_scope_finding_added_for_out_of_scope_file():
    out = scope_findings({"a.py", "evil.py"}, {"a.py"})
    assert len(out) == 1
    assert out[0].category == "SCOPE" and out[0].severity == "HIGH"
    assert out[0].file == "evil.py"


def test_blocking_iff_open_critical_or_high():
    assert blocking(aggregate([_raw("RULE", "SECURITY", "HIGH")])) is True
    assert blocking(aggregate([_raw("RULE", "MAINTAINABILITY", "LOW")])) is False
