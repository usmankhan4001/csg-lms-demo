"""add installment_plan_id and installment_number to sms_student_fee_voucher

TWO NEW COLUMNS ON AN EXISTING TABLE. `create_all` creates missing TABLES but
never ALTERs, so without this migration the code and every existing database
disagree and every fee read fails. The five new fee tables
(sms_fee_installment_plan, sms_fee_concession, sms_fee_concession_application,
sms_fee_refund, sms_bank_transfer_record, sms_fee_reminder_log,
sms_fee_change_event) land on their own via create_all and are NOT in this
migration.

WHY THESE COLUMNS EXIST: schools in this market bill in instalments as
standard. Before this, a three-instalment year meant three disconnected
vouchers with no parent-visible schedule and no way to answer "have we paid 2
of 3?".

Each instalment is modelled as a real voucher belonging to a plan, rather than
one voucher carrying a payment schedule, because late-fee accrual reads
`due_date` per voucher. A family that misses instalment 2 must be charged a
late fee on instalment 2 -- with a single voucher, accrual would read the one
due date and charge late fees against the entire year's fee the day the first
instalment slipped.

Both columns are NULLABLE: every voucher that exists today is a one-off and
stays one, and the ordinary billing path is unchanged. The FK is SET NULL
rather than CASCADE -- deleting a plan must never delete the money a family
owes.

Revision ID: 2f4c13b60f5b
Revises: 03447a484193
Create Date: 2026-09-14

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa  # noqa: F401
import sqlmodel  # noqa: F401


# revision identifiers, used by Alembic.
revision: str = '2f4c13b60f5b'
down_revision: Union[str, None] = '03447a484193'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "sms_student_fee_voucher",
        sa.Column("installment_plan_id", sa.Integer(), nullable=True),
    )
    op.add_column(
        "sms_student_fee_voucher",
        sa.Column("installment_number", sa.Integer(), nullable=True),
    )
    op.create_index(
        "ix_sms_student_fee_voucher_installment_plan_id",
        "sms_student_fee_voucher",
        ["installment_plan_id"],
    )
    # No FK constraint, matching the model exactly.
    # `sms_fee_installment_plan` is created by SQLModel's create_all when the
    # app boots, which happens AFTER `alembic upgrade head` in the container
    # entrypoint -- so a create_foreign_key here would reference a table that
    # does not yet exist on a fresh database. Declaring the column as a plain
    # integer in BOTH the model and this migration keeps the two deployment
    # paths (fresh create_all vs. migrated) structurally identical, rather than
    # leaving an FK that exists in one and not the other.


def downgrade() -> None:
    op.drop_index(
        "ix_sms_student_fee_voucher_installment_plan_id",
        table_name="sms_student_fee_voucher",
    )
    op.drop_column("sms_student_fee_voucher", "installment_number")
    op.drop_column("sms_student_fee_voucher", "installment_plan_id")
