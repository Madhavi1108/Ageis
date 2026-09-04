"""SQLAlchemy models. Import all model modules here so Base.metadata sees
every table (Alembic autogenerate and create_all both rely on this)."""

from __future__ import annotations

from app.models.audit_log import AuditLog
from app.models.base import Base
from app.models.job import Job

__all__ = ["Base", "Job", "AuditLog"]
