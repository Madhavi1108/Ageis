"""issue -> code mapping table (code_mapping)

Revision ID: 0006
Revises: 0005
Create Date: 2026-09-06

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "code_mapping",
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
        sa.Column("candidates", sa.JSON(), nullable=False),
        sa.Column("related_tests", sa.JSON(), nullable=False),
        sa.Column("dependencies", sa.JSON(), nullable=False),
        sa.Column("overall_confidence", sa.Float(), nullable=False),
        sa.Column("semantic_available", sa.Boolean(), nullable=False),
        sa.Column("model_version", sa.String(length=32), nullable=False),
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
        sa.UniqueConstraint("task_id", name="uq_code_mapping_task"),
    )
    op.create_index("ix_code_mapping_task_id", "code_mapping", ["task_id"])
    op.create_index("ix_code_mapping_snapshot_id", "code_mapping", ["snapshot_id"])


def downgrade() -> None:
    op.drop_index("ix_code_mapping_snapshot_id", table_name="code_mapping")
    op.drop_index("ix_code_mapping_task_id", table_name="code_mapping")
    op.drop_table("code_mapping")
