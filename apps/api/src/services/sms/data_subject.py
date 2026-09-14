"""
Data-subject access and erasure for the SCHOOL record.
=======================================================

Why this module exists
----------------------
`services/admin/admin.py::export_user_data` is labelled "Full GDPR data
export" and returns memberships, trails, certificates, usergroups and API
tokens -- i.e. the Learnhouse LMS record. It touches no `sms_` table at all.
So a parent asking "show me everything you hold on my child" received course
trails and none of: enrolment, attendance, grades, report cards, fees,
library loans, live-class attendance, tutor transcripts or admissions history.

That is worse than having no export, because it *looks* like compliance.

Two rules this module is built around
-------------------------------------
1. **Existence-masking beats completeness.** `routers/sms_counseling.py`
   enforces a deliberate 404-never-403 policy: where a record's EXISTENCE is
   confidential, a non-psychologist gets an empty result, never "access
   denied", so existence can never be inferred. An export is the obvious back
   door around that -- "2 counselling sessions withheld" leaks exactly what
   the 404 rule protects. So for a caller without clinical authority those
   tables are **silently absent**, indistinguishable from a child who has no
   such records. See `_CLINICAL` / `_SAFEGUARDING_INCIDENTS` below.

2. **Never claim a deletion you did not perform.** A school has statutory
   retention duties for academic, financial and safeguarding records; it
   cannot simply delete a child on request, and deleting a grade would
   corrupt a section's aggregate. So erasure removes what it genuinely can
   and returns an *itemised* statement of what is retained and under what
   basis. A system that reports "deleted" while keeping the data is the same
   class of lie as the export that claimed to be complete.

Identifier note
---------------
A subject has two identifiers and the tables are split between them:
`user.id` (int) for most `sms_` tables, and `user.user_uuid` (str) for
`ai_safety_incidents`, `student_concept_masteries`, `sms_lesson_plan` and
`sms_counseling.psychologist_id`. Both are resolved up front; keying on only
one silently omits whole modules.
"""

import datetime
import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import delete as sql_delete
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.db.ai_models import AISafetyIncident
from src.db.ai_oversight import AITutorAccessBlock, AITutorTranscript
from src.db.data_subject import DataSubjectRequestLog
from src.db.notifications import Message, Notification, ThreadParticipant
from src.db.revops_conversation import (
    LeadConversationTurn,
    LeadNurtureState,
    LeadOutboundTouch,
)
from src.db.sms_attendance import AttendanceLeaveRequest, StudentAttendance
from src.db.sms_campus import StudentEnrollment
from src.db.sms_counseling import (
    CareerGuidancePlan,
    CounselingActivityLog,
    CounselingSession,
)
from src.db.sms_exam import AssignmentHintUsage, ExamIncident, ExamResult
from src.db.sms_fees import StudentFeeVoucher
from src.db.sms_gradebook import GradebookEntry, TermReportCard
from src.db.sms_hr import StaffLeave, StaffProfile
from src.db.sms_identity import SMSImpersonationEvent, SMSUserRole, StudentGuardian
from src.db.sms_library import BookLoan
from src.db.sms_live_class import LiveClassAttendanceLog, LiveClassSession
from src.db.sms_payroll import SalarySlip, SalaryStructure
from src.db.sms_revops import AdmissionsLead, LeadActivityLog, ScholarshipOffer
from src.db.sms_teacher_tools import LessonPlan
from src.db.sms_timetable import TimetableSchedule
from src.db.users import User

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Retention bases. These are the reasons a school may lawfully keep a record
# after an erasure request. Each erased/retained line quotes one, so the
# statement a family receives is specific rather than "some data is retained".
# ---------------------------------------------------------------------------

RETENTION_ACADEMIC = (
    "Academic record. Schools are required to retain enrolment, attendance, "
    "assessment and certification records for a statutory period, and a "
    "pupil's results also form part of other pupils' cohort aggregates."
)
RETENTION_FINANCIAL = (
    "Financial record. Invoices, payments and receipts are retained to meet "
    "tax and accounting obligations."
)
RETENTION_SAFEGUARDING = (
    "Safeguarding record. Child-protection and wellbeing records are retained "
    "under statutory child-protection duties and cannot be deleted on request."
)
RETENTION_SECURITY = (
    "Security audit record. Role grants and administrative access events are "
    "retained so that access to children's data remains auditable."
)
RETENTION_EMPLOYMENT = (
    "Employment record. Contract, leave and payroll records are retained to "
    "meet employment and tax obligations."
)


@dataclass(frozen=True)
class SubjectTable:
    """One table's relationship to a data subject.

    `erasable` is the whole judgement: True means there is no statutory basis
    to keep it once a subject objects, False means there is and
    `retention_basis` says which.
    """

    key: str
    model: Any
    column: str
    #: True when `column` holds `user.user_uuid` rather than `user.id`.
    by_uuid: bool = False
    erasable: bool = False
    retention_basis: str = ""
    #: Scrub these columns instead of deleting the row. Used where the row
    #: itself must survive (it anchors other records) but the PII need not.
    scrub_fields: Tuple[str, ...] = ()


# ---------------------------------------------------------------------------
# The subject's school record, excluding confidential clinical records.
#
# Everything a school holds ABOUT a person, keyed on that person. Tables that
# describe the SCHOOL rather than a subject are deliberately absent: fee
# structures, the chart of accounts, journal entries, the book catalogue, the
# timetable's periods, campuses, years, terms and sections are institutional
# configuration, not personal data, and exporting them would bury a family's
# actual record in noise.
#
# `sms_school_settings.updated_by_user_id` is likewise excluded: incidental
# authorship metadata on a config row is not a record about that person.
# ---------------------------------------------------------------------------

_GENERAL: Tuple[SubjectTable, ...] = (
    # --- identity and enrolment -------------------------------------------
    SubjectTable("school_roles", SMSUserRole, "user_id",
                 retention_basis=RETENTION_SECURITY),
    SubjectTable("guardian_of", StudentGuardian, "guardian_user_id",
                 retention_basis=RETENTION_ACADEMIC),
    SubjectTable("guardians", StudentGuardian, "student_id",
                 retention_basis=RETENTION_ACADEMIC),
    SubjectTable("enrolments", StudentEnrollment, "student_id",
                 retention_basis=RETENTION_ACADEMIC),
    # `target_user_id`, not `actor_user_id`: the record that matters to a
    # subject is who impersonated THEM, not who they impersonated.
    SubjectTable("impersonated_by", SMSImpersonationEvent, "target_user_id",
                 retention_basis=RETENTION_SECURITY),

    # --- attendance --------------------------------------------------------
    SubjectTable("attendance", StudentAttendance, "student_id",
                 retention_basis=RETENTION_ACADEMIC),
    SubjectTable("leave_requests", AttendanceLeaveRequest, "student_id",
                 retention_basis=RETENTION_ACADEMIC),

    # --- assessment --------------------------------------------------------
    SubjectTable("grades", GradebookEntry, "student_id",
                 retention_basis=RETENTION_ACADEMIC),
    SubjectTable("report_cards", TermReportCard, "student_id",
                 retention_basis=RETENTION_ACADEMIC),
    SubjectTable("exam_results", ExamResult, "student_id",
                 retention_basis=RETENTION_ACADEMIC),
    SubjectTable("exam_incidents", ExamIncident, "student_id",
                 retention_basis=RETENTION_ACADEMIC),

    # --- fees --------------------------------------------------------------
    SubjectTable("fee_vouchers", StudentFeeVoucher, "student_id",
                 retention_basis=RETENTION_FINANCIAL),

    # --- library and live classes -----------------------------------------
    SubjectTable("library_loans", BookLoan, "user_id",
                 retention_basis=RETENTION_FINANCIAL),
    SubjectTable("live_class_attendance", LiveClassAttendanceLog, "student_id",
                 retention_basis=RETENTION_ACADEMIC),

    # --- AI tutor ----------------------------------------------------------
    # Transcripts ARE erasable: a conversation with a chatbot is not an
    # academic record, and this is precisely the "AI processing of my child's
    # data" a family is most likely to object to. Hint usage is NOT, because
    # it carries a grading penalty and deleting it would alter a mark.
    SubjectTable("tutor_transcripts", AITutorTranscript, "student_id", erasable=True),
    SubjectTable("tutor_access_blocks", AITutorAccessBlock, "student_id",
                 retention_basis=RETENTION_SAFEGUARDING),
    SubjectTable("assignment_hint_usage", AssignmentHintUsage, "student_id",
                 retention_basis=RETENTION_ACADEMIC),

    # --- notifications and messaging --------------------------------------
    # Notifications are transient delivery artefacts -> erasable. Messages
    # are not: a thread is a two-party record and deleting one side's
    # messages would silently rewrite the other party's conversation.
    SubjectTable("notifications", Notification, "recipient_user_id", erasable=True),
    SubjectTable("message_participation", ThreadParticipant, "user_id",
                 retention_basis=RETENTION_ACADEMIC),
    SubjectTable("messages_sent", Message, "sender_user_id",
                 retention_basis=RETENTION_ACADEMIC),

    # --- career guidance ---------------------------------------------------
    # Explicitly NOT existence-masked: the module docstring states career
    # plans are "academic/advisory in nature, not a clinical record".
    SubjectTable("career_guidance_plans", CareerGuidancePlan, "student_id",
                 retention_basis=RETENTION_ACADEMIC),
)

# Staff-side records. Only populated when the subject is actually staff.
_STAFF: Tuple[SubjectTable, ...] = (
    SubjectTable("staff_profile", StaffProfile, "user_id",
                 retention_basis=RETENTION_EMPLOYMENT),
    SubjectTable("lessons_taught", LiveClassSession, "teacher_id",
                 retention_basis=RETENTION_ACADEMIC),
    SubjectTable("timetable_slots", TimetableSchedule, "teacher_id",
                 retention_basis=RETENTION_ACADEMIC),
    SubjectTable("lesson_plans", LessonPlan, "teacher_id", by_uuid=True,
                 retention_basis=RETENTION_ACADEMIC),
)

# Staff records keyed on StaffProfile.id rather than user.id -- a second hop.
# Keying these on user_id would silently return nothing, which is how a
# payroll record quietly goes missing from a subject-access response.
_STAFF_BY_PROFILE: Tuple[SubjectTable, ...] = (
    SubjectTable("staff_leave", StaffLeave, "staff_id",
                 retention_basis=RETENTION_EMPLOYMENT),
    SubjectTable("salary_structure", SalaryStructure, "staff_id",
                 retention_basis=RETENTION_EMPLOYMENT),
    SubjectTable("salary_slips", SalarySlip, "staff_id",
                 retention_basis=RETENTION_EMPLOYMENT),
)

# Admissions / marketing. This is the most erasable category in the system:
# a lead is a marketing record, and once a family has objected there is no
# basis to keep nurture history. The lead ROW itself is scrubbed rather than
# deleted where it anchors an enrolment.
_LEAD: Tuple[SubjectTable, ...] = (
    SubjectTable("admissions_leads", AdmissionsLead, "email",
                 scrub_fields=("parent_name", "student_name", "email", "phone", "notes")),
    SubjectTable("lead_activity", LeadActivityLog, "lead_id", erasable=True),
    SubjectTable("lead_conversations", LeadConversationTurn, "lead_id", erasable=True),
    SubjectTable("lead_nurture_state", LeadNurtureState, "lead_id", erasable=True),
    SubjectTable("lead_outbound", LeadOutboundTouch, "lead_id", erasable=True),
    SubjectTable("scholarship_offers", ScholarshipOffer, "lead_id",
                 retention_basis=RETENTION_FINANCIAL),
)

# ---------------------------------------------------------------------------
# CONFIDENTIAL. Included ONLY for a caller with clinical authority, and
# SILENTLY ABSENT otherwise -- never listed as withheld, never counted, never
# mentioned in the retention statement. Reporting "withheld: 2 counselling
# sessions" would defeat the 404-never-403 rule these tables live under just
# as effectively as returning them.
#
# None are erasable: safeguarding records are retained under child-protection
# duties. But that fact is only ever stated to a caller who could already see
# them -- for anyone else the retention statement does not mention them at all.
# ---------------------------------------------------------------------------

# Two tiers, because the codebase enforces two different rules and collapsing
# them would over- or under-disclose:
#
#   _CLINICAL  -- counselling. routers/sms_counseling.py is PSYCHOLOGIST-only;
#                 a SCHOOL_ADMIN gets a 404 there, so they must not receive
#                 these rows through an export either.
#   _SAFEGUARDING_INCIDENTS -- AI safety incidents. ai_oversight.py gates these
#                 on SUPER_ADMIN / SCHOOL_ADMIN / PSYCHOLOGIST, so school
#                 leadership legitimately sees them.
_CLINICAL: Tuple[SubjectTable, ...] = (
    SubjectTable("counselling_sessions", CounselingSession, "student_id",
                 retention_basis=RETENTION_SAFEGUARDING),
    SubjectTable("counselling_activity", CounselingActivityLog, "student_id",
                 retention_basis=RETENTION_SAFEGUARDING),
)

_SAFEGUARDING_INCIDENTS: Tuple[SubjectTable, ...] = (
    SubjectTable("ai_safety_incidents", AISafetyIncident, "student_id", by_uuid=True,
                 retention_basis=RETENTION_SAFEGUARDING),
)


def _rows_to_dicts(rows: List[Any]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for r in rows:
        try:
            out.append(r.model_dump(mode="json"))
        except Exception:  # pragma: no cover - defensive
            out.append({k: str(v) for k, v in vars(r).items() if not k.startswith("_")})
    return out


async def _fetch(
    session: AsyncSession, spec: SubjectTable, user_id: int, user_uuid: str,
    lead_ids: Optional[List[int]] = None, email: Optional[str] = None,
    staff_profile_ids: Optional[List[int]] = None,
) -> List[Any]:
    """Rows of one table belonging to this subject, or [] if not applicable."""
    col = getattr(spec.model, spec.column, None)
    if col is None:
        logger.warning("Data-subject spec references missing column %s.%s",
                       spec.model.__name__, spec.column)
        return []

    if spec.column == "lead_id":
        if not lead_ids:
            return []
        stmt = select(spec.model).where(col.in_(lead_ids))
    elif spec.column == "staff_id":
        if not staff_profile_ids:
            return []
        stmt = select(spec.model).where(col.in_(staff_profile_ids))
    elif spec.column == "email":
        if not email:
            return []
        stmt = select(spec.model).where(col == email)
    elif spec.by_uuid:
        stmt = select(spec.model).where(col == user_uuid)
    else:
        stmt = select(spec.model).where(col == user_id)

    try:
        return list((await session.execute(stmt)).scalars().all())
    except Exception:
        # A table that does not exist yet (a module mid-migration) must not
        # take down a subject-access request. Log loudly; omit the section.
        logger.exception("Data-subject fetch failed for %s", spec.key)
        return []


async def _resolve_linked_ids(
    session: AsyncSession, user_id: int, email: Optional[str]
) -> Tuple[List[int], List[int]]:
    """(lead_ids, staff_profile_ids) for this subject.

    Leads are matched on email -- a prospective family has no user row yet, so
    the lead is the only link back to them. Staff payroll hangs off
    StaffProfile.id, not user.id.
    """
    lead_ids: List[int] = []
    staff_profile_ids: List[int] = []

    if email:
        try:
            lead_ids = [
                r for (r,) in (await session.execute(
                    select(AdmissionsLead.id).where(AdmissionsLead.email == email)
                )).all()
            ]
        except Exception:
            logger.exception("Lead lookup failed during data-subject resolution")

    try:
        staff_profile_ids = [
            r for (r,) in (await session.execute(
                select(StaffProfile.id).where(StaffProfile.user_id == user_id)
            )).all()
        ]
    except Exception:
        logger.exception("Staff profile lookup failed during data-subject resolution")

    return lead_ids, staff_profile_ids


async def collect_school_record(
    session: AsyncSession,
    user: User,
    *,
    include_clinical: bool = False,
    include_safeguarding: bool = False,
) -> Dict[str, Any]:
    """Everything the school holds about this subject.

    Both flags must reflect the CALLER's authority. When False the matching
    tables are not queried at all, so the response is byte-identical to that
    of a child who has no such records -- which is the point.
    """
    user_id = user.id
    user_uuid = getattr(user, "user_uuid", "") or ""
    email = getattr(user, "email", None)

    lead_ids, staff_profile_ids = await _resolve_linked_ids(session, user_id, email)

    specs: List[SubjectTable] = (
        list(_GENERAL) + list(_STAFF) + list(_STAFF_BY_PROFILE) + list(_LEAD)
    )
    if include_clinical:
        specs += list(_CLINICAL)
    if include_safeguarding:
        specs += list(_SAFEGUARDING_INCIDENTS)

    record: Dict[str, Any] = {}
    for spec in specs:
        rows = await _fetch(session, spec, user_id, user_uuid, lead_ids=lead_ids,
                            email=email, staff_profile_ids=staff_profile_ids)
        if rows:
            record[spec.key] = _rows_to_dicts(rows)

    return record


async def collect_parent_visible_counselling(
    session: AsyncSession, student_id: int
) -> List[Dict[str, Any]]:
    """The narrow slice of counselling a parent is designed to see.

    `CounselingSession.parent_visible_summary` exists precisely so a family
    can be told something without the clinical record being disclosed. Only
    rows explicitly flagged `share_summary_with_parent` are returned, and only
    the summary field -- never notes, never the follow-up plan.
    """
    try:
        rows = (
            await session.execute(
                select(CounselingSession).where(
                    CounselingSession.student_id == student_id,
                    CounselingSession.share_summary_with_parent == True,  # noqa: E712
                )
            )
        ).scalars().all()
    except Exception:
        logger.exception("Parent-visible counselling lookup failed")
        return []

    return [
        {
            "session_date": getattr(r, "session_date", None) and str(r.session_date),
            "summary": getattr(r, "parent_visible_summary", None),
        }
        for r in rows
        if getattr(r, "parent_visible_summary", None)
    ]


async def erase_school_record(
    session: AsyncSession,
    user: User,
    *,
    include_clinical: bool = False,
    include_safeguarding: bool = False,
) -> Dict[str, Any]:
    """Erase what may lawfully be erased; itemise what is retained and why.

    Returns `{"erased": {...}, "scrubbed": {...}, "retained": [...]}`. The
    retained list quotes a specific basis per category so a family receives a
    real answer, not "some data is retained".

    Confidential records are never erased, and when the caller lacks the
    matching authority they are not mentioned in the retained list either --
    naming them would disclose their existence to someone who cannot see them.
    """
    user_id = user.id
    user_uuid = getattr(user, "user_uuid", "") or ""
    email = getattr(user, "email", None)

    lead_ids, staff_profile_ids = await _resolve_linked_ids(session, user_id, email)

    erased: Dict[str, int] = {}
    scrubbed: Dict[str, int] = {}
    retained: List[Dict[str, Any]] = []

    specs: List[SubjectTable] = (
        list(_GENERAL) + list(_STAFF) + list(_STAFF_BY_PROFILE) + list(_LEAD)
    )
    if include_clinical:
        specs += list(_CLINICAL)
    if include_safeguarding:
        specs += list(_SAFEGUARDING_INCIDENTS)

    for spec in specs:
        rows = await _fetch(session, spec, user_id, user_uuid, lead_ids=lead_ids,
                            email=email, staff_profile_ids=staff_profile_ids)
        if not rows:
            continue

        if spec.scrub_fields:
            for row in rows:
                for field in spec.scrub_fields:
                    if hasattr(row, field):
                        setattr(row, field, _scrubbed_value(row, field))
                session.add(row)
            scrubbed[spec.key] = len(rows)
            continue

        if spec.erasable:
            col = getattr(spec.model, spec.column)
            if spec.column == "lead_id":
                stmt = sql_delete(spec.model).where(col.in_(lead_ids))
            elif spec.column == "staff_id":
                stmt = sql_delete(spec.model).where(col.in_(staff_profile_ids))
            elif spec.by_uuid:
                stmt = sql_delete(spec.model).where(col == user_uuid)
            else:
                stmt = sql_delete(spec.model).where(col == user_id)
            await session.execute(stmt)
            erased[spec.key] = len(rows)
            continue

        retained.append({
            "category": spec.key,
            "records": len(rows),
            "basis": spec.retention_basis or RETENTION_ACADEMIC,
        })

    await session.commit()
    return {"erased": erased, "scrubbed": scrubbed, "retained": retained}


def _scrubbed_value(row: Any, field: str) -> Any:
    """A well-formed placeholder, so a scrubbed row stays readable/valid."""
    if field == "email":
        return f"erased-{getattr(row, 'id', 'x')}@anonymized.example.com"
    if field == "phone":
        return ""
    return "[erased at subject request]"


async def log_data_subject_request(
    session: AsyncSession,
    *,
    subject_user_id: int,
    requested_by_user_id: Optional[int],
    requested_by_role: Optional[str],
    org_id: Optional[int],
    request_type: str,
    outcome: Dict[str, Any],
    included_confidential: bool,
) -> DataSubjectRequestLog:
    """Append one row. There is deliberately no update or delete counterpart."""
    entry = DataSubjectRequestLog(
        subject_user_id=subject_user_id,
        requested_by_user_id=requested_by_user_id,
        requested_by_role=requested_by_role,
        org_id=org_id,
        request_type=request_type,
        outcome=outcome,
        included_confidential=included_confidential,
        created_at=datetime.datetime.now(datetime.timezone.utc),
    )
    session.add(entry)
    await session.commit()
    await session.refresh(entry)
    return entry
