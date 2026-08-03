"""Queue integration foundation

Revision ID: 20260802_0009
Revises: 20260802_0008
Create Date: 2026-08-03 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '20260802_0009'
down_revision = '20260802_0008'
branch_labels = None
depends_on = None

def upgrade() -> None:
    # Add task_id to jobs table
    op.add_column('jobs', sa.Column('task_id', sa.String(length=255), nullable=True))
    # Add task_id to workflow_executions table
    op.add_column('workflow_executions', sa.Column('task_id', sa.String(length=255), nullable=True))

def downgrade() -> None:
    # Remove task_id from workflow_executions table
    op.drop_column('workflow_executions', 'task_id')
    # Remove task_id from jobs table
    op.drop_column('jobs', 'task_id')
