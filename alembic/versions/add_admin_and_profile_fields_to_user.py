"""Add admin and profile fields to User model

Revision ID: add_admin_profile_fields
Revises: 1207b06d8194
Create Date: 2024-01-01 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_admin_profile_fields'
down_revision = '1207b06d8194'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add new columns to user table
    op.add_column('user', sa.Column('first_name', sa.String(length=100), nullable=True))
    op.add_column('user', sa.Column('last_name', sa.String(length=100), nullable=True))
    op.add_column('user', sa.Column('user_metadata', sa.JSON(), nullable=True, server_default='{}'))
    op.add_column('user', sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'))
    op.add_column('user', sa.Column('is_admin', sa.Boolean(), nullable=False, server_default='false'))


def downgrade() -> None:
    # Remove added columns
    op.drop_column('user', 'is_admin')
    op.drop_column('user', 'is_active')
    op.drop_column('user', 'user_metadata')
    op.drop_column('user', 'last_name')
    op.drop_column('user', 'first_name')