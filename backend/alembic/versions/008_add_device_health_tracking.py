"""add device health tracking

Revision ID: 008
Revises: 007
Create Date: 2026-04-04 08:05:00
"""
from alembic import op
import sqlalchemy as sa

revision = '008'
down_revision = '007'
branch_labels = None
depends_on = None


def upgrade():
    # Add is_online field to track device connectivity status
    op.add_column('devices', sa.Column('is_online', sa.Boolean(), nullable=False, server_default='true'))
    
    # Add last_error field to store connection error details
    op.add_column('devices', sa.Column('last_error', sa.Text(), nullable=True))
    
    # Add consecutive_failures counter for triggering rescans
    op.add_column('devices', sa.Column('consecutive_failures', sa.Integer(), nullable=False, server_default='0'))


def downgrade():
    op.drop_column('devices', 'consecutive_failures')
    op.drop_column('devices', 'last_error')
    op.drop_column('devices', 'is_online')
