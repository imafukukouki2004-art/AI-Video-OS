"""Workflow execution history foundation.

Revision ID: 20260802_0006
Revises: 20260802_0005
Create Date: 2026-08-02 14:15:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260802_0006"
down_revision: str | None = "20260802_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Create workflow_execution_history table
    op.create_table(
        "workflow_execution_history",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("workflow_execution_id", sa.UUID(), nullable=False),
        sa.Column("workflow_step_id", sa.UUID(), nullable=True),
        sa.Column("from_status", sa.String(length=50), nullable=False),
        sa.Column("to_status", sa.String(length=50), nullable=False),
        sa.Column("message", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["workflow_execution_id"], ["workflow_executions.id"]),
        sa.ForeignKeyConstraint(["workflow_step_id"], ["workflow_steps.id"]),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    # Drop workflow_execution_history table
    op.drop_table("workflow_execution_history")
