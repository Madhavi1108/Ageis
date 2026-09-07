"""orchestration: task.cancel_requested + job claim index

Revision ID: 0020
Revises: 0019
Create Date: 2026-09-07

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0020"
down_revision: Union[str, None] = "0019"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "task",
        sa.Column(
            "cancel_requested",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.create_index("ix_job_state_queued_at", "job", ["state", "queued_at"])


def downgrade() -> None:
    op.drop_index("ix_job_state_queued_at", table_name="job")
    with op.batch_alter_table("task") as batch:
        batch.drop_column("cancel_requested")
