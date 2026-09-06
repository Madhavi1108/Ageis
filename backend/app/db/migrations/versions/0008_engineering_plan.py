"""engineering plan table (engineering_plan)

Revision ID: 0008
Revises: 0007
Create Date: 2026-09-06

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0008"
down_revision: Union[str, None] = "0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "engineering_plan",
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
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("problem_interpretation", sa.Text(), nullable=False),
        sa.Column("assumptions", sa.JSON(), nullable=False),
        sa.Column("files_to_inspect", sa.JSON(), nullable=False),
        sa.Column("files_to_modify", sa.JSON(), nullable=False),
        sa.Column("symbols_to_modify", sa.JSON(), nullable=False),
        sa.Column("dependencies", sa.JSON(), nullable=False),
        sa.Column("steps", sa.JSON(), nullable=False),
        sa.Column("test_strategy", sa.JSON(), nullable=False),
        sa.Column("expected_behavior", sa.Text(), nullable=False),
        sa.Column("regression_risks", sa.JSON(), nullable=False),
        sa.Column("rollback_strategy", sa.Text(), nullable=False),
        sa.Column("source", sa.String(length=24), nullable=False),
        sa.Column("confidence", sa.JSON(), nullable=False),
        sa.Column("evidence", sa.JSON(), nullable=False),
        sa.Column("validation", sa.JSON(), nullable=True),
        sa.Column("validation_verdict", sa.String(length=16), nullable=True),
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
            "task_id", "version", name="uq_engineering_plan_task_version"
        ),
    )
    op.create_index("ix_engineering_plan_task_id", "engineering_plan", ["task_id"])
    op.create_index(
        "ix_engineering_plan_snapshot_id", "engineering_plan", ["snapshot_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_engineering_plan_snapshot_id", table_name="engineering_plan")
    op.drop_index("ix_engineering_plan_task_id", table_name="engineering_plan")
    op.drop_table("engineering_plan")
