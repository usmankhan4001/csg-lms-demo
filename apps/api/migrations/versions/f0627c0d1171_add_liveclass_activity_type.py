"""add TYPE_LIVECLASS / SUBTYPE_LIVECLASS_LIVEKIT to the activity enums

Lets a live class be a first-class course ACTIVITY (added from the course
builder's "add activity" picker, rendered inline in the player) rather than
the detached /live/[roomId] island it was. The LiveKit machinery itself
already exists and works -- this only teaches Learnhouse's activity system
that the type exists.

Why a migration at all, when every sms_* table in this project is created by
SQLModel.metadata.create_all: `activity` is a Learnhouse CORE table, and
activity_type / activity_sub_type are native PostgreSQL enum types
(activitytypeenum / activitysubtypeenum -- verified against the running
database), not varchars. Adding a label therefore needs ALTER TYPE, which
create_all will never emit.

Mirrors b2c3d4e5f8a9 (add CUSTOM to assignmenttasktypeenum) exactly.

Revision ID: f0627c0d1171
Revises: a1c4e90d77b3
Create Date: 2026-09-13

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa  # noqa: F401
import sqlmodel  # noqa: F401


# revision identifiers, used by Alembic.
revision: str = 'f0627c0d1171'
down_revision: Union[str, None] = 'a1c4e90d77b3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ALTER TYPE ... ADD VALUE cannot run inside a transaction block; commit the
    # migration's implicit transaction first (mirrors b2c3d4e5f8a9).
    op.execute("COMMIT")
    op.execute("ALTER TYPE activitytypeenum ADD VALUE IF NOT EXISTS 'TYPE_LIVECLASS'")
    op.execute(
        "ALTER TYPE activitysubtypeenum ADD VALUE IF NOT EXISTS 'SUBTYPE_LIVECLASS_LIVEKIT'"
    )


def downgrade() -> None:
    # PostgreSQL cannot remove an enum value. Rows already carrying the label
    # would be orphaned by a DROP/recreate, so this is deliberately a no-op --
    # same stance as every other enum migration in this project.
    pass
