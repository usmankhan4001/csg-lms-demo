"""Merge all remaining branches into a single unified head

Revision ID: ff99a88b77c6
Create Date: 2026-09-17
"""
from typing import Sequence, Union

from alembic import op  # noqa: F401
import sqlalchemy as sa  # noqa: F401
import sqlmodel  # noqa: F401


# revision identifiers, used by Alembic.
revision: str = 'ff99a88b77c6'
down_revision: Union[str, Sequence[str], None] = (
    'c9d0e1f2a3b4',
)
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """No-op: a merge reconciles history, it does not change the schema."""
    pass


def downgrade() -> None:
    """No-op: un-merging would re-create the multi-head ambiguity."""
    pass
