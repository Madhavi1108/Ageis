"""commit + pull_request tables

Revision ID: 0018
Revises: 0017
Create Date: 2026-09-07

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0018"
down_revision: Union[str, None] = "0017"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "commit",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "repository_id",
            sa.String(length=36),
            sa.ForeignKey("repository.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("sha", sa.String(length=64), nullable=False),
        sa.Column("authored_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("author_email_hash", sa.String(length=64), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("files_changed", sa.JSON(), nullable=False),
        sa.Column("insertions", sa.Integer(), nullable=False),
        sa.Column("deletions", sa.Integer(), nullable=False),
        sa.Column("is_related_fix", sa.Boolean(), nullable=False),
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
        sa.UniqueConstraint("repository_id", "sha", name="uq_commit_repo_sha"),
    )
    op.create_index("ix_commit_repository_id", "commit", ["repository_id"])
    op.create_index("ix_commit_authored_at", "commit", ["authored_at"])

    op.create_table(
        "pull_request",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "task_id",
            sa.String(length=36),
            sa.ForeignKey("task.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("mode", sa.String(length=16), nullable=False),
        sa.Column("title", sa.String(length=512), nullable=False),
        sa.Column(
            "body_artifact_id",
            sa.String(length=36),
            sa.ForeignKey("artifact.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("branch", sa.String(length=255), nullable=True),
        sa.Column("commit_sha", sa.String(length=64), nullable=True),
        sa.Column("github_url", sa.String(length=1024), nullable=True),
        sa.Column("github_number", sa.Integer(), nullable=True),
        sa.Column("state", sa.String(length=16), nullable=False),
        sa.Column("failure_reason", sa.String(length=512), nullable=True),
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
    op.create_index("ix_pull_request_task_id", "pull_request", ["task_id"])
    op.create_index("ix_pull_request_state", "pull_request", ["state"])


def downgrade() -> None:
    op.drop_index("ix_pull_request_state", table_name="pull_request")
    op.drop_index("ix_pull_request_task_id", table_name="pull_request")
    op.drop_table("pull_request")
    op.drop_index("ix_commit_authored_at", table_name="commit")
    op.drop_index("ix_commit_repository_id", table_name="commit")
    op.drop_table("commit")
