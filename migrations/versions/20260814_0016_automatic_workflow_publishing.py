"""Link automatic publications to workflow executions.

Revision ID: 20260814_0016
Revises: 20260813_0015
Create Date: 2026-08-14
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260814_0016"
down_revision: str | None = "20260813_0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("publications", sa.Column("workflow_execution_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "fk_publications_workflow_execution_id",
        "publications",
        "workflow_executions",
        ["workflow_execution_id"],
        ["id"],
    )
    op.create_index(
        "ix_publications_workflow_execution_id",
        "publications",
        ["workflow_execution_id"],
    )
    op.create_unique_constraint(
        "uq_publications_auto_workflow_provider_asset",
        "publications",
        ["workflow_execution_id", "provider", "asset_id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_publications_auto_workflow_provider_asset",
        "publications",
        type_="unique",
    )
    op.drop_index("ix_publications_workflow_execution_id", table_name="publications")
    op.drop_constraint(
        "fk_publications_workflow_execution_id",
        "publications",
        type_="foreignkey",
    )
    op.drop_column("publications", "workflow_execution_id")
