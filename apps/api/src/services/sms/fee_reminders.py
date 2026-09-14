"""Scheduled fee reminders (M08).

THE GAP THIS CLOSES: late fees accrue automatically and, until now, nobody told
the family. A balance grew silently until someone happened to open the ledger,
and the first a parent heard of it was a larger bill than they expected. A
school chasing a debt it never mentioned is both bad practice and, for the
family, indistinguishable from a billing error.

Runs daily rather than hourly: a fee balance changes on the scale of days, and
an hourly job would be a machine for harassing families.

Every send goes through `services/notifications/service.notify()`, so:

* the notification is PERSISTED and readable in-app even when mail is broken;
* a failed email is a visible `NotificationDelivery` row with its reason,
  rather than a swallowed log line;
* `FeeReminderLog.delivered` records what the provider actually accepted, not
  what we hoped -- so "were we really chasing this?" has a truthful answer.

With `RESEND_API_KEY` unset (the default in this deployment) every email
attempt fails and is recorded as failed, while the in-app notification still
exists. That is the honest outcome, and the log makes the gap visible instead
of letting a school believe reminders went out.
"""

import datetime
import logging
from typing import Dict, List, Optional

from sqlalchemy import and_, select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.db.sms_fees import StudentFeeVoucher, VoucherStatus
from src.db.sms_fees_extended import FeeReminderKind, FeeReminderLog
from src.db.sms_identity import StudentGuardian
from src.db.users import User

logger = logging.getLogger(__name__)

# Days before the due date at which a courtesy reminder goes out.
UPCOMING_DAYS_BEFORE = 7

# Overdue reminders repeat on this cadence rather than daily. Seven days is
# long enough not to badger a family who already knows, short enough that a
# balance cannot drift a month without contact.
OVERDUE_REPEAT_DAYS = 7


def _reminder_kind(
    voucher: StudentFeeVoucher, today: datetime.date
) -> Optional[FeeReminderKind]:
    """Which reminder, if any, this voucher warrants today."""
    days_until_due = (voucher.due_date - today).days
    if days_until_due == UPCOMING_DAYS_BEFORE:
        return FeeReminderKind.UPCOMING
    if days_until_due == 0:
        return FeeReminderKind.DUE_TODAY
    if days_until_due < 0:
        return FeeReminderKind.OVERDUE
    return None


def render_reminder_html(
    voucher: StudentFeeVoucher, kind: FeeReminderKind, student_name: str
) -> str:
    """The reminder a family actually receives.

    States only figures taken from the voucher itself. Where a late fee has
    been charged it is named separately, because an unexplained increase in
    what is owed is exactly what generates an angry phone call.
    """
    if kind == FeeReminderKind.UPCOMING:
        lead = f"A fee payment for {student_name} is due on {voucher.due_date:%d %B %Y}."
    elif kind == FeeReminderKind.DUE_TODAY:
        lead = f"A fee payment for {student_name} is due today."
    else:
        days = (datetime.date.today() - voucher.due_date).days
        lead = (
            f"A fee payment for {student_name} was due on {voucher.due_date:%d %B %Y}, "
            f"{days} day{'s' if days != 1 else ''} ago."
        )

    late_fee_line = ""
    if voucher.late_fee_applied and voucher.late_fee_applied > 0:
        late_fee_line = (
            f'<tr><td style="padding:4px 12px 4px 0;color:#666">Late fee charged</td>'
            f"<td><strong>{voucher.late_fee_applied:.2f}</strong></td></tr>"
        )

    installment_line = ""
    if voucher.installment_number:
        installment_line = (
            f'<tr><td style="padding:4px 12px 4px 0;color:#666">Instalment</td>'
            f"<td>{voucher.installment_number}</td></tr>"
        )

    return f"""
    <div style="font-family:system-ui,-apple-system,Segoe UI,sans-serif;line-height:1.5">
      <h2 style="margin-bottom:4px">Fee reminder</h2>
      <p style="margin-top:0;color:#444">{lead}</p>
      <table style="border-collapse:collapse;margin:16px 0">
        <tr><td style="padding:4px 12px 4px 0;color:#666">Voucher</td><td>{voucher.voucher_no}</td></tr>
        {installment_line}
        <tr><td style="padding:4px 12px 4px 0;color:#666">Total</td><td>{voucher.total_amount:.2f}</td></tr>
        <tr><td style="padding:4px 12px 4px 0;color:#666">Already paid</td><td>{voucher.paid_amount:.2f}</td></tr>
        {late_fee_line}
        <tr><td style="padding:4px 12px 4px 0;color:#666">Outstanding</td>
            <td><strong>{voucher.balance_amount:.2f}</strong></td></tr>
      </table>
      <p style="color:#888;font-size:12px">
        Figures come from the school's own fee records. If you have already paid,
        or believe this is wrong, please contact the school office.
      </p>
    </div>
    """


async def _already_reminded(
    session: AsyncSession,
    voucher_id: int,
    kind: FeeReminderKind,
    today: datetime.date,
) -> bool:
    """Has this reminder already gone out recently?

    UPCOMING and DUE_TODAY fire on an exact day, so one log row ever is enough.
    OVERDUE repeats, so it is suppressed only within the repeat window.
    """
    stmt = select(FeeReminderLog).where(
        and_(FeeReminderLog.voucher_id == voucher_id, FeeReminderLog.kind == kind)
    )
    rows = (await session.execute(stmt)).scalars().all()
    if not rows:
        return False
    if kind != FeeReminderKind.OVERDUE:
        return True
    most_recent = max(r.sent_on for r in rows)
    return (today - most_recent).days < OVERDUE_REPEAT_DAYS


async def _resolve_student_org_id(session, student_id: int):
    """Which school a student belongs to, or None.

    Returns None rather than a fallback. A fee reminder is a demand for money
    naming a child; sending one under a guessed tenant is the worst version of
    the cross-tenant default this codebase has spent the day removing.
    """
    from src.db.sms_identity import SMSUserRole

    row = (
        await session.execute(
            select(SMSUserRole).where(
                SMSUserRole.user_id == student_id,
                SMSUserRole.is_active == True,  # noqa: E712
            )
        )
    ).scalars().first()
    return getattr(row, "org_id", None) if row is not None else None


async def send_fee_reminders(ctx: Optional[dict] = None) -> Dict[str, int]:
    """arq job: remind guardians about upcoming, due and overdue fees.

    Registered as a daily cron job in `src/core/worker.py`. Opens its own DB
    session because jobs run outside request scope, and never lets one family's
    failure abort the batch.
    """
    from src.core.events.database import _async_session_factory
    from src.services.notifications import notify_event
    from src.services.sms.school_events import FEE_REMINDER

    today = datetime.date.today()
    considered = 0
    sent = 0
    skipped_settled = 0
    skipped_recent = 0
    no_guardian = 0
    no_org = 0
    failed = 0

    async with _async_session_factory() as session:
        # PAID owes nothing; CANCELLED is void. Reminding on either would be
        # chasing a debt that does not exist.
        stmt = select(StudentFeeVoucher).where(
            StudentFeeVoucher.status.in_([VoucherStatus.UNPAID, VoucherStatus.PARTIAL])
        )
        vouchers = (await session.execute(stmt)).scalars().all()

        guardians_by_student: Dict[int, List[User]] = {}

        for voucher in vouchers:
            try:
                considered += 1
                if voucher.balance_amount <= 0.001:
                    # Defensive: a zero balance on a non-PAID voucher is a data
                    # oddity, not something to chase a family about.
                    skipped_settled += 1
                    continue

                kind = _reminder_kind(voucher, today)
                if kind is None:
                    continue

                if await _already_reminded(session, voucher.id, kind, today):
                    skipped_recent += 1
                    continue

                if voucher.student_id not in guardians_by_student:
                    links = (
                        (
                            await session.execute(
                                select(StudentGuardian).where(
                                    StudentGuardian.student_id == voucher.student_id
                                )
                            )
                        )
                        .scalars()
                        .all()
                    )
                    people: List[User] = []
                    for link in links:
                        guardian = await session.get(User, link.guardian_user_id)
                        if guardian is not None:
                            people.append(guardian)
                    guardians_by_student[voucher.student_id] = people

                recipients = guardians_by_student[voucher.student_id]
                if not recipients:
                    # Loud: a family that cannot be contacted about money owed
                    # is a data gap the school needs to close, not a silent
                    # skip.
                    no_guardian += 1
                    logger.warning(
                        "Fee reminder undeliverable: student %s has no guardian link (voucher %s)",
                        voucher.student_id,
                        voucher.voucher_no,
                    )
                    continue

                student = await session.get(User, voucher.student_id)
                student_name = (
                    getattr(student, "username", None) or f"student #{voucher.student_id}"
                )

                # MIGRATED FROM `notify()` TO THE EVENT FABRIC (Lane J).
                #
                # The direct `notify()` call worked, but it sat outside
                # everything the fabric exists for: a parent could not switch
                # fee email off, two runs of this job in one day sent two
                # reminders, and nothing recorded WHY a message did not arrive.
                # It also passed no `org_id`, so the notification rows it wrote
                # were unscoped -- in a multi-school deployment that is a row
                # belonging to no tenant.
                #
                # `render_reminder_html` is deliberately still used rather than
                # replaced by a registered template: it renders a real money
                # figure from the voucher, and re-expressing that as template
                # context risks formatting a balance in the one place where
                # being approximately right is being wrong. The fabric's
                # per-school template override therefore does not apply to this
                # one event; that is a known limit, noted here rather than
                # hidden.
                # WHERE org_id COMES FROM, and why it is not on the voucher.
                #
                # `StudentFeeVoucher` carries no tenant column -- it is scoped
                # only transitively, through the student. The fabric refuses to
                # send without an explicit org (a message naming a child must
                # never go out under a guessed tenant), so it is resolved from
                # the student's own role grant here and the voucher is SKIPPED,
                # loudly, when it cannot be. Defaulting would be the same
                # eighteen-site `org_id or 1` bug that Lane C has just removed
                # from this codebase, reintroduced in the one place that sends
                # a family a demand for money.
                org_id = await _resolve_student_org_id(session, voucher.student_id)
                if org_id is None:
                    no_org += 1
                    logger.warning(
                        "Fee reminder for voucher %s skipped: student %s has no "
                        "school role, so the school it belongs to cannot be "
                        "established.",
                        voucher.voucher_no,
                        voucher.student_id,
                    )
                    continue

                result = await notify_event(
                    session,
                    event_key=FEE_REMINDER.key,
                    org_id=org_id,
                    recipients=recipients,
                    context={
                        "student_name": student_name,
                        "amount": f"{voucher.balance_amount:.2f}",
                        "due_date": voucher.due_date.isoformat()
                        if getattr(voucher, "due_date", None)
                        else None,
                    },
                    related_kind="fee_voucher",
                    related_id=voucher.id,
                )

                session.add(
                    FeeReminderLog(
                        voucher_id=voucher.id,
                        student_id=voucher.student_id,
                        kind=kind,
                        sent_on=today,
                        recipients=len(recipients),
                        delivered=result.delivered,
                        balance_at_send=voucher.balance_amount,
                    )
                )
                await session.commit()
                sent += 1
            except Exception:
                failed += 1
                logger.exception(
                    "Fee reminder failed for voucher %s", getattr(voucher, "id", None)
                )
                try:
                    await session.rollback()
                except Exception:
                    logger.exception("Rollback failed after fee reminder error")

    logger.info(
        "Fee reminders: %d considered, %d sent, %d already reminded, %d without a guardian, %d failed",
        considered,
        sent,
        skipped_recent,
        no_guardian,
        no_org,
        failed,
    )
    return {
        "considered": considered,
        "sent": sent,
        "skipped_settled": skipped_settled,
        "skipped_recent": skipped_recent,
        "no_guardian": no_guardian,
        # Vouchers whose school could not be established. Surfaced rather than
        # folded into "failed": it is a data gap (a student with no role
        # grant), not a delivery fault, and the fix is different.
        "no_org": no_org,
        "failed": failed,
    }
