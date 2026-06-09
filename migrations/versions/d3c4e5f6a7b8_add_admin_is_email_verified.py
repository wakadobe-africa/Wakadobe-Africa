"""add admin is_email_verified

Revision ID: d3c4e5f6a7b8
Revises: c2b3d4e5f6a7
Create Date: 2026-05-31 10:15:00.000000
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd3c4e5f6a7b8'
down_revision = 'c2b3d4e5f6a7'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('admin', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column('is_email_verified', sa.Boolean(), nullable=True, server_default=sa.text('FALSE'))
        )


def downgrade():
    with op.batch_alter_table('admin', schema=None) as batch_op:
        batch_op.drop_column('is_email_verified')
