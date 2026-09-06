"""repair_attempt table

Revision ID: 0013
Revises: 0012
Create Date: 2026-09-06

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0013"
down_revision: Union[str, None] = "0012"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "repair_attempt",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "task_id",
            sa.String(length=36),
            sa.ForeignKey("task.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("iteration", sa.Integer(), nullable=False),
        sa.Column("root_cause", sa.JSON(), nullable=False),
        sa.Column("proposal", sa.JSON(), nullable=False),
        sa.Column("hypothesis", sa.Text(), nullable=False),
        sa.Column("edit_ops", sa.JSON(), nullable=False),
        sa.Column("outcome", sa.String(length=16), nullable=False),
        sa.Column("score", sa.JSON(), nullable=False),
        sa.Column(
            "candidate_patch_id",
            sa.String(length=36),
            sa.ForeignKey("patch.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "targeted_execution_id",
            sa.String(length=36),
            sa.ForeignKey("test_execution.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "regression_execution_id",
            sa.String(length=36),
            sa.ForeignKey("test_execution.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("run_summary", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "task_id", "iteration", name="uq_repair_attempt_task_iteration"
        ),
    )
    op.create_index("ix_repair_attempt_task_id", "repair_attempt", ["task_id"])


def downgrade() -> None:
    op.drop_index("ix_repair_attempt_task_id", table_name="repair_attempt")
    op.drop_table("repair_attempt")
