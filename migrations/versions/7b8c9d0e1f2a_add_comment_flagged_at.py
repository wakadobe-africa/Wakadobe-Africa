"""add comment flagged_at

Revision ID: 7b8c9d0e1f2a
Revises: efb5c68c1685
Create Date: 2026-04-17 12:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '7b8c9d0e1f2a'
down_revision = 'efb5c68c1685'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('comment', schema=None) as batch_op:
        batch_op.add_column(sa.Column('flagged_at', sa.DateTime(), nullable=True))
        batch_op.create_index(batch_op.f('ix_comment_flagged_at'), ['flagged_at'], unique=False)


def downgrade():
    with op.batch_alter_table('comment', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_comment_flagged_at'))
        batch_op.drop_column('flagged_at')