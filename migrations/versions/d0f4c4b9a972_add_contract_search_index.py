"""add contract search index

Revision ID: d0f4c4b9a972
Revises: 9db45bd4585d
Create Date: 2026-03-09 13:05:00.000000

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d0f4c4b9a972"
down_revision: Union[str, Sequence[str], None] = "9db45bd4585d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute(
        """
        CREATE VIRTUAL TABLE contract_search_index USING fts5(
            slug,
            contract_name,
            display_name,
            short_summary,
            long_description,
            author_text,
            category_text,
            tags_text,
            source_text,
            tokenize = 'unicode61'
        )
        """
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("DROP TABLE IF EXISTS contract_search_index")
