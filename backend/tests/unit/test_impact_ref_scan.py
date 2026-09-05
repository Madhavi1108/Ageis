"""Config / DB reference scanners -- best-effort, always basis INFERENCE
(Specification Section 21, docs/REPOSITORY_ANALYSIS.md Section 6)."""

from __future__ import annotations

from app.analysis.impact import _scan_refs, _security_sensitive

_CONFIG_SRC = """
import os
from app.core.config import Settings

def load():
    timeout = settings.request_timeout_s
    key = os.environ["API_KEY"]
    dsn = os.getenv("DATABASE_URL")
    return timeout, key, dsn
"""

_DB_SRC = """
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base

class Widget(Base):
    __tablename__ = "widget"
    id: Mapped[str] = mapped_column(primary_key=True)

def recent(session):
    return session.execute("SELECT * FROM widget LIMIT 10")
"""


def test_config_scanner_finds_settings_and_env():
    config_refs, _ = _scan_refs({"loader.py": _CONFIG_SRC})
    details = {r["detail"] for r in config_refs}
    assert any("request_timeout_s" in d for d in details)
    assert any("API_KEY" in d for d in details)
    assert any("DATABASE_URL" in d for d in details)
    assert all(r["basis"] == "INFERENCE" for r in config_refs)
    assert all(r["ref"] == "loader.py" for r in config_refs)


def test_db_scanner_finds_model_and_sql_literal():
    _, db_refs = _scan_refs({"models.py": _DB_SRC})
    details = {r["detail"] for r in db_refs}
    assert "ORM model (Base subclass)" in details
    assert "SQL string literal" in details
    assert all(r["basis"] == "INFERENCE" for r in db_refs)


def test_no_refs_in_plain_code():
    plain = "def add(a, b):\n    return a + b\n"
    config_refs, db_refs = _scan_refs({"math.py": plain})
    assert config_refs == []
    assert db_refs == []


def test_security_sensitive_detects_crypto():
    assert _security_sensitive({"auth.py": "import hashlib\n"}) is True
    assert _security_sensitive({"x.py": "import subprocess\n"}) is True
    assert _security_sensitive({"pure.py": "def f():\n    return 1\n"}) is False


def test_security_sensitive_uses_path_too():
    assert _security_sensitive({"app/auth/tokens.py": "x = 1\n"}) is True
