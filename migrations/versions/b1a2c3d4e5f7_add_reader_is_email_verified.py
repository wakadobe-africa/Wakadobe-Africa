"""add reader is_email_verified

Revision ID: b1a2c3d4e5f7
Revises: e0a7c3d4b5f6
Create Date: 2026-05-31 09:40:00.000000
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b1a2c3d4e5f7'
down_revision = 'e0a7c3d4b5f6'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('reader', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column('is_email_verified', sa.Boolean(), nullable=True, server_default=sa.text('FALSE'))
        )
        batch_op.create_index(batch_op.f('ix_reader_is_email_verified'), ['is_email_verified'], unique=False)


def downgrade():
    with op.batch_alter_table('reader', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_reader_is_email_verified'))
        batch_op.drop_column('is_email_verified')
