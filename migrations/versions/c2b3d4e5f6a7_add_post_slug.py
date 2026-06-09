"""add post slug

Revision ID: c2b3d4e5f6a7
Revises: b1a2c3d4e5f7
Create Date: 2026-05-31 10:00:00.000000
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c2b3d4e5f6a7'
down_revision = 'b1a2c3d4e5f7'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('post', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column('slug', sa.String(length=250), nullable=True)
        )
        batch_op.create_index(batch_op.f('ix_post_slug'), ['slug'], unique=False)

    # Backfill slug with default values for existing posts
    conn = op.get_bind()
    conn.execute(
        sa.text(
            "UPDATE post SET slug = LOWER(CONCAT(REPLACE(REPLACE(REPLACE(title, ' ', '-'), '.', ''), '/', '-'), '-draft')) WHERE slug IS NULL"
        )
    )

    # Make slug non-nullable after backfill
    with op.batch_alter_table('post', schema=None) as batch_op:
        batch_op.alter_column(
            'slug',
            existing_type=sa.String(length=250),
            nullable=False,
            existing_nullable=True,
        )


def downgrade():
    with op.batch_alter_table('post', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_post_slug'))
        batch_op.drop_column('slug')
