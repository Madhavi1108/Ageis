"""regression_plan table

Revision ID: 0014
Revises: 0013
Create Date: 2026-09-06

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0014"
down_revision: Union[str, None] = "0013"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "regression_plan",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "task_id",
            sa.String(length=36),
            sa.ForeignKey("task.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "snapshot_id",
            sa.String(length=36),
            sa.ForeignKey("repository_snapshot.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("mode", sa.String(length=8), nullable=False),
        sa.Column("changed_set", sa.JSON(), nullable=False),
        sa.Column("tests", sa.JSON(), nullable=False),
        sa.Column("selection", sa.JSON(), nullable=False),
        sa.Column("full_suite_count", sa.Integer(), nullable=False),
        sa.Column("subset_justification", sa.Text(), nullable=True),
        sa.Column("subset_risk_note", sa.Text(), nullable=True),
        sa.Column(
            "execution_id",
            sa.String(length=36),
            sa.ForeignKey("test_execution.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("baseline_execution_id", sa.String(length=36), nullable=True),
        sa.Column("new_failures", sa.JSON(), nullable=False),
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
        sa.UniqueConstraint("task_id", name="uq_regression_plan_task"),
    )
    op.create_index("ix_regression_plan_task_id", "regression_plan", ["task_id"])


def downgrade() -> None:
    op.drop_index("ix_regression_plan_task_id", table_name="regression_plan")
    op.drop_table("regression_plan")
