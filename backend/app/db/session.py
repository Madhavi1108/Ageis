"""SQLAlchemy engine and session wiring.

See docs/AEGIS_IMPLEMENTATION_PLAN.md Section 10: sync engine is acceptable
for dev (async optional, documented -- see CONTRIBUTING.md). Default DSN is
SQLite for zero-infra local dev; Postgres is opt-in via AEGIS_DATABASE_URL
(docs/TECH_STACK.md Section 2, docs/DECISIONS ADR-0001).
"""

from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings, get_settings


def make_engine(settings: Settings) -> Engine:
    connect_args = (
        {"check_same_thread": False}
        if settings.database_url.startswith("sqlite")
        else {}
    )
    return create_engine(settings.database_url, connect_args=connect_args)


engine = make_engine(get_settings())
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Iterator[Session]:
    """FastAPI dependency yielding a request-scoped Session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
