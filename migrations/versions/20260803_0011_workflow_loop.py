"""Add loop fields to WorkflowStep

Revision ID: 20260803_0011
Revises: 20260802_0010
Create Date: 2026-08-03 15:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260803_0011"
down_revision: str | None = "20260802_0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Add loop_source and loop_variable columns to workflow_steps table
    op.add_column("workflow_steps", sa.Column("loop_source", sa.String(length=500), nullable=True))
    op.add_column(
        "workflow_steps", sa.Column("loop_variable", sa.String(length=100), nullable=True)
    )


def downgrade() -> None:
    # Remove loop columns
    op.drop_column("workflow_steps", "loop_variable")
    op.drop_column("workflow_steps", "loop_source")
