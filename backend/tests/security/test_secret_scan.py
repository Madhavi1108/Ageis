"""No secret reaches a log record or a persisted artifact
(docs/SECURITY_MODEL.md Section 4). Re-asserted through the Phase 26
``core.security`` module paths.
"""

from __future__ import annotations

import io
import json
import logging
from pathlib import Path

from app.core.security import contains_secret, redact, scrub_secret_env
from app.core.security.redaction import REDACTED

FAKE_TOKEN = "ghp_" + "b" * 36
FAKE_KEY = "sk-" + "c" * 40


def test_redact_masks_known_shapes():
    for probe, secret in (
        (f"Authorization: Bearer {FAKE_KEY}", FAKE_KEY),
        (f"token={FAKE_TOKEN}", FAKE_TOKEN),
        (f"api_key: {FAKE_KEY}", FAKE_KEY),
        ("password=hunter2secret", "hunter2secret"),
    ):
        out = redact(probe)
        assert REDACTED in out
        assert secret not in out


def test_logging_filter_scrubs_records():
    from app.core.logging import JSONFormatter, RedactionFilter

    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.addFilter(RedactionFilter())
    handler.setFormatter(JSONFormatter())
    logger = logging.getLogger("aegis.security.test")
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    try:
        logger.info("cloning with token %s into workspace", FAKE_TOKEN)
        logger.info("payload=%s", json.dumps({"api_key": FAKE_KEY}))
    finally:
        logger.removeHandler(handler)

    blob = stream.getvalue()
    assert FAKE_TOKEN not in blob
    assert FAKE_KEY not in blob
    assert not contains_secret(blob)


def test_scrub_secret_env_drops_credential_shaped_names():
    src = {
        "PATH": "/usr/bin",
        "ANTHROPIC_API_KEY": FAKE_KEY,
        "AWS_SECRET_ACCESS_KEY": "x",
        "GITHUB_TOKEN": FAKE_TOKEN,
        "AEGIS_DATABASE_URL": "postgres://u:p@h/db",
        "MY_PASSWORD": "p",
        "LANG": "C.UTF-8",
    }
    out = scrub_secret_env(src)
    assert set(out) == {"PATH", "LANG"}


def test_no_artifact_contains_a_secret(
    db_session, security_settings, monkeypatch, tmp_path
):
    """A tiny ingest+analyze run leaves nothing secret-shaped in artifacts_root."""
    from app.analysis.analyze import analyze_snapshot
    from app.ingestion.ingest import ingest_repository
    from app.repository.repositories import RepositoryRepository
    from app.repository.snapshots import SnapshotRepository
    from app.schemas.repository import IngestRequest

    monkeypatch.setenv("ANTHROPIC_API_KEY", FAKE_KEY)
    monkeypatch.setenv("AEGIS_GITHUB_TOKEN", FAKE_TOKEN)

    src = tmp_path / "proj"
    src.mkdir()
    (src / "m.py").write_text("def f(x):\n    return x + 1\n", encoding="utf-8")
    (src / "test_m.py").write_text(
        "from m import f\n\n\ndef test_f():\n    assert f(1) == 2\n", encoding="utf-8"
    )

    repo = RepositoryRepository(db_session).get_or_create(
        source_type="LOCAL", url_or_path=str(src), name="proj"
    )
    ingested = ingest_repository(
        db_session, repository=repo, request=IngestRequest(), settings=security_settings
    )
    analyze_snapshot(
        db_session,
        snapshot=SnapshotRepository(db_session).get(ingested.snapshot_id),
        settings=security_settings,
    )

    root = Path(security_settings.artifacts_root)
    offenders = []
    for p in root.rglob("*"):
        if p.is_file():
            text = p.read_text(encoding="utf-8", errors="ignore")
            if contains_secret(text):
                offenders.append(str(p.relative_to(root)))
    assert offenders == [], f"secret-shaped content in artifacts: {offenders}"
