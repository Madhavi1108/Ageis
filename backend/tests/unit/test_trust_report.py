from aegis.schemas.trust_report import EvidenceTrace, TrustReportV0
from aegis.verification.trust import build_trust_report


def test_trust_report_v0_serializes_with_required_fields():
    report = TrustReportV0(
        task_repo="repo",
        task_title="title",
        outcome="VERIFIED",
        evidence_trace=EvidenceTrace(
            why_file=["a.py"], why_change="fix bug", why_tests=["t::x: PASS"], why_safe="all good"
        ),
    )
    data = report.model_dump()
    for key in ("task_repo", "task_title", "outcome", "evidence_trace", "limitations"):
        assert key in data
    assert report.model_dump_json()  # round-trips through JSON without error


def test_build_trust_report_populates_limitations_when_not_verified():
    report = build_trust_report(
        task_repo="repo", task_title="title", outcome="NOT_VERIFIED", limitations=[]
    )
    assert report.limitations, "a non-VERIFIED outcome must always explain itself"


def test_build_trust_report_verified_has_no_forced_limitation():
    report = build_trust_report(task_repo="repo", task_title="title", outcome="VERIFIED")
    assert report.limitations == []
