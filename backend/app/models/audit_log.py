"""AuditLog -- tamper-evident record of every mutating / autonomous action.

See docs/DATA_MODEL.md Section 2.5. Append-only: no ``updated_at``, no
update/delete path is exposed anywhere in the app. ``task_id`` is a plain
nullable indexed column with no FK yet (``Task`` doesn't exist until a later
phase). The hash-chain (``prev_hash``/``entry_hash``) computation logic
described in docs/GOVERNANCE.md is out of scope for Phase 2 -- only the
table shape lands now.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.ids import new_id
from app.models.base import Base


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    # NOTE: monotonic sequencing (and the hash-chain that depends on it) is assigned by
    # application logic in a later phase, not by DB autoincrement -- `seq` isn't the
    # primary key, so most backends won't auto-populate it. Table shape only for now.
    seq: Mapped[int] = mapped_column(Integer, unique=True, nullable=False)
    task_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    actor: Mapped[str] = mapped_column(String(128), nullable=False)
    action: Mapped[str] = mapped_column(String(128), nullable=False)
    target_type: Mapped[str] = mapped_column(String(64), nullable=False)
    target_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    payload_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    prev_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    entry_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
