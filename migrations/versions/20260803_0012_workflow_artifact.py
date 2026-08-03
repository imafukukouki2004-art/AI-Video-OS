"""Add workflow artifact foundation.

Revision ID: 20260803_0012
Revises: 20260803_0011
Create Date: 2026-08-03

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260803_0012"
down_revision: str | None = "20260803_0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "workflow_artifacts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workflow_execution_id", sa.Uuid(), nullable=False),
        sa.Column("workflow_step_id", sa.Uuid(), nullable=True),
        sa.Column("artifact_type", sa.String(length=100), nullable=False),
        sa.Column("asset_id", sa.Uuid(), nullable=True),
        sa.Column("metadata_data", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["asset_id"], ["assets.id"]),
        sa.ForeignKeyConstraint(["workflow_execution_id"], ["workflow_executions.id"]),
        sa.ForeignKeyConstraint(["workflow_step_id"], ["workflow_steps.id"]),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("workflow_artifacts")
