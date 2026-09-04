from app.core.errors import AppError, ErrorEnvelope
from aegis.schemas.common import Evidence


def test_envelope_serialization_minimal():
    envelope = ErrorEnvelope(code="NOT_FOUND", message="Job not found.")
    dumped = envelope.model_dump()
    assert dumped == {
        "code": "NOT_FOUND",
        "message": "Job not found.",
        "details": None,
        "evidence": None,
    }


def test_envelope_serialization_with_details_and_evidence():
    envelope = ErrorEnvelope(
        code="INVALID_STATE",
        message="Job cannot transition.",
        details={"from": "FAILED", "to": "RUNNING"},
        evidence=[Evidence(kind="file", ref="app/models/job.py", detail="state enum")],
    )
    dumped = envelope.model_dump()
    assert dumped["code"] == "INVALID_STATE"
    assert dumped["details"] == {"from": "FAILED", "to": "RUNNING"}
    assert dumped["evidence"][0]["kind"] == "file"


def test_app_error_to_envelope_round_trips_fields():
    err = AppError(
        "RATE_LIMITED",
        "Too many requests.",
        status_code=429,
        details={"retry_after": 5},
    )
    envelope = err.to_envelope()
    assert envelope.code == "RATE_LIMITED"
    assert envelope.message == "Too many requests."
    assert envelope.details == {"retry_after": 5}
    assert err.status_code == 429
