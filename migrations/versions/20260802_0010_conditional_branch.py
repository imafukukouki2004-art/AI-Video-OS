"""Add conditional branch fields to WorkflowStep

Revision ID: 20260802_0010
Revises: 20260802_0009
Create Date: 2026-08-03 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260802_0010"
down_revision: str | None = "20260802_0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Add columns to workflow_steps table
    op.add_column("workflow_steps", sa.Column("condition", sa.String(length=500), nullable=True))
    op.add_column("workflow_steps", sa.Column("next_step_on_true", sa.UUID(), nullable=True))
    op.add_column("workflow_steps", sa.Column("next_step_on_false", sa.UUID(), nullable=True))

    # Add foreign key constraints
    op.create_foreign_key(
        "fk_workflow_steps_next_true",
        "workflow_steps",
        "workflow_steps",
        ["next_step_on_true"],
        ["id"],
    )
    op.create_foreign_key(
        "fk_workflow_steps_next_false",
        "workflow_steps",
        "workflow_steps",
        ["next_step_on_false"],
        ["id"],
    )


def downgrade() -> None:
    # Remove foreign key constraints
    op.drop_constraint("fk_workflow_steps_next_false", "workflow_steps", type_="foreignkey")
    op.drop_constraint("fk_workflow_steps_next_true", "workflow_steps", type_="foreignkey")

    # Remove columns
    op.drop_column("workflow_steps", "next_step_on_false")
    op.drop_column("workflow_steps", "next_step_on_true")
    op.drop_column("workflow_steps", "condition")
