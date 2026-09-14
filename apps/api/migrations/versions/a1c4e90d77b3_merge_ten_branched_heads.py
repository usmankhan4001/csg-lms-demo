"""merge ten branched migration heads into one

`alembic upgrade head` has been FAILING in this project with "Multiple head
revisions are present for given argument 'head'" -- the version history had
branched into ten independent heads, so Alembic could not decide what "head"
meant and refused to do anything.

The container entrypoint runs `alembic upgrade head` at every startup and
swallows the failure, so this was invisible: the schema you see was built
entirely by `SQLModel.metadata.create_all`, not by migrations. Note that
`alembic_version` does not exist in the dev database at time of writing --
Alembic has never successfully completed here.

This is a pure bookkeeping merge: it runs no DDL. It only tells Alembic that
these ten lineages are reconciled, so `head` resolves to a single revision
again and future migrations can chain off it normally.

It does NOT by itself make migrations runnable against a database whose
schema came from create_all -- that needs a baseline (`alembic stamp`) so
Alembic stops trying to replay 69 revisions from scratch against tables that
already exist. That decision is deliberately left to a human, because
stamping asserts "the schema already matches these revisions", and any
migration that performed a data transformation rather than a pure schema
change would be silently skipped by it.

Revision ID: a1c4e90d77b3
Create Date: 2026-09-13

"""
from typing import Sequence, Union

from alembic import op  # noqa: F401
import sqlalchemy as sa  # noqa: F401
import sqlmodel  # noqa: F401


# revision identifiers, used by Alembic.
revision: str = 'a1c4e90d77b3'
down_revision: Union[str, Sequence[str], None] = (
    '5e3a9c7f1b2d',
    'a2b3c4d5e6f7',
    'b1c2d3e4f5a6',
    'b8c9d0e1f2a3',
    'c1d2e3f4a5b6',
    'd3e4f5a6b7c8',
    'd4e5f6a7b8c9',
    'm3b4c5d6e7f8',
    'n4o5p6q7r8s9',
    'u9v8w7x6y5z4',
)
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """No-op: a merge reconciles history, it does not change the schema."""
    pass


def downgrade() -> None:
    """No-op: un-merging would re-create the ten-head ambiguity this fixes."""
    pass
