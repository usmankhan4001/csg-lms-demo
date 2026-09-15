"""merge cognia and ems rbac migration heads

Revision ID: f9a0b1c2d3e4
Create Date: 2026-09-15
"""
from typing import Sequence, Union

from alembic import op  # noqa: F401
import sqlalchemy as sa  # noqa: F401
import sqlmodel  # noqa: F401


# revision identifiers, used by Alembic.
revision: str = 'f9a0b1c2d3e4'
down_revision: Union[str, Sequence[str], None] = (
    'c4f81a7d2e93',
    'e8f9a0b1c2d3',
)
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """No-op: a merge reconciles history, it does not change the schema."""
    pass


def downgrade() -> None:
    """No-op: un-merging would re-create the multi-head ambiguity."""
    pass
