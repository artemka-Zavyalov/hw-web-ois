"""add tags

Revision ID: 7f4b2c1d9a10
Revises: c9b2edd051a6
Create Date: 2026-11-20 14:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "7f4b2c1d9a10"
down_revision: Union[str, Sequence[str], None] = "c9b2edd051a6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tags",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.CheckConstraint("length(name) BETWEEN 1 AND 50", name="tags_name_check"),
        sa.PrimaryKeyConstraint("id", name="tags_pkey"),
        sa.UniqueConstraint("name", name="tags_name_key"),
    )

    op.create_table(
        "event_tags",
        sa.Column("event_id", sa.BigInteger(), nullable=False),
        sa.Column("tag_id", sa.BigInteger(), nullable=False),
        sa.ForeignKeyConstraint(
            ["event_id"],
            ["events.id"],
            name="event_tags_event_id_fkey",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["tag_id"],
            ["tags.id"],
            name="event_tags_tag_id_fkey",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "event_id",
            "tag_id",
            name="event_tags_pkey",
        ),
    )


def downgrade() -> None:
    op.drop_table("event_tags")
    op.drop_table("tags")
