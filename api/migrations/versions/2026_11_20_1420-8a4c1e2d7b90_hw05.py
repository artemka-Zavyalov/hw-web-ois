"""homework 05 tables

Revision ID: 8a4c1e2d7b90
Revises: 7222c5e25ea9
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "8a4c1e2d7b90"
down_revision: Union[str, Sequence[str], None] = "7222c5e25ea9"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table(
        "login_attempts",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("email", sa.Text(), nullable=False),
        sa.Column("attempted_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("login_attempts_pkey")),
    )
    op.create_index(
        "login_attempts_email_attempted_at_idx",
        "login_attempts",
        ["email", "attempted_at"],
        unique=False,
    )

    op.create_table(
        "audit_log",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=True),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column("identity", sa.Text(), nullable=False),
        sa.Column("object_id", sa.Text(), nullable=True),
        sa.Column("changes", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("audit_log_user_id_fkey"), ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name=op.f("audit_log_pkey")),
    )
    op.create_index(op.f("audit_log_created_at_idx"), "audit_log", ["created_at"], unique=False)
    op.create_index(op.f("audit_log_user_id_idx"), "audit_log", ["user_id"], unique=False)

def downgrade() -> None:
    op.drop_index(op.f("audit_log_user_id_idx"), table_name="audit_log")
    op.drop_index(op.f("audit_log_created_at_idx"), table_name="audit_log")
    op.drop_table("audit_log")
    op.drop_index("login_attempts_email_attempted_at_idx", table_name="login_attempts")
    op.drop_table("login_attempts")
