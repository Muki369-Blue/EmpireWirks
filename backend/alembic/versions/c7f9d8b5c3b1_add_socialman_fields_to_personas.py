"""add socialman persona fields

Revision ID: c7f9d8b5c3b1
Revises: a3c8f4e91d01
Create Date: 2026-04-20 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "c7f9d8b5c3b1"
down_revision = "a3c8f4e91d01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("personas", sa.Column("socialman_token", sa.Text(), nullable=True))
    op.add_column("personas", sa.Column("socialman_enabled", sa.Boolean(), nullable=False, server_default=sa.text("0")))
    op.add_column("personas", sa.Column("socialman_platforms", sa.JSON(), nullable=True))
    op.add_column("personas", sa.Column("socialman_title_template", sa.Text(), nullable=True))
    op.add_column("personas", sa.Column("socialman_description_template", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("personas", "socialman_description_template")
    op.drop_column("personas", "socialman_title_template")
    op.drop_column("personas", "socialman_platforms")
    op.drop_column("personas", "socialman_enabled")
    op.drop_column("personas", "socialman_token")