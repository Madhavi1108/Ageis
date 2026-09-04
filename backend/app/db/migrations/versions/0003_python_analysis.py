"""python analysis tables (repository_symbol, dependency, repository_analysis)

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-04

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "repository_symbol",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "snapshot_id",
            sa.String(length=36),
            sa.ForeignKey("repository_snapshot.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "file_id",
            sa.String(length=36),
            sa.ForeignKey("repository_file.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("symbol_id", sa.String(length=1536), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("qualname", sa.String(length=1024), nullable=False),
        sa.Column("signature", sa.String(length=2048), nullable=True),
        sa.Column("lineno", sa.Integer(), nullable=False),
        sa.Column("end_lineno", sa.Integer(), nullable=False),
        sa.Column("decorators", sa.JSON(), nullable=True),
        sa.Column("docstring", sa.Text(), nullable=True),
        sa.Column("is_exported", sa.Boolean(), nullable=False),
        sa.UniqueConstraint(
            "snapshot_id", "symbol_id", name="uq_symbol_snapshot_symbolid"
        ),
    )
    op.create_index(
        "ix_symbol_snapshot_symbolid", "repository_symbol", ["snapshot_id", "symbol_id"]
    )
    op.create_index("ix_symbol_file_id", "repository_symbol", ["file_id"])
    op.create_index(
        "ix_symbol_snapshot_kind", "repository_symbol", ["snapshot_id", "kind"]
    )

    op.create_table(
        "dependency",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "snapshot_id",
            sa.String(length=36),
            sa.ForeignKey("repository_snapshot.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column(
            "from_file_id",
            sa.String(length=36),
            sa.ForeignKey("repository_file.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("target", sa.String(length=255), nullable=False),
        sa.Column("classification", sa.String(length=16), nullable=False),
        sa.Column("version_spec", sa.String(length=128), nullable=True),
        sa.Column("extras", sa.JSON(), nullable=True),
    )
    op.create_index(
        "ix_dependency_snapshot_classification",
        "dependency",
        ["snapshot_id", "classification"],
    )
    op.create_index("ix_dependency_from_file_id", "dependency", ["from_file_id"])

    op.create_table(
        "repository_analysis",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "snapshot_id",
            sa.String(length=36),
            sa.ForeignKey("repository_snapshot.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("entry_points", sa.JSON(), nullable=True),
        sa.Column("test_framework", sa.String(length=64), nullable=True),
        sa.Column("test_command", sa.String(length=512), nullable=True),
        sa.Column("package_manager", sa.String(length=32), nullable=True),
        sa.Column("build_backend", sa.String(length=128), nullable=True),
        sa.Column(
            "graph_artifact_id",
            sa.String(length=36),
            sa.ForeignKey("artifact.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("summary", sa.JSON(), nullable=True),
        sa.Column("unknowns", sa.JSON(), nullable=True),
        sa.Column("analysed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("duration_ms", sa.Integer(), nullable=False),
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


def downgrade() -> None:
    op.drop_table("repository_analysis")

    op.drop_index("ix_dependency_from_file_id", table_name="dependency")
    op.drop_index("ix_dependency_snapshot_classification", table_name="dependency")
    op.drop_table("dependency")

    op.drop_index("ix_symbol_snapshot_kind", table_name="repository_symbol")
    op.drop_index("ix_symbol_file_id", table_name="repository_symbol")
    op.drop_index("ix_symbol_snapshot_symbolid", table_name="repository_symbol")
    op.drop_table("repository_symbol")
