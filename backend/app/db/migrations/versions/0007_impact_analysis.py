"""impact analysis table (impact_analysis)

Revision ID: 0007
Revises: 0006
Create Date: 2026-09-06

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0007"
down_revision: Union[str, None] = "0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "impact_analysis",
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
        sa.Column("changed_set", sa.JSON(), nullable=False),
        sa.Column("blast_radius", sa.JSON(), nullable=False),
        sa.Column("callers", sa.JSON(), nullable=False),
        sa.Column("related_tests", sa.JSON(), nullable=False),
        sa.Column("public_api_touched", sa.JSON(), nullable=False),
        sa.Column("config_refs", sa.JSON(), nullable=False),
        sa.Column("db_refs", sa.JSON(), nullable=False),
        sa.Column("regression_areas", sa.JSON(), nullable=False),
        sa.Column("risk_signal_bundle", sa.JSON(), nullable=False),
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
        sa.UniqueConstraint("task_id", name="uq_impact_analysis_task"),
    )
    op.create_index("ix_impact_analysis_task_id", "impact_analysis", ["task_id"])
    op.create_index(
        "ix_impact_analysis_snapshot_id", "impact_analysis", ["snapshot_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_impact_analysis_snapshot_id", table_name="impact_analysis")
    op.drop_index("ix_impact_analysis_task_id", table_name="impact_analysis")
    op.drop_table("impact_analysis")
