"""Workflow execution state management foundation.

Revision ID: 20260802_0004
Revises: 20260802_0003
Create Date: 2026-08-02 13:30:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260802_0004"
down_revision: str | None = "20260802_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Create workflow_execution_status enum if not exists
    # In PostgreSQL, we can use a DO block to safely create the type
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'workflowexecutionstatus') THEN
                CREATE TYPE workflowexecutionstatus AS ENUM (
                    'PENDING', 'RUNNING', 'COMPLETED', 'FAILED'
                );
            END IF;
        END$$;
        """
    )

    # Create workflow_executions table
    op.create_table(
        "workflow_executions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("workflow_id", sa.UUID(), nullable=False),
        sa.Column(
            "status",
            sa.Enum("PENDING", "RUNNING", "COMPLETED", "FAILED", name="workflowexecutionstatus"),
            nullable=False,
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["workflow_id"], ["workflows.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    # Add execution_id to jobs table
    op.add_column("jobs", sa.Column("execution_id", sa.UUID(), nullable=True))
    op.create_foreign_key(
        "fk_jobs_execution_id_workflow_executions",
        "jobs",
        "workflow_executions",
        ["execution_id"],
        ["id"],
    )


def downgrade() -> None:
    # Remove execution_id from jobs table
    op.drop_constraint("fk_jobs_execution_id_workflow_executions", "jobs", type_="foreignkey")
    op.drop_column("jobs", "execution_id")

    # Drop workflow_executions table
    op.drop_table("workflow_executions")

    # Drop workflow_execution_status enum
    op.execute("DROP TYPE workflowexecutionstatus")
