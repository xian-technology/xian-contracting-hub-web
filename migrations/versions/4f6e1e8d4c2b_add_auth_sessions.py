"""add auth sessions

Revision ID: 4f6e1e8d4c2b
Revises: d0f4c4b9a972
Create Date: 2026-03-09 18:40:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
import sqlmodel
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "4f6e1e8d4c2b"
down_revision: Union[str, Sequence[str], None] = "d0f4c4b9a972"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "auth_sessions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column(
            "session_token_hash",
            sqlmodel.sql.sqltypes.AutoString(length=64),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "session_token_hash",
            name="uq_auth_sessions_session_token_hash",
        ),
    )
    with op.batch_alter_table("auth_sessions", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_auth_sessions_created_at"), ["created_at"], unique=False
        )
        batch_op.create_index(
            batch_op.f("ix_auth_sessions_expires_at"), ["expires_at"], unique=False
        )
        batch_op.create_index(
            batch_op.f("ix_auth_sessions_session_token_hash"),
            ["session_token_hash"],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f("ix_auth_sessions_updated_at"), ["updated_at"], unique=False
        )
        batch_op.create_index(batch_op.f("ix_auth_sessions_user_id"), ["user_id"], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("auth_sessions", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_auth_sessions_user_id"))
        batch_op.drop_index(batch_op.f("ix_auth_sessions_updated_at"))
        batch_op.drop_index(batch_op.f("ix_auth_sessions_session_token_hash"))
        batch_op.drop_index(batch_op.f("ix_auth_sessions_expires_at"))
        batch_op.drop_index(batch_op.f("ix_auth_sessions_created_at"))

    op.drop_table("auth_sessions")
