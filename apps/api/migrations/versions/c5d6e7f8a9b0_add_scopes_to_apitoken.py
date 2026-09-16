"""Add scopes JSON column to apitoken

``APITokenBase.scopes`` (``Optional[List[str]]`` mapped to ``Column(JSON)``)
was added to the model after the last migration, but no migration ever
added the column. ``SQLModel.metadata.create_all`` only creates *missing
tables*, it never ALTERs an existing one, so on every database that
already has ``apitoken`` -- i.e. every real environment -- the column is
absent while the ORM keeps selecting and inserting it. Every read/write
of a token then fails with::

    UndefinedColumn: column apitoken.scopes does not exist

which includes the token-authentication path, so it surfaces as 500s in
production rather than as a migration failure.

Adds the column as nullable JSON, matching the model. No server default
is set: the model uses a Python-side ``default_factory=list``, and
``NULL`` is read back as ``None``, which the read schemas already allow.

Revision ID: c5d6e7f8a9b0
Revises: f9a0b1c2d3e4
Create Date: 2026-09-16

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel  # noqa: F401


revision: str = 'c5d6e7f8a9b0'
down_revision: Union[str, None] = 'f9a0b1c2d3e4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if 'apitoken' not in inspector.get_table_names():
        return

    existing_columns = {col['name'] for col in inspector.get_columns('apitoken')}
    if 'scopes' in existing_columns:
        return

    op.add_column(
        'apitoken',
        sa.Column(
            'scopes',
            sa.JSON(),
            nullable=True,
        ),
    )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if 'apitoken' not in inspector.get_table_names():
        return

    existing_columns = {col['name'] for col in inspector.get_columns('apitoken')}
    if 'scopes' in existing_columns:
        op.drop_column('apitoken', 'scopes')
