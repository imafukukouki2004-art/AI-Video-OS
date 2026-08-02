"""Establish the PostgreSQL migration baseline.

Revision ID: 20260802_0001
Revises: None
Create Date: 2026-08-02
"""

from collections.abc import Sequence

revision: str = "20260802_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create no domain tables in the foundation ticket."""


def downgrade() -> None:
    """Remove no domain tables from the foundation baseline."""
