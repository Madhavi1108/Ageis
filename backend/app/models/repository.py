"""Repository -- a target repo AEGIS has been pointed at. See docs/DATA_MODEL.md Section 2.1."""

from __future__ import annotations

import enum

from sqlalchemy import String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.ids import new_id
from app.models.base import Base, TimestampMixin


class SourceType(str, enum.Enum):
    LOCAL = "LOCAL"
    GITHUB = "GITHUB"


class Repository(Base, TimestampMixin):
    __tablename__ = "repository"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    source_type: Mapped[str] = mapped_column(String(16), nullable=False)
    # Never contains embedded credentials -- url_validator.validate_remote_url rejects
    # user:pass@ URLs before a Repository row is ever created.
    url_or_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    default_branch: Mapped[str | None] = mapped_column(String(255), nullable=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    owner: Mapped[str | None] = mapped_column(String(255), nullable=True)

    __table_args__ = (
        UniqueConstraint("source_type", "url_or_path", name="uq_repository_source_url"),
    )
