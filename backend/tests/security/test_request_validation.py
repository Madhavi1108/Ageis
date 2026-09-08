"""External-input validation (docs/SECURITY_MODEL.md Section 3): unknown body
fields rejected, un-declared-length bodies rejected, oversized xlsx rejected.
"""

from __future__ import annotations

import io
import zipfile

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.main import app
from app.models.base import Base


@pytest.fixture
def client(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'sec_reqval.db'}")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)

    def _get_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    def _get_settings():
        return Settings(
            ingestion_local_roots=[str(tmp_path)],
            artifacts_root=str(tmp_path / "artifacts"),
            report_import_max_bytes=2048,
            report_import_max_cells=100,
            _env_file=None,
        )

    app.dependency_overrides[get_db] = _get_db
    app.dependency_overrides[get_settings] = _get_settings
    try:
        with TestClient(app) as c:
            yield c
    finally:
        app.dependency_overrides.clear()


def test_unknown_body_field_is_rejected(client):
    resp = client.post(
        "/repositories",
        json={"source_type": "LOCAL", "url_or_path": "/x", "evil_extra": "boom"},
    )
    assert resp.status_code == 422
    assert "evil_extra" in resp.text


def test_unknown_field_in_nested_body_is_rejected(client):
    resp = client.post(
        "/tasks",
        json={
            "repository_id": "r1",
            "issue": {"title": "t", "body": "b", "injected": 1},
        },
    )
    assert resp.status_code == 422


def test_chunked_body_without_content_length_is_rejected(client):
    # httpx sends a generator body as Transfer-Encoding: chunked, no Content-Length
    def _gen():
        yield b'{"source_type": "LOCAL", "url_or_path": "/x"}'

    resp = client.post("/repositories", content=_gen())
    assert resp.status_code == 411


def test_oversized_xlsx_upload_is_rejected(client):
    big = b"PK\x03\x04" + b"\x00" * 4096  # > report_import_max_bytes (2048)
    resp = client.post("/reports/import", content=big)
    assert resp.status_code == 413
    assert resp.json()["code"] == "REPORT_WORKBOOK_TOO_LARGE"


def test_zip_bomb_style_workbook_is_rejected(client):
    # a structurally-valid-ish xlsx whose declared sheet dimension is enormous
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr(
            "[Content_Types].xml",
            '<?xml version="1.0"?><Types xmlns='
            '"http://schemas.openxmlformats.org/package/2006/content-types"/>',
        )
        z.writestr(
            "xl/worksheets/sheet1.xml",
            "<worksheet><dimension ref='A1:ZZ100000'/></worksheet>",
        )
    data = buf.getvalue()
    assert len(data) < 2048  # passes the byte cap, must fail on structure/cells
    resp = client.post("/reports/import", content=data)
    assert resp.status_code in (413, 422)  # too-large (cells) or parse error
