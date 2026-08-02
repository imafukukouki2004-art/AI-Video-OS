"""Workflow step model foundation.

Revision ID: 20260802_0005
Revises: 20260802_0004
Create Date: 2026-08-02 14:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260802_0005"
down_revision: str | None = "20260802_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Create workflow_step_status enum if not exists
    op.execute(
        "DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'workflowstepstatus') "
        "THEN CREATE TYPE workflowstepstatus AS ENUM "
        "('pending', 'running', 'completed', 'failed'); "
        "END IF; END $$;"
    )

    # Create workflow_steps table
    op.create_table(
        "workflow_steps",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("workflow_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("step_type", sa.String(length=100), nullable=False),
        sa.Column("order", sa.Integer(), nullable=False),
        sa.Column("config", sa.dialects.postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "status",
            sa.Enum("PENDING", "RUNNING", "COMPLETED", "FAILED", name="workflowstepstatus"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["workflow_id"], ["workflows.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    # Add step_id to jobs table
    op.add_column("jobs", sa.Column("step_id", sa.UUID(), nullable=True))
    op.create_foreign_key(
        "fk_jobs_step_id_workflow_steps",
        "jobs",
        "workflow_steps",
        ["step_id"],
        ["id"],
    )


def downgrade() -> None:
    # Remove step_id from jobs table
    op.drop_constraint("fk_jobs_step_id_workflow_steps", "jobs", type_="foreignkey")
    op.drop_column("jobs", "step_id")

    # Drop workflow_steps table
    op.drop_table("workflow_steps")

    # Drop workflow_step_status enum
    op.execute("DROP TYPE workflowstepstatus")
