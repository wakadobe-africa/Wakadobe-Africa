"""add comment parent_id

Revision ID: d3fb2a799642
Revises: 94d44a04e624
Create Date: 2026-05-31 08:41:45.872241

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd3fb2a799642'
down_revision = '94d44a04e624'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('comment', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column('parent_id', sa.Integer(), sa.ForeignKey('comment.id', ondelete='CASCADE'), nullable=True)
        )
        batch_op.create_index(batch_op.f('ix_comment_parent_id'), ['parent_id'], unique=False)


def downgrade():
    with op.batch_alter_table('comment', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_comment_parent_id'))
        batch_op.drop_column('parent_id')
