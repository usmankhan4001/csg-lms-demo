"""
Registry of events that webhook endpoints can subscribe to.

Each event defines:
- ``category``      – UI grouping label.
- ``description``   – Human-readable explanation shown in the UI.
- ``data_schema``   – **The** definition of the ``data`` field sent in the
  webhook payload.  Keys are field names; values are either a type hint
  string (``"string"``, ``"integer"``, ``"boolean"``, ``"list[string]"``,
  ``"list[integer]"`` …) or a nested dict for object fields.

``data_schema`` is the single source of truth:
  1. The ``/webhooks/events`` endpoint returns it so the UI shows the real
     payload structure without any hardcoded copy.
  2. ``validate_event_data()`` checks dispatched payloads against it at
     runtime so drift is caught immediately.
"""

import logging

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Event registry
# ---------------------------------------------------------------------------

WEBHOOK_EVENTS: dict[str, dict] = {
    # ── System ───────────────────────────────────────────────────────
    "ping": {
        "category": "System",
        "description": "Test event sent to verify endpoint connectivity",
        "data_schema": {
            "message": "string",
        },
    },
    # ── Learning progress ────────────────────────────────────────────
    "course_completed": {
        "category": "Learning Progress",
        "description": "Triggered when a user completes all activities in a course",
        "data_schema": {
            "user": {"user_uuid": "string", "email": "string", "username": "string"},
            "course": {"course_uuid": "string", "name": "string"},
        },
    },
    "course_enrolled": {
        "category": "Learning Progress",
        "description": "Triggered when a user enrolls in a course",
        "data_schema": {
            "user": {"user_uuid": "string", "email": "string", "username": "string"},
            "course": {"course_uuid": "string", "name": "string"},
        },
    },
    "activity_completed": {
        "category": "Learning Progress",
        "description": "Triggered when a user completes an activity",
        "data_schema": {
            "user": {"user_uuid": "string", "email": "string", "username": "string"},
            "activity": {"activity_uuid": "string", "activity_type": "string"},
            "course": {"course_uuid": "string", "name": "string"},
        },
    },
    "assignment_submitted": {
        "category": "Learning Progress",
        "description": "Triggered when a user submits an assignment",
        "data_schema": {
            "user": {"user_uuid": "string", "email": "string", "username": "string"},
            "assignment": {"assignment_uuid": "string"},
            "course": {"course_uuid": "string", "name": "string"},
            "attempt_number": "integer",
        },
    },
    "assignment_graded": {
        "category": "Learning Progress",
        "description": "Triggered when an assignment submission is graded (by an instructor or auto-grading)",
        "data_schema": {
            "user_id": "integer",
            "assignment_uuid": "string",
            "course_uuid": "string",
            "grade": "integer",
            "max_grade": "integer",
            "percentage": "number",
            "display_grade": "string",
            "letter_grade": "string",
            "points_summary": "string",
            "passed": "boolean",
            "grading_type": "string",
            "overall_feedback": "string",
            "auto_graded": "boolean",
        },
    },
    "certificate_claimed": {
        "category": "Learning Progress",
        "description": "Triggered when a user receives a certificate",
        "data_schema": {
            "user": {"user_uuid": "string", "email": "string", "username": "string"},
            "course": {"course_uuid": "string", "name": "string"},
            "certificate": {"user_certification_uuid": "string"},
        },
    },
    "certificate_revoked": {
        "category": "Learning Progress",
        "description": (
            "Triggered when a previously issued certificate is revoked (e.g. a "
            "gating assignment was regraded below the pass threshold, or the "
            "learner reset/retried a completed assignment)"
        ),
        "data_schema": {
            "user": {"user_uuid": "string", "email": "string", "username": "string"},
            "course": {"course_uuid": "string", "name": "string"},
            "certificate": {"user_certification_uuid": "string"},
            "reason": "string",
        },
    },
    # ── User & access ────────────────────────────────────────────────
    "user_signed_up": {
        "category": "User & Access",
        "description": "Triggered when a new user signs up for the organization",
        "data_schema": {
            "user": {
                "user_uuid": "string",
                "email": "string",
                "username": "string",
                "first_name": "string",
                "last_name": "string",
            },
            "signup_method": "string",
        },
    },
    "user_email_verified": {
        "category": "User & Access",
        "description": "Triggered when a user verifies their email address",
        "data_schema": {
            "user_uuid": "string",
            "email": "string",
        },
    },
    "user_role_changed": {
        "category": "User & Access",
        "description": "Triggered when a user's role is changed in the organization",
        "data_schema": {
            "user_id": "integer",
            "org_id": "integer",
            "new_role_uuid": "string",
        },
    },
    "user_invited_to_org": {
        "category": "User & Access",
        "description": "Triggered when users are invited to the organization",
        "data_schema": {
            "org_id": "integer",
            "emails": "list[string]",
            "invite_code_uuid": "string",
            "invited_by": "string",
        },
    },
    "user_removed_from_org": {
        "category": "User & Access",
        "description": "Triggered when a user is removed from the organization",
        "data_schema": {
            "user_id": "integer",
            "org_id": "integer",
        },
    },
    # ── Course lifecycle ─────────────────────────────────────────────
    "course_created": {
        "category": "Course Lifecycle",
        "description": "Triggered when a new course is created",
        "data_schema": {
            "course_uuid": "string",
            "name": "string",
            "org_id": "integer",
        },
    },
    "course_published": {
        "category": "Course Lifecycle",
        "description": "Triggered when a course is published or unpublished",
        "data_schema": {
            "course_uuid": "string",
            "name": "string",
            "published": "boolean",
        },
    },
    "course_deleted": {
        "category": "Course Lifecycle",
        "description": "Triggered when a course is deleted",
        "data_schema": {
            "course_uuid": "string",
            "name": "string",
        },
    },
    "course_update_published": {
        "category": "Course Lifecycle",
        "description": "Triggered when an announcement is posted to a course",
        "data_schema": {
            "courseupdate_uuid": "string",
            "course_uuid": "string",
        },
    },
    # ── Content management ───────────────────────────────────────────
    "activity_version_created": {
        "category": "Content Management",
        "description": "Triggered when an activity version snapshot is created",
        "data_schema": {
            "activity_id": "integer",
            "version_number": "integer",
            "created_by_id": "integer",
        },
    },
    "activity_version_restored": {
        "category": "Content Management",
        "description": "Triggered when an activity is restored to a previous version",
        "data_schema": {
            "activity_uuid": "string",
            "restored_version_number": "integer",
            "new_version_number": "integer",
        },
    },
    "course_contributor_added": {
        "category": "Content Management",
        "description": "Triggered when contributors are added to a course",
        "data_schema": {
            "course_uuid": "string",
            "contributors": "list[object]",
        },
    },
    "course_contributor_removed": {
        "category": "Content Management",
        "description": "Triggered when contributors are removed from a course",
        "data_schema": {
            "course_uuid": "string",
            "contributors": "list[object]",
        },
    },
    "folder_created": {
        "category": "Content Management",
        "description": "Triggered when a new folder is created",
        "data_schema": {
            "folder_uuid": "string",
            "name": "string",
        },
    },
    "folder_updated": {
        "category": "Content Management",
        "description": "Triggered when a folder is updated",
        "data_schema": {
            "folder_uuid": "string",
            "name": "string",
        },
    },
    "folder_deleted": {
        "category": "Content Management",
        "description": "Triggered when a folder is deleted",
        "data_schema": {
            "folder_uuid": "string",
            "name": "string",
        },
    },
    "podcast_episode_created": {
        "category": "Content Management",
        "description": "Triggered when a new podcast episode is added",
        "data_schema": {
            "episode_uuid": "string",
            "podcast_uuid": "string",
            "title": "string",
            "episode_number": "integer",
        },
    },
    # ── Collaboration ────────────────────────────────────────────────
    "board_created": {
        "category": "Collaboration",
        "description": "Triggered when a new whiteboard is created",
        "data_schema": {
            "board_uuid": "string",
            "name": "string",
            "created_by": "integer",
        },
    },
    "board_member_added": {
        "category": "Collaboration",
        "description": "Triggered when a member is added to a whiteboard",
        "data_schema": {
            "board_uuid": "string",
            "user_id": "integer",
            "role": "string",
        },
    },
    "playground_created": {
        "category": "Collaboration",
        "description": "Triggered when a new playground is created",
        "data_schema": {
            "playground_uuid": "string",
            "name": "string",
            "created_by": "integer",
        },
    },
    # ── Community ────────────────────────────────────────────────────
    "discussion_posted": {
        "category": "Community",
        "description": "Triggered when a user creates a discussion",
        "data_schema": {
            "user": {"user_uuid": "string", "email": "string", "username": "string"},
            "discussion": {"discussion_uuid": "string", "title": "string"},
            "community": {"community_uuid": "string"},
        },
    },
    "comment_created": {
        "category": "Community",
        "description": "Triggered when a user posts a comment on a discussion",
        "data_schema": {
            "user": {"user_uuid": "string", "email": "string", "username": "string"},
            "comment": {"comment_uuid": "string"},
            "discussion": {"discussion_uuid": "string", "title": "string"},
            "community": {"community_uuid": "string"},
        },
    },
    "discussion_pinned": {
        "category": "Community",
        "description": "Triggered when a discussion is pinned or unpinned",
        "data_schema": {
            "discussion_uuid": "string",
            "title": "string",
            "is_pinned": "boolean",
            "community_uuid": "string",
        },
    },
    "discussion_locked": {
        "category": "Community",
        "description": "Triggered when a discussion is locked or unlocked",
        "data_schema": {
            "discussion_uuid": "string",
            "title": "string",
            "is_locked": "boolean",
            "community_uuid": "string",
        },
    },
    "discussion_vote_cast": {
        "category": "Community",
        "description": "Triggered when a user upvotes a discussion",
        "data_schema": {
            "discussion_uuid": "string",
            "user_id": "integer",
            "upvote_count": "integer",
        },
    },
    # ── Groups ───────────────────────────────────────────────────────
    "usergroup_created": {
        "category": "Groups",
        "description": "Triggered when a new user group is created",
        "data_schema": {
            "usergroup_uuid": "string",
            "name": "string",
        },
    },
    "usergroup_deleted": {
        "category": "Groups",
        "description": "Triggered when a user group is deleted",
        "data_schema": {
            "usergroup_uuid": "string",
            "name": "string",
        },
    },
    "usergroup_users_added": {
        "category": "Groups",
        "description": "Triggered when users are added to a user group",
        "data_schema": {
            "usergroup_id": "integer",
            "usergroup_uuid": "string",
            "user_ids": "list[integer]",
        },
    },
    "usergroup_resources_added": {
        "category": "Groups",
        "description": "Triggered when resources are assigned to a user group",
        "data_schema": {
            "usergroup_id": "integer",
            "usergroup_uuid": "string",
            "resource_uuids": "list[string]",
        },
    },
    # ── Subscriptions ────────────────────────────────────────────────
    "pack_activated": {
        "category": "Subscriptions",
        "description": "Triggered when a subscription pack is activated",
        "data_schema": {
            "pack_id": "string",
            "pack_type": "string",
            "quantity": "integer",
            "platform_subscription_id": "string",
        },
    },
    "pack_deactivated": {
        "category": "Subscriptions",
        "description": "Triggered when a subscription pack is cancelled",
        "data_schema": {
            "pack_id": "string",
            "pack_type": "string",
            "platform_subscription_id": "string",
        },
    },
    # ── Org administration ───────────────────────────────────────────
    "org_signup_method_changed": {
        "category": "Organization",
        "description": "Triggered when the organization signup method is changed",
        "data_schema": {
            "signup_mechanism": "string",
        },
    },
    "org_ai_config_changed": {
        "category": "Organization",
        "description": "Triggered when the organization AI configuration is updated",
        "data_schema": {
            "ai_enabled": "boolean",
            "copilot_enabled": "boolean",
        },
    },
    "org_payments_config_changed": {
        "category": "Organization",
        "description": "Triggered when the organization payments configuration is updated",
        "data_schema": {
            "payments_enabled": "boolean",
        },
    },

    # ── Admissions & RevOps ───────────────────────────────────────────
    "lead.created": {
        "category": "Admissions & RevOps",
        "description": "Triggered when a new prospective student inquiry is received",
        "data_schema": {
            "lead_id": "integer",
            "first_name": "string",
            "last_name": "string",
            "parent_name": "string",
            "email": "string",
            "phone": "string",
            "target_grade": "integer",
            "target_academic_year": "string",
            "campus_id": "integer",
            "lead_source": "string",
            "stage": "string",
        },
    },
    "lead.stage_changed": {
        "category": "Admissions & RevOps",
        "description": "Triggered when an admissions lead progresses to a new pipeline stage",
        "data_schema": {
            "lead_id": "integer",
            "previous_stage": "string",
            "new_stage": "string",
            "bant_score": "number",
            "priority_tier": "string",
        },
    },
    "lead.matriculated": {
        "category": "Admissions & RevOps",
        "description": "Triggered when an admissions lead completes the 1-Click Matriculation Handshake",
        "data_schema": {
            "lead_id": "integer",
            "student_user_id": "integer",
            "student_email": "string",
            "parent_user_id": "integer",
            "parent_email": "string",
            "campus_id": "integer",
            "section_id": "integer",
            "section_name": "string",
            "enrollment_date": "string",
            "initial_voucher_id": "integer",
            "total_tuition_due": "number",
        },
    },

    # ── Academic Structure & Enrollment ──────────────────────────────
    "section.created": {
        "category": "Academic",
        "description": "Triggered when a new class section is provisioned",
        "data_schema": {
            "section_id": "integer",
            "campus_id": "integer",
            "name": "string",
            "grade_level": "integer",
            "academic_year_id": "integer",
            "capacity": "integer",
        },
    },
    "student.enrolled": {
        "category": "Academic",
        "description": "Triggered when a student is formally enrolled into a class section",
        "data_schema": {
            "student_id": "integer",
            "section_id": "integer",
            "section_name": "string",
            "academic_year": "string",
            "roll_number": "string",
        },
    },
    "student.transferred": {
        "category": "Academic",
        "description": "Triggered when a student transfers between sections or campuses",
        "data_schema": {
            "student_id": "integer",
            "from_section_id": "integer",
            "to_section_id": "integer",
            "transfer_date": "string",
        },
    },
    "timetable.published": {
        "category": "Academic",
        "description": "Triggered when an academic timetable schedule is published or refreshed",
        "data_schema": {
            "term_id": "integer",
            "campus_id": "integer",
            "total_slots": "integer",
            "published_at": "string",
        },
    },

    # ── Biometric Attendance & Truancy ────────────────────────────────
    "attendance.recorded": {
        "category": "Attendance",
        "description": "Triggered when daily or period attendance is posted for a cohort",
        "data_schema": {
            "date": "string",
            "campus_id": "integer",
            "section_id": "integer",
            "period_number": "integer",
            "total_students": "integer",
            "present_count": "integer",
            "absent_count": "integer",
            "tardy_count": "integer",
        },
    },
    "attendance.truancy_alert": {
        "category": "Attendance",
        "description": "Triggered when a student breaches consecutive unexcused absence thresholds",
        "data_schema": {
            "student_id": "integer",
            "student_name": "string",
            "section_name": "string",
            "consecutive_unexcused_days": "integer",
            "term_attendance_rate": "number",
        },
    },
    "attendance.excuse_submitted": {
        "category": "Attendance",
        "description": "Triggered when a parent submits an absence excuse note",
        "data_schema": {
            "student_id": "integer",
            "parent_id": "integer",
            "date_range": "string",
            "reason": "string",
        },
    },
    "attendance.excuse_approved": {
        "category": "Attendance",
        "description": "Triggered when an absence excuse note is approved by administration",
        "data_schema": {
            "student_id": "integer",
            "excuse_id": "integer",
            "approved_by_user_id": "integer",
        },
    },

    # ── Assessment, SpeedGrader & Gradebook ───────────────────────────
    "coursework.graded": {
        "category": "Assessment",
        "description": "Triggered when coursework is evaluated in SpeedGrader with analytical rubrics",
        "data_schema": {
            "gradebook_entry_id": "integer",
            "student_id": "integer",
            "course_id": "integer",
            "course_name": "string",
            "section_id": "integer",
            "assessment_title": "string",
            "score_obtained": "number",
            "max_score": "number",
            "percentage": "number",
            "graded_by_user_id": "integer",
        },
    },
    "speedgrader.evaluated": {
        "category": "Assessment",
        "description": "Triggered when SpeedGrader records multi-criteria rubric points for a submission",
        "data_schema": {
            "submission_id": "string",
            "student_id": "integer",
            "rubric_total": "number",
            "rubric_max": "number",
            "graded_by_user_id": "integer",
        },
    },
    "report_card.published": {
        "category": "Assessment",
        "description": "Triggered when official Term Report Cards and cumulative GPAs are published",
        "data_schema": {
            "student_id": "integer",
            "section_id": "integer",
            "term_id": "integer",
            "gpa": "number",
            "rank_in_section": "integer",
            "attendance_percentage": "number",
            "published_at": "string",
        },
    },

    # ── CBT Examinations ──────────────────────────────────────────────
    "exam.scheduled": {
        "category": "Examinations",
        "description": "Triggered when an official examination sitting schedule is posted",
        "data_schema": {
            "exam_id": "integer",
            "title": "string",
            "course_id": "integer",
            "exam_date": "string",
            "start_time": "string",
            "total_candidates": "integer",
        },
    },
    "exam.submitted": {
        "category": "Examinations",
        "description": "Triggered when a student finalizes and submits a CBT examination",
        "data_schema": {
            "exam_id": "integer",
            "student_id": "integer",
            "submission_timestamp": "string",
            "raw_score": "number",
            "percentage": "number",
        },
    },
    "exam.psychometrics_calculated": {
        "category": "Examinations",
        "description": "Triggered when 2PL Item Response Theory & Cronbach alpha are compiled for an exam",
        "data_schema": {
            "exam_id": "integer",
            "exam_title": "string",
            "cohort_size": "integer",
            "mean_score": "number",
            "cronbach_alpha": "number",
            "flagged_items_count": "integer",
        },
    },

    # ── Tuition Fees & Billing ────────────────────────────────────────
    "fee.voucher_created": {
        "category": "Financials",
        "description": "Triggered when a tuition or services invoice voucher is issued to a student",
        "data_schema": {
            "voucher_id": "integer",
            "voucher_number": "string",
            "student_id": "integer",
            "total_amount": "number",
            "due_date": "string",
            "academic_term": "string",
        },
    },
    "fee.payment_received": {
        "category": "Financials",
        "description": "Triggered when a fee payment is successfully processed and receipted",
        "data_schema": {
            "voucher_id": "integer",
            "voucher_number": "string",
            "student_id": "integer",
            "amount_paid": "number",
            "payment_method": "string",
            "transaction_reference": "string",
            "remaining_balance": "number",
            "status": "string",
        },
    },
    "fee.overdue": {
        "category": "Financials",
        "description": "Triggered when a student fee voucher passes its payment deadline",
        "data_schema": {
            "voucher_id": "integer",
            "student_id": "integer",
            "days_overdue": "integer",
            "balance_due": "number",
        },
    },

    # ── General Ledger & Payroll ──────────────────────────────────────
    "journal.posted": {
        "category": "Financials",
        "description": "Triggered when a balanced double-entry General Ledger journal entry is posted",
        "data_schema": {
            "journal_id": "integer",
            "voucher_number": "string",
            "posting_date": "string",
            "total_debit": "number",
            "total_credit": "number",
            "posted_by_user_id": "integer",
        },
    },
    "payroll.processed": {
        "category": "Financials",
        "description": "Triggered when monthly faculty/staff payroll calculations are prepared",
        "data_schema": {
            "payroll_period": "string",
            "total_employees": "integer",
            "gross_amount": "number",
            "tax_withheld": "number",
            "net_disbursement": "number",
        },
    },
    "payroll.approved": {
        "category": "Financials",
        "description": "Triggered when the Bursar/Executive Headmaster signs off on payroll disbursement",
        "data_schema": {
            "payroll_period": "string",
            "total_employees": "integer",
            "gross_disbursement": "number",
            "net_disbursement": "number",
            "approved_by_user_id": "integer",
        },
    },

    # ── Pastoral Care & Crisis Safety ─────────────────────────────────
    "crisis.escalated": {
        "category": "Pastoral & Safety",
        "description": "Triggered when urgent mental health or safety risk is detected (<=120s SLA)",
        "data_schema": {
            "alert_id": "string",
            "severity": "string",
            "student_id": "integer",
            "campus_id": "integer",
            "detected_source": "string",
            "alert_timestamp": "string",
        },
    },
    "discipline.incident_logged": {
        "category": "Pastoral & Safety",
        "description": "Triggered when a behavioral commendation or disciplinary incident is recorded",
        "data_schema": {
            "incident_id": "integer",
            "student_id": "integer",
            "incident_type": "string",
            "severity": "string",
            "logged_by_user_id": "integer",
        },
    },

    # ── Accreditation & Compliance ────────────────────────────────────
    "cognia.evidence_submitted": {
        "category": "Accreditation",
        "description": "Triggered when a standard artifact is uploaded to the Cognia evidence locker",
        "data_schema": {
            "evidence_id": "integer",
            "standard_code": "string",
            "title": "string",
            "academic_year": "string",
            "submitted_by_user_id": "integer",
        },
    },
    "cognia.evidence_verified": {
        "category": "Accreditation",
        "description": "Triggered when Cognia compliance evidence is certified with SHA-256 validation",
        "data_schema": {
            "evidence_id": "integer",
            "standard_code": "string",
            "performance_score": "number",
            "verified_by_user_id": "integer",
            "current_ami_index": "number",
        },
    },
    "cognia.ami_updated": {
        "category": "Accreditation",
        "description": "Triggered when institutional Accreditation Maturity Index (AMI) is recalculated",
        "data_schema": {
            "academic_year": "string",
            "ami_index": "number",
            "total_verified_standards": "integer",
        },
    },
}



# ---------------------------------------------------------------------------
# Runtime validation
# ---------------------------------------------------------------------------


def _schema_keys(schema: dict) -> set[str]:
    """Return the set of top-level keys expected by a schema dict."""
    return set(schema.keys())


def validate_event_data(event_name: str, data: dict) -> None:
    """
    Check that *data* matches the ``data_schema`` registered for *event_name*.

    Logs a warning on mismatch — never raises, so webhook delivery is not
    blocked by a schema drift bug.
    """
    event = WEBHOOK_EVENTS.get(event_name)
    if event is None:
        logger.warning("Webhook event %r is not registered in WEBHOOK_EVENTS", event_name)
        return

    schema = event.get("data_schema")
    if schema is None:
        return

    expected = _schema_keys(schema)
    actual = set(data.keys())

    missing = expected - actual
    extra = actual - expected

    if missing:
        logger.warning(
            "Webhook %r payload is missing keys defined in data_schema: %s",
            event_name,
            sorted(missing),
        )
    if extra:
        logger.warning(
            "Webhook %r payload has keys not defined in data_schema: %s",
            event_name,
            sorted(extra),
        )
