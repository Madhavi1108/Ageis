"""repository ingestion tables (repository, repository_snapshot, repository_file, artifact)

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-04

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "repository",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("source_type", sa.String(length=16), nullable=False),
        sa.Column("url_or_path", sa.String(length=1024), nullable=False),
        sa.Column("default_branch", sa.String(length=255), nullable=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("owner", sa.String(length=255), nullable=True),
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
            "source_type", "url_or_path", name="uq_repository_source_url"
        ),
    )
    op.create_index("ix_repository_name", "repository", ["name"])

    op.create_table(
        "repository_snapshot",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "repository_id",
            sa.String(length=36),
            sa.ForeignKey("repository.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("commit_sha", sa.String(length=64), nullable=False),
        sa.Column("branch", sa.String(length=255), nullable=True),
        sa.Column("ingested_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("file_count", sa.Integer(), nullable=False),
        sa.Column("total_bytes", sa.Integer(), nullable=False),
        sa.Column("history_depth", sa.Integer(), nullable=False),
        sa.Column("languages", sa.JSON(), nullable=True),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("limit_reason", sa.String(length=512), nullable=True),
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
            "repository_id", "commit_sha", name="uq_snapshot_repo_commit"
        ),
    )
    op.create_index(
        "ix_snapshot_repository_id", "repository_snapshot", ["repository_id"]
    )
    op.create_index("ix_snapshot_status", "repository_snapshot", ["status"])

    op.create_table(
        "repository_file",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "snapshot_id",
            sa.String(length=36),
            sa.ForeignKey("repository_snapshot.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("path", sa.String(length=1024), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("language", sa.String(length=32), nullable=False),
        sa.Column("is_test", sa.Boolean(), nullable=False),
        sa.Column("is_vendored", sa.Boolean(), nullable=False),
        sa.Column("parse_status", sa.String(length=16), nullable=False),
        sa.Column("parse_error", sa.String(length=2048), nullable=True),
        sa.UniqueConstraint("snapshot_id", "path", name="uq_file_snapshot_path"),
    )
    op.create_index("ix_file_snapshot_path", "repository_file", ["snapshot_id", "path"])
    op.create_index(
        "ix_file_snapshot_is_test", "repository_file", ["snapshot_id", "is_test"]
    )
    op.create_index("ix_file_language", "repository_file", ["language"])

    op.create_table(
        "artifact",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("task_id", sa.String(length=36), nullable=True),
        sa.Column(
            "snapshot_id",
            sa.String(length=36),
            sa.ForeignKey("repository_snapshot.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("store", sa.String(length=8), nullable=False),
        sa.Column("uri", sa.String(length=1024), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=True),
        sa.Column("size_bytes", sa.Integer(), nullable=True),
        sa.Column("content_type", sa.String(length=128), nullable=True),
        sa.Column("retention", sa.String(length=16), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_artifact_task_kind", "artifact", ["task_id", "kind"])
    op.create_index("ix_artifact_retention", "artifact", ["retention"])
    op.create_index("ix_artifact_expires_at", "artifact", ["expires_at"])


def downgrade() -> None:
    op.drop_index("ix_artifact_expires_at", table_name="artifact")
    op.drop_index("ix_artifact_retention", table_name="artifact")
    op.drop_index("ix_artifact_task_kind", table_name="artifact")
    op.drop_table("artifact")

    op.drop_index("ix_file_language", table_name="repository_file")
    op.drop_index("ix_file_snapshot_is_test", table_name="repository_file")
    op.drop_index("ix_file_snapshot_path", table_name="repository_file")
    op.drop_table("repository_file")

    op.drop_index("ix_snapshot_status", table_name="repository_snapshot")
    op.drop_index("ix_snapshot_repository_id", table_name="repository_snapshot")
    op.drop_table("repository_snapshot")

    op.drop_index("ix_repository_name", table_name="repository")
    op.drop_table("repository")
