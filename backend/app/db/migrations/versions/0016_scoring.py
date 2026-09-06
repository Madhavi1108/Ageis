"""risk_assessment + repository_health tables

Revision ID: 0016
Revises: 0015
Create Date: 2026-09-06

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0016"
down_revision: Union[str, None] = "0015"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "risk_assessment",
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
        sa.Column("implementation_version", sa.Integer(), nullable=False),
        sa.Column(
            "patch_id",
            sa.String(length=36),
            sa.ForeignKey("patch.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("pcs_value", sa.Integer(), nullable=False),
        sa.Column("pcs_classification", sa.String(length=16), nullable=False),
        sa.Column("pcs_breakdown", sa.JSON(), nullable=False),
        sa.Column("crs_value", sa.Integer(), nullable=False),
        sa.Column("crs_classification", sa.String(length=16), nullable=False),
        sa.Column("crs_breakdown", sa.JSON(), nullable=False),
        sa.Column("task_risk_profile", sa.JSON(), nullable=False),
        sa.Column("hard_gate", sa.JSON(), nullable=True),
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
        sa.UniqueConstraint("task_id", name="uq_risk_assessment_task"),
    )
    op.create_index(
        "ix_risk_assessment_task_id", "risk_assessment", ["task_id"]
    )
    op.create_index(
        "ix_risk_assessment_patch_id", "risk_assessment", ["patch_id"]
    )

    op.create_table(
        "repository_health",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "snapshot_id",
            sa.String(length=36),
            sa.ForeignKey("repository_snapshot.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("repository_id", sa.String(length=36), nullable=False),
        sa.Column("rhp_value", sa.Integer(), nullable=False),
        sa.Column("rhp_classification", sa.String(length=16), nullable=False),
        sa.Column("subscores", sa.JSON(), nullable=False),
        sa.Column("risky_modules", sa.JSON(), nullable=False),
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
        sa.UniqueConstraint(
            "snapshot_id", name="uq_repository_health_snapshot"
        ),
    )
    op.create_index(
        "ix_repository_health_snapshot_id", "repository_health", ["snapshot_id"]
    )
    op.create_index(
        "ix_repository_health_repository_id", "repository_health", ["repository_id"]
    )


def downgrade() -> None:
    op.drop_index(
        "ix_repository_health_repository_id", table_name="repository_health"
    )
    op.drop_index(
        "ix_repository_health_snapshot_id", table_name="repository_health"
    )
    op.drop_table("repository_health")
    op.drop_index("ix_risk_assessment_patch_id", table_name="risk_assessment")
    op.drop_index("ix_risk_assessment_task_id", table_name="risk_assessment")
    op.drop_table("risk_assessment")
