"""failure + investigation tables

Revision ID: 0012
Revises: 0011
Create Date: 2026-09-06

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0012"
down_revision: Union[str, None] = "0011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "failure",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "execution_id",
            sa.String(length=36),
            sa.ForeignKey("test_execution.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "task_id",
            sa.String(length=36),
            sa.ForeignKey("task.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("test_name", sa.String(length=512), nullable=False),
        sa.Column("failure_type", sa.String(length=24), nullable=False),
        sa.Column(
            "traceback_artifact_id",
            sa.String(length=36),
            sa.ForeignKey("artifact.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("frames", sa.JSON(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_failure_task_id", "failure", ["task_id"])
    op.create_index("ix_failure_execution_id", "failure", ["execution_id"])

    op.create_table(
        "investigation",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "task_id",
            sa.String(length=36),
            sa.ForeignKey("task.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "execution_id",
            sa.String(length=36),
            sa.ForeignKey("test_execution.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("failure_ids", sa.JSON(), nullable=False),
        sa.Column("evidence", sa.JSON(), nullable=False),
        sa.Column("facts", sa.JSON(), nullable=False),
        sa.Column("inferences", sa.JSON(), nullable=False),
        sa.Column("classification", sa.JSON(), nullable=False),
        sa.Column("failures", sa.JSON(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
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
            "task_id", "execution_id", name="uq_investigation_task_execution"
        ),
    )
    op.create_index("ix_investigation_task_id", "investigation", ["task_id"])


def downgrade() -> None:
    op.drop_index("ix_investigation_task_id", table_name="investigation")
    op.drop_table("investigation")
    op.drop_index("ix_failure_execution_id", table_name="failure")
    op.drop_index("ix_failure_task_id", table_name="failure")
    op.drop_table("failure")
