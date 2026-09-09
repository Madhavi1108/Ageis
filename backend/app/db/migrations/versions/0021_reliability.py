"""reliability: job backoff/heartbeat + analysis limit_reason (Phase 27)

Revision ID: 0021
Revises: 0020
Create Date: 2026-09-08

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0021"
down_revision: Union[str, None] = "0020"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "job", sa.Column("run_after", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column(
        "job", sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.create_index("ix_job_run_after", "job", ["run_after"])
    op.add_column(
        "repository_analysis",
        sa.Column("limit_reason", sa.String(length=512), nullable=True),
    )


def downgrade() -> None:
    with op.batch_alter_table("repository_analysis") as batch:
        batch.drop_column("limit_reason")
    op.drop_index("ix_job_run_after", table_name="job")
    with op.batch_alter_table("job") as batch:
        batch.drop_column("heartbeat_at")
        batch.drop_column("run_after")
