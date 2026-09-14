"""Payroll separation of duties.

The three payroll endpoints compose into a self-dealing path: set a salary
structure, generate a slip from it, mark the slip paid. Narrowing the role to
SCHOOL_ADMIN reduced WHO could walk that path; it did not introduce a control,
because one person could still take every step alone.

This adds the missing control: a slip must be APPROVED by someone other than
the person who PREPARED it before it can be paid.

`sms_salary_slip` has no `created_by` column, and adding one would need a
migration that then disagrees with every database already holding the table.
So `PayrollAction` carries it: a PREPARED row is written when slips are
generated, and approval reads that row to identify the preparer. The audit
trail is therefore also the enforcement mechanism rather than a parallel
record that could drift from it.
"""

from typing import List, Optional, Sequence

from sqlalchemy import select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.db.sms_hr import StaffProfile
from src.db.sms_hr_extended import PayrollAction, PayrollActionType
from src.db.sms_payroll import SalaryPaymentStatus, SalarySlip


async def record_payroll_action(
    session: AsyncSession,
    slip: SalarySlip,
    action: PayrollActionType,
    actor_user_id: Optional[int],
    campus_id: Optional[int] = None,
    note: Optional[str] = None,
    actor_label: Optional[str] = None,
) -> PayrollAction:
    """Append one action to the trail.

    Added to the session but NOT committed: the caller commits it in the same
    transaction as the change it describes, so a crash cannot leave a slip
    paid with no record of who paid it.
    """
    event = PayrollAction(
        slip_id=slip.id,
        staff_id=slip.staff_id,
        campus_id=campus_id,
        action=action,
        net_salary_at_action=slip.net_salary,
        note=note,
        actor_user_id=actor_user_id,
        actor_label=actor_label,
    )
    session.add(event)
    return event


async def record_prepared_actions(
    session: AsyncSession,
    slips: Sequence[SalarySlip],
    actor_user_id: Optional[int],
) -> None:
    """Write a PREPARED row for each newly generated slip.

    Without this the system cannot answer "who produced this slip?", and
    separation of duties has nothing to compare an approver against.
    """
    if not slips:
        return

    staff_ids = {s.staff_id for s in slips}
    campus_by_staff = {}
    if staff_ids:
        rows = (
            await session.execute(
                select(StaffProfile).where(StaffProfile.id.in_(staff_ids))
            )
        ).scalars().all()
        campus_by_staff = {p.id: p.campus_id for p in rows}

    for slip in slips:
        await record_payroll_action(
            session=session,
            slip=slip,
            action=PayrollActionType.PREPARED,
            actor_user_id=actor_user_id,
            campus_id=campus_by_staff.get(slip.staff_id),
        )


async def get_preparer_user_id(session: AsyncSession, slip_id: int) -> Optional[int]:
    """Who generated this slip, per the trail. None if unknown."""
    row = (
        await session.execute(
            select(PayrollAction)
            .where(
                PayrollAction.slip_id == slip_id,
                PayrollAction.action == PayrollActionType.PREPARED,
            )
            .order_by(PayrollAction.id.asc())
        )
    ).scalars().first()
    return row.actor_user_id if row is not None else None


async def latest_action(
    session: AsyncSession, slip_id: int, action: PayrollActionType
) -> Optional[PayrollAction]:
    return (
        await session.execute(
            select(PayrollAction)
            .where(PayrollAction.slip_id == slip_id, PayrollAction.action == action)
            .order_by(PayrollAction.id.desc())
        )
    ).scalars().first()


async def is_approved(session: AsyncSession, slip_id: int) -> bool:
    """Approved, and not subsequently rejected."""
    approved = await latest_action(session, slip_id, PayrollActionType.APPROVED)
    if approved is None:
        return False
    rejected = await latest_action(session, slip_id, PayrollActionType.REJECTED)
    if rejected is None:
        return True
    # Whichever came last wins; ids are monotonic within this table.
    return (approved.id or 0) > (rejected.id or 0)


async def assert_payable(session: AsyncSession, slip_id: int) -> None:
    """Raise unless this slip has been approved by a second party.

    Imported and called by the pay endpoint. Deliberately a hard failure
    rather than a warning: a payment that goes out unapproved cannot be
    recalled, so refusing is the recoverable direction.
    """
    from fastapi import HTTPException, status

    if not await is_approved(session, slip_id):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "This salary slip has not been approved. Payroll requires "
                "approval by someone other than the person who prepared it "
                "before payment can be recorded."
            ),
        )


async def approve_slips(
    session: AsyncSession,
    slip_ids: List[int],
    actor_user_id: Optional[int],
    note: Optional[str],
    reject: bool = False,
) -> List[dict]:
    """Approve (or reject) slips, enforcing separation of duties.

    A bad slip is REPORTED, not raised: one unapprovable slip must not abort a
    whole payroll review, leaving the reviewer unsure which of thirty slips
    were actioned.
    """
    results: List[dict] = []

    for slip_id in slip_ids:
        slip = (
            await session.execute(select(SalarySlip).where(SalarySlip.id == slip_id))
        ).scalar_one_or_none()

        if slip is None:
            results.append(
                {"slip_id": slip_id, "outcome": "not_found", "detail": "No such salary slip."}
            )
            continue

        if slip.payment_status == SalaryPaymentStatus.PAID:
            results.append(
                {
                    "slip_id": slip_id,
                    "outcome": "already_paid",
                    "detail": "Already disbursed; approval no longer applies.",
                }
            )
            continue

        if not reject:
            preparer = await get_preparer_user_id(session, slip_id)
            if (
                preparer is not None
                and actor_user_id is not None
                and preparer == actor_user_id
            ):
                # THE control. Without it, one person completes the whole
                # prepare -> approve -> pay path unaided.
                results.append(
                    {
                        "slip_id": slip_id,
                        "outcome": "self_approval_refused",
                        "detail": (
                            "You prepared this slip. Payroll must be approved "
                            "by a second person."
                        ),
                    }
                )
                continue

        profile = (
            await session.execute(
                select(StaffProfile).where(StaffProfile.id == slip.staff_id)
            )
        ).scalar_one_or_none()

        await record_payroll_action(
            session=session,
            slip=slip,
            action=PayrollActionType.REJECTED if reject else PayrollActionType.APPROVED,
            actor_user_id=actor_user_id,
            campus_id=profile.campus_id if profile is not None else None,
            note=note,
        )
        results.append(
            {
                "slip_id": slip_id,
                "outcome": "rejected" if reject else "approved",
                "detail": None,
            }
        )

    await session.commit()
    return results
