"""task / issue ingestion tables (issue, task, task_step)

Revision ID: 0005
Revises: 0004
Create Date: 2026-09-05

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "issue",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "repository_id",
            sa.String(length=36),
            sa.ForeignKey("repository.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("source", sa.String(length=16), nullable=False),
        sa.Column("external_ref", sa.String(length=255), nullable=True),
        sa.Column("title", sa.String(length=512), nullable=False),
        sa.Column("body_sanitized", sa.Text(), nullable=False),
        sa.Column("imported_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_issue_repository_id", "issue", ["repository_id"])
    op.create_index(
        "ix_issue_source_external_ref", "issue", ["source", "external_ref"]
    )

    op.create_table(
        "task",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "repository_id",
            sa.String(length=36),
            sa.ForeignKey("repository.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "issue_id",
            sa.String(length=36),
            sa.ForeignKey("issue.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "snapshot_id",
            sa.String(length=36),
            sa.ForeignKey("repository_snapshot.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column("task_type", sa.String(length=16), nullable=False),
        sa.Column("title", sa.String(length=512), nullable=False),
        sa.Column("description_sanitized", sa.Text(), nullable=False),
        sa.Column("constraints", sa.JSON(), nullable=True),
        sa.Column("priority", sa.String(length=8), nullable=False),
        sa.Column("allowed_paths", sa.JSON(), nullable=True),
        sa.Column("idempotency_key", sa.String(length=64), nullable=False),
        sa.Column("state", sa.String(length=24), nullable=False),
        sa.Column("terminal_reason", sa.String(length=512), nullable=True),
        sa.Column("created_by", sa.String(length=255), nullable=False),
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
        sa.UniqueConstraint(
            "repository_id", "idempotency_key", name="uq_task_repo_idempotency"
        ),
    )
    op.create_index("ix_task_state", "task", ["state"])
    op.create_index("ix_task_repository_id", "task", ["repository_id"])
    op.create_index("ix_task_created_at", "task", ["created_at"])

    op.create_table(
        "task_step",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "task_id",
            sa.String(length=36),
            sa.ForeignKey("task.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("state", sa.String(length=24), nullable=False),
        sa.Column("entered_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("exited_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("agent", sa.String(length=64), nullable=True),
        sa.Column("input_ref", sa.String(length=36), nullable=True),
        sa.Column("output_ref", sa.String(length=36), nullable=True),
        sa.Column("error", sa.JSON(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.UniqueConstraint("task_id", "seq", name="uq_task_step_task_seq"),
    )
    op.create_index("ix_task_step_task_seq", "task_step", ["task_id", "seq"])
    op.create_index("ix_task_step_task_state", "task_step", ["task_id", "state"])


def downgrade() -> None:
    op.drop_index("ix_task_step_task_state", table_name="task_step")
    op.drop_index("ix_task_step_task_seq", table_name="task_step")
    op.drop_table("task_step")

    op.drop_index("ix_task_created_at", table_name="task")
    op.drop_index("ix_task_repository_id", table_name="task")
    op.drop_index("ix_task_state", table_name="task")
    op.drop_table("task")

    op.drop_index("ix_issue_source_external_ref", table_name="issue")
    op.drop_index("ix_issue_repository_id", table_name="issue")
    op.drop_table("issue")
