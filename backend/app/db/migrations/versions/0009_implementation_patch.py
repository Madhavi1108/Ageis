"""implementation + patch tables (implementation, patch)

Revision ID: 0009
Revises: 0008
Create Date: 2026-09-06

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0009"
down_revision: Union[str, None] = "0008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "implementation",
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
        sa.Column(
            "plan_id",
            sa.String(length=36),
            sa.ForeignKey("engineering_plan.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("edit_ops", sa.JSON(), nullable=False),
        sa.Column("scope_violations", sa.JSON(), nullable=False),
        sa.Column("traceability", sa.JSON(), nullable=False),
        sa.Column("source", sa.String(length=16), nullable=False),
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
            "task_id", "version", name="uq_implementation_task_version"
        ),
    )
    op.create_index("ix_implementation_task_id", "implementation", ["task_id"])
    op.create_index(
        "ix_implementation_snapshot_id", "implementation", ["snapshot_id"]
    )
    op.create_index("ix_implementation_plan_id", "implementation", ["plan_id"])

    op.create_table(
        "patch",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "implementation_id",
            sa.String(length=36),
            sa.ForeignKey("implementation.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "artifact_id",
            sa.String(length=36),
            sa.ForeignKey("artifact.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("touched_paths", sa.JSON(), nullable=False),
        sa.Column("diff_size", sa.Integer(), nullable=False),
        sa.Column(
            "is_candidate", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
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
    )
    op.create_index("ix_patch_implementation_id", "patch", ["implementation_id"])


def downgrade() -> None:
    op.drop_index("ix_patch_implementation_id", table_name="patch")
    op.drop_table("patch")
    op.drop_index("ix_implementation_plan_id", table_name="implementation")
    op.drop_index("ix_implementation_snapshot_id", table_name="implementation")
    op.drop_index("ix_implementation_task_id", table_name="implementation")
    op.drop_table("implementation")
