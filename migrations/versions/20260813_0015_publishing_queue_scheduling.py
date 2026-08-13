"""Add publishing queue and scheduling state.

Revision ID: 20260813_0015
Revises: 20260813_0014
Create Date: 2026-08-13
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260813_0015"
down_revision: str | None = "20260813_0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TYPE publicationstatus ADD VALUE IF NOT EXISTS 'QUEUED' BEFORE 'PUBLISHING'")
    op.add_column("publications", sa.Column("scheduled_at", sa.DateTime(timezone=True)))
    op.add_column("publications", sa.Column("queued_at", sa.DateTime(timezone=True)))
    op.add_column("publications", sa.Column("started_at", sa.DateTime(timezone=True)))
    op.add_column("publications", sa.Column("task_id", sa.String(length=255)))


def downgrade() -> None:
    op.drop_column("publications", "task_id")
    op.drop_column("publications", "started_at")
    op.drop_column("publications", "queued_at")
    op.drop_column("publications", "scheduled_at")
    op.execute("UPDATE publications SET status = 'PENDING' WHERE status = 'QUEUED'")
    op.execute("ALTER TABLE publications ALTER COLUMN status TYPE VARCHAR(50) USING status::text")
    op.execute("DROP TYPE publicationstatus")
    op.execute(
        "CREATE TYPE publicationstatus AS ENUM ('PENDING', 'PUBLISHING', 'PUBLISHED', 'FAILED')"
    )
    op.execute(
        "ALTER TABLE publications ALTER COLUMN status TYPE publicationstatus "
        "USING status::publicationstatus"
    )
