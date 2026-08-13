"""Add YouTube OAuth connection foundation.

Revision ID: 20260813_0014
Revises: 20260813_0013
Create Date: 2026-08-13
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260813_0014"
down_revision: str | None = "20260813_0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "publishing_connections",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("provider", sa.String(length=100), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "PENDING",
                "CONNECTED",
                "FAILED",
                "DISCONNECTED",
                name="publishingconnectionstatus",
            ),
            nullable=False,
        ),
        sa.Column("scopes", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("account_id", sa.String(length=255), nullable=True),
        sa.Column("account_name", sa.String(length=255), nullable=True),
        sa.Column("error_code", sa.String(length=100), nullable=True),
        sa.Column("error_message", sa.String(length=1000), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("connected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("disconnected_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_publishing_connections_provider", "publishing_connections", ["provider"])
    op.create_table(
        "publishing_credentials",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("connection_id", sa.Uuid(), nullable=False),
        sa.Column("encrypted_refresh_token", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["connection_id"], ["publishing_connections.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_publishing_credentials_connection_id",
        "publishing_credentials",
        ["connection_id"],
        unique=True,
    )
    op.create_table(
        "publishing_oauth_states",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("connection_id", sa.Uuid(), nullable=False),
        sa.Column("state_digest", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["connection_id"], ["publishing_connections.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_publishing_oauth_states_connection_id",
        "publishing_oauth_states",
        ["connection_id"],
    )
    op.create_index(
        "ix_publishing_oauth_states_state_digest",
        "publishing_oauth_states",
        ["state_digest"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_publishing_oauth_states_state_digest", table_name="publishing_oauth_states")
    op.drop_index("ix_publishing_oauth_states_connection_id", table_name="publishing_oauth_states")
    op.drop_table("publishing_oauth_states")
    op.drop_index("ix_publishing_credentials_connection_id", table_name="publishing_credentials")
    op.drop_table("publishing_credentials")
    op.drop_index("ix_publishing_connections_provider", table_name="publishing_connections")
    op.drop_table("publishing_connections")
    op.execute("DROP TYPE publishingconnectionstatus")
