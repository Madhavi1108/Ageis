"""initial job and audit_log tables

Revision ID: 0001
Revises:
Create Date: 2026-09-04

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "job",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("task_id", sa.String(length=36), nullable=True),
        sa.Column("type", sa.String(length=20), nullable=False),
        sa.Column("state", sa.String(length=20), nullable=False),
        sa.Column("progress", sa.Float(), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("max_attempts", sa.Integer(), nullable=False),
        sa.Column("idempotency_key", sa.String(length=64), nullable=False),
        sa.Column("dedupe_key", sa.String(length=64), nullable=True),
        sa.Column("last_checkpoint", sa.JSON(), nullable=True),
        sa.Column("worker_id", sa.String(length=64), nullable=True),
        sa.Column("queued_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error", sa.JSON(), nullable=True),
        sa.Column("logs_artifact_id", sa.String(length=36), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("idempotency_key", name="uq_job_idempotency_key"),
    )
    op.create_index("ix_job_task_id", "job", ["task_id"])
    op.create_index("ix_job_state", "job", ["state"])
    op.create_index("ix_job_dedupe_key", "job", ["dedupe_key"])

    op.create_table(
        "audit_log",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("task_id", sa.String(length=36), nullable=True),
        sa.Column("actor", sa.String(length=128), nullable=False),
        sa.Column("action", sa.String(length=128), nullable=False),
        sa.Column("target_type", sa.String(length=64), nullable=False),
        sa.Column("target_id", sa.String(length=36), nullable=True),
        sa.Column("payload_digest", sa.String(length=64), nullable=False),
        sa.Column("prev_hash", sa.String(length=64), nullable=True),
        sa.Column("entry_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("seq", name="uq_audit_log_seq"),
    )
    op.create_index("ix_audit_log_task_id", "audit_log", ["task_id"])


def downgrade() -> None:
    op.drop_index("ix_audit_log_task_id", table_name="audit_log")
    op.drop_table("audit_log")

    op.drop_index("ix_job_dedupe_key", table_name="job")
    op.drop_index("ix_job_state", table_name="job")
    op.drop_index("ix_job_task_id", table_name="job")
    op.drop_table("job")
