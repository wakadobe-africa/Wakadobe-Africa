"""make reader password non-nullable

Revision ID: e0a7c3d4b5f6
Revises: d3fb2a799642
Create Date: 2026-05-31 09:10:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import text


# revision identifiers, used by Alembic.
revision = 'e0a7c3d4b5f6'
down_revision = 'd3fb2a799642'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    result = conn.execute(text("SELECT COUNT(*) FROM reader WHERE password IS NULL"))
    null_count = result.scalar()
    if null_count and null_count > 0:
        from alembic import op
        import sqlalchemy as sa
        from sqlalchemy.sql import text
        import uuid
        from werkzeug.security import generate_password_hash


        # revision identifiers, used by Alembic.
        revision = 'e0a7c3d4b5f6'
        down_revision = 'd3fb2a799642'
        branch_labels = None
        depends_on = None


        def upgrade():
            conn = op.get_bind()

            # Backfill NULL passwords with a securely-generated random password hash.
            rows = conn.execute(text("SELECT id FROM reader WHERE password IS NULL")).fetchall()
            for row in rows:
                temp_pw = uuid.uuid4().hex
                pw_hash = generate_password_hash(temp_pw)
                conn.execute(
                    text("UPDATE reader SET password = :pw WHERE id = :id"),
                    {"pw": pw_hash, "id": row[0]},
                )

            # Verify no NULLs remain
            result = conn.execute(text("SELECT COUNT(*) FROM reader WHERE password IS NULL"))
            null_count = result.scalar()
            if null_count and null_count > 0:
                raise RuntimeError(
                    f"Cannot make reader.password non-nullable: {null_count} rows still have NULL password after backfill"
                )

            with op.batch_alter_table('reader', schema=None) as batch_op:
                batch_op.alter_column(
                    'password',
                    existing_type=sa.String(length=255),
                    nullable=False,
                    existing_nullable=True,
                )


        def downgrade():
            with op.batch_alter_table('reader', schema=None) as batch_op:
                batch_op.alter_column(
                    'password',
                    existing_type=sa.String(length=255),
                    nullable=True,
                    existing_nullable=False,
                )
