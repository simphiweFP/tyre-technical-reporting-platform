"""Store report image content as Base64 in the database."""

import sqlalchemy as sa
from alembic import op

revision = "20260927_07"
down_revision = "20260924_06"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("report_images") as batch:
        batch.add_column(sa.Column("base64_data", sa.Text(), nullable=True))

    # Existing filesystem-backed rows cannot be safely copied into the database
    # from a schema migration. Keep the migration deterministic and require old
    # development images to be re-uploaded after this storage change.
    op.execute("UPDATE report_images SET base64_data = '' WHERE base64_data IS NULL")

    with op.batch_alter_table("report_images") as batch:
        batch.alter_column(
            "base64_data",
            existing_type=sa.Text(),
            nullable=False,
        )
        batch.drop_column("file_path")


def downgrade() -> None:
    with op.batch_alter_table("report_images") as batch:
        batch.add_column(sa.Column("file_path", sa.String(length=500), nullable=True))

    connection = op.get_bind()
    rows = connection.execute(sa.text("SELECT id FROM report_images")).fetchall()
    for row in rows:
        connection.execute(
            sa.text(
                "UPDATE report_images SET file_path = :file_path WHERE id = :image_id"
            ),
            {
                "file_path": f"database-image-{row[0]}",
                "image_id": row[0],
            },
        )

    with op.batch_alter_table("report_images") as batch:
        batch.alter_column(
            "file_path",
            existing_type=sa.String(length=500),
            nullable=False,
        )
        batch.drop_column("base64_data")
