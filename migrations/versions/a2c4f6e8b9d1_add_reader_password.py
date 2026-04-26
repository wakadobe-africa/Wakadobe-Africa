"""add reader password

Revision ID: a2c4f6e8b9d1
Revises: 7b8c9d0e1f2a
Create Date: 2026-04-19 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "a2c4f6e8b9d1"
down_revision = "7b8c9d0e1f2a"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("reader", schema=None) as batch_op:
        batch_op.add_column(sa.Column("password", sa.String(length=255), nullable=True))


def downgrade():
    with op.batch_alter_table("reader", schema=None) as batch_op:
        batch_op.drop_column("password")
