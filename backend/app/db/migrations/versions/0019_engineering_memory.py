"""engineering_memory + repository_knowledge tables

Revision ID: 0019
Revises: 0018
Create Date: 2026-09-07

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0019"
down_revision: Union[str, None] = "0018"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "engineering_memory",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "repository_id",
            sa.String(length=36),
            sa.ForeignKey("repository.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "task_id",
            sa.String(length=36),
            sa.ForeignKey("task.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("issue_text_sanitized", sa.Text(), nullable=False),
        sa.Column("touched_symbols", sa.JSON(), nullable=False),
        sa.Column("touched_files", sa.JSON(), nullable=False),
        sa.Column("failure_signatures", sa.JSON(), nullable=False),
        sa.Column("fix_summary", sa.Text(), nullable=False),
        sa.Column("plan_ref", sa.JSON(), nullable=False),
        sa.Column("patch_ref", sa.String(length=36), nullable=True),
        sa.Column("review_summary", sa.JSON(), nullable=False),
        sa.Column("verification_verdict", sa.String(length=16), nullable=True),
        sa.Column("outcome", sa.String(length=16), nullable=False),
        sa.Column("embedding_ref", sa.String(length=36), nullable=True),
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
        sa.UniqueConstraint("task_id", name="uq_engineering_memory_task"),
    )
    op.create_index(
        "ix_engineering_memory_repository_id", "engineering_memory", ["repository_id"]
    )
    op.create_index(
        "ix_engineering_memory_created_at", "engineering_memory", ["created_at"]
    )

    op.create_table(
        "repository_knowledge",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "repository_id",
            sa.String(length=36),
            sa.ForeignKey("repository.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("task_count", sa.Integer(), nullable=False),
        sa.Column("risky_files", sa.JSON(), nullable=False),
        sa.Column("recurring_failures", sa.JSON(), nullable=False),
        sa.Column("prior_mappings", sa.JSON(), nullable=False),
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
            "repository_id", name="uq_repository_knowledge_repository"
        ),
    )
    op.create_index(
        "ix_repository_knowledge_repository_id",
        "repository_knowledge",
        ["repository_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_repository_knowledge_repository_id", table_name="repository_knowledge"
    )
    op.drop_table("repository_knowledge")
    op.drop_index(
        "ix_engineering_memory_created_at", table_name="engineering_memory"
    )
    op.drop_index(
        "ix_engineering_memory_repository_id", table_name="engineering_memory"
    )
    op.drop_table("engineering_memory")
