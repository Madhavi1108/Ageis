"""verification table

Revision ID: 0017
Revises: 0016
Create Date: 2026-09-07

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0017"
down_revision: Union[str, None] = "0016"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "verification",
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
        sa.Column("verdict", sa.String(length=16), nullable=False),
        sa.Column("criteria", sa.JSON(), nullable=False),
        sa.Column("plan_alignment", sa.JSON(), nullable=False),
        sa.Column("trace", sa.JSON(), nullable=False),
        sa.Column(
            "trace_artifact_id",
            sa.String(length=36),
            sa.ForeignKey("artifact.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column("replay_fidelity", sa.Float(), nullable=True),
        sa.Column("confidence", sa.JSON(), nullable=False),
        sa.Column("resulting_state", sa.String(length=24), nullable=False),
        sa.Column("decision", sa.JSON(), nullable=True),
        sa.Column("model_version", sa.String(length=32), nullable=False),
        sa.Column(
            "superseded_by",
            sa.String(length=36),
            sa.ForeignKey("verification.id", ondelete="SET NULL"),
            nullable=True,
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
    op.create_index("ix_verification_task_id", "verification", ["task_id"])
    op.create_index(
        "ix_verification_superseded_by", "verification", ["superseded_by"]
    )


def downgrade() -> None:
    op.drop_index("ix_verification_superseded_by", table_name="verification")
    op.drop_index("ix_verification_task_id", table_name="verification")
    op.drop_table("verification")
