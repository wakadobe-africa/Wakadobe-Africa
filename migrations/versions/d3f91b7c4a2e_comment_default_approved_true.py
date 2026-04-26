"""set comment default approval to true

Revision ID: d3f91b7c4a2e
Revises: 7b8c9d0e1f2a
Create Date: 2026-04-20 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd3f91b7c4a2e'
down_revision = '7b8c9d0e1f2a'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('comment', schema=None) as batch_op:
        batch_op.alter_column(
            'is_approved',
            existing_type=sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        )

    op.execute(
        sa.text(
            "UPDATE comment "
            "SET is_approved = TRUE "
            "WHERE flagged_at IS NULL AND (is_approved IS NULL OR is_approved = FALSE)"
        )
    )


def downgrade():
    op.execute(
        sa.text(
            "UPDATE comment "
            "SET is_approved = FALSE "
            "WHERE flagged_at IS NULL AND is_approved = TRUE"
        )
    )

    with op.batch_alter_table('comment', schema=None) as batch_op:
        batch_op.alter_column(
            'is_approved',
            existing_type=sa.Boolean(),
            nullable=True,
            server_default=None,
        )