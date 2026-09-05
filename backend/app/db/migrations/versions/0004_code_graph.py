"""code graph tables (graph_node, graph_edge)

Revision ID: 0004
Revises: 0003
Create Date: 2026-09-04

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "graph_node",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "snapshot_id",
            sa.String(length=36),
            sa.ForeignKey("repository_snapshot.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("node_type", sa.String(length=16), nullable=False),
        sa.Column("ref", sa.String(length=1536), nullable=False),
        sa.Column("label", sa.String(length=1536), nullable=False),
        sa.Column("extra", sa.JSON(), nullable=True),
        sa.UniqueConstraint("snapshot_id", "ref", name="uq_graph_node_snapshot_ref"),
    )
    op.create_index(
        "ix_graph_node_snapshot_type", "graph_node", ["snapshot_id", "node_type"]
    )
    op.create_index(
        "ix_graph_node_snapshot_ref", "graph_node", ["snapshot_id", "ref"]
    )

    op.create_table(
        "graph_edge",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "snapshot_id",
            sa.String(length=36),
            sa.ForeignKey("repository_snapshot.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("edge_type", sa.String(length=16), nullable=False),
        sa.Column(
            "source_node_id",
            sa.String(length=36),
            sa.ForeignKey("graph_node.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "target_node_id",
            sa.String(length=36),
            sa.ForeignKey("graph_node.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("confidence", sa.String(length=16), nullable=True),
        sa.Column("evidence", sa.JSON(), nullable=True),
    )
    op.create_index(
        "ix_graph_edge_snapshot_type", "graph_edge", ["snapshot_id", "edge_type"]
    )
    op.create_index("ix_graph_edge_source", "graph_edge", ["source_node_id"])
    op.create_index("ix_graph_edge_target", "graph_edge", ["target_node_id"])


def downgrade() -> None:
    op.drop_index("ix_graph_edge_target", table_name="graph_edge")
    op.drop_index("ix_graph_edge_source", table_name="graph_edge")
    op.drop_index("ix_graph_edge_snapshot_type", table_name="graph_edge")
    op.drop_table("graph_edge")

    op.drop_index("ix_graph_node_snapshot_ref", table_name="graph_node")
    op.drop_index("ix_graph_node_snapshot_type", table_name="graph_node")
    op.drop_table("graph_node")
