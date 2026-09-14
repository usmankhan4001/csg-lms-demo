import pytest
from fastapi import HTTPException
from sqlmodel.ext.asyncio.session import AsyncSession

from src.core.keycloak_auth import KeycloakUserPrincipal
from src.schemas.sms_gradebook import (
    AssessmentPlanCreate,
    BatchGradebookEntryRequest,
    GenerateReportCardDraftRequest,
    GradeInterval,
    GradebookEntryInput,
    GradingScaleCreate,
    ReportCardDraftUpdate,
)
from src.routers.sms_gradebook import (
    batch_enter_grades,
    create_assessment_plan,
    create_grading_scale,
    generate_report_card_draft_endpoint,
    get_report_card_by_id_endpoint,
    download_report_card_pdf_endpoint,
    get_student_report_card,
    list_assessment_plans,
    list_grading_scales,
    list_section_gradebook_entries,
    send_report_card_endpoint,
    update_report_card_draft_endpoint,
)
from src.services.sms import gradebook as gradebook_service
from src.services.sms.gradebook import resolve_letter_and_gpa

# Grade authoring is now role-gated AND section-scoped: a STUDENT could
# previously enter grades for any assessment plan, including their own. These
# tests exercise the grade MATH, not authorization, so they act as a school
# admin -- which bypasses the section-ownership check the way SUPER_ADMIN/
# SCHOOL_ADMIN do in `assert_owns_section_or_privileged`. Authorization itself
# is covered in test_gradebook_authorization.py.
_ADMIN = KeycloakUserPrincipal(
    sub="admin-fixture", org_id=1, campus_id=1, roles={"SCHOOL_ADMIN"}
)


def test_resolve_letter_and_gpa():
    """Test standard 4.0 GPA scale resolution."""
    assert resolve_letter_and_gpa(95.0) == ("A+", 4.0)
    assert resolve_letter_and_gpa(85.0) == ("A", 3.7)
    assert resolve_letter_and_gpa(78.0) == ("B+", 3.3)
    assert resolve_letter_and_gpa(72.0) == ("B", 3.0)
    assert resolve_letter_and_gpa(66.0) == ("C+", 2.7)
    assert resolve_letter_and_gpa(62.0) == ("C", 2.0)
    assert resolve_letter_and_gpa(55.0) == ("D", 1.0)
    assert resolve_letter_and_gpa(45.0) == ("F", 0.0)


@pytest.mark.asyncio
async def test_gradebook_and_gpa_calculation_lifecycle(db: AsyncSession):
    """Test full gradebook lifecycle: plans, grading entries, and term report card."""
    # 1. Create custom grading scale
    scale_payload = GradingScaleCreate(
        name="Custom 4.0 Scale",
        description="Standard institutional grading scale",
        intervals=[
            GradeInterval(grade="A+", min_percentage=90.0, max_percentage=100.0, gpa_point=4.0),
            GradeInterval(grade="A", min_percentage=80.0, max_percentage=89.99, gpa_point=3.7),
            GradeInterval(grade="B", min_percentage=70.0, max_percentage=79.99, gpa_point=3.0),
            GradeInterval(grade="C", min_percentage=60.0, max_percentage=69.99, gpa_point=2.0),
            GradeInterval(grade="F", min_percentage=0.0, max_percentage=59.99, gpa_point=0.0),
        ],
        is_default=True,
    )
    scale = await create_grading_scale(payload=scale_payload, session=db, principal=_ADMIN)
    assert scale.id is not None

    scales = await list_grading_scales(session=db)
    assert len(scales) == 1

    # 2. Create Assessment Plans for Course 101 (Midterm 40%, Final 60%)
    plan1 = await create_assessment_plan(
        payload=AssessmentPlanCreate(
            course_id=101,
            section_id=1,
            academic_term_id=1,
            assessment_name="Midterm Exam",
            weight_percentage=40.0,
            max_score=100.0,
        ),
        session=db, principal=_ADMIN,
    )
    plan2 = await create_assessment_plan(
        payload=AssessmentPlanCreate(
            course_id=101,
            section_id=1,
            academic_term_id=1,
            assessment_name="Final Exam",
            weight_percentage=60.0,
            max_score=100.0,
        ),
        session=db, principal=_ADMIN,
    )
    assert plan1.id is not None
    assert plan2.id is not None

    plans = await list_assessment_plans(course_id=101, session=db)
    assert len(plans) == 2

    # 3. Enter grades for Student 501
    # Midterm: 90/100 (weighted = 36)
    # Final: 80/100 (weighted = 48)
    # Course final score = 36 + 48 = 84% -> Grade A, GPA point 3.7
    await batch_enter_grades(
        payload=BatchGradebookEntryRequest(
            assessment_plan_id=plan1.id,
            entries=[GradebookEntryInput(student_id=501, raw_score=90.0, remarks="Excellent")],
            graded_by=10,
        ),
        session=db,
        principal=_ADMIN,
    )
    await batch_enter_grades(
        payload=BatchGradebookEntryRequest(
            assessment_plan_id=plan2.id,
            entries=[GradebookEntryInput(student_id=501, raw_score=80.0, remarks="Good job")],
            graded_by=10,
        ),
        session=db,
        principal=_ADMIN,
    )

    # 4. Generate Student Report Card
    report = await get_student_report_card(
        student_id=501,
        section_id=1,
        academic_term_id=1,
        session=db,
    )
    assert report.student_id == 501
    assert report.total_credits == 3.0
    assert report.cumulative_gpa == 3.7
    assert report.overall_letter_grade == "A"
    assert len(report.courses) == 1
    assert report.courses[0].total_weighted_percentage == 84.0
    assert len(report.courses[0].assessment_breakdown) == 2


@pytest.mark.asyncio
async def test_report_card_draft_to_sent_lifecycle(db: AsyncSession, monkeypatch):
    """Phase 4, Part A.4: TEACHER generates a DRAFT (GPA data + AI narrative),
    edits it, then explicitly sends it. A PARENT can only see it once SENT,
    and a sent report card is frozen against further regeneration/editing."""

    async def _fake_narrative(**kwargs):
        return "Great progress this term, especially in mathematics."

    monkeypatch.setattr(gradebook_service, "generate", _fake_narrative)

    teacher = KeycloakUserPrincipal(sub="teacher-1", org_id=1, campus_id=1, roles={"TEACHER"})
    parent = KeycloakUserPrincipal(sub="parent-1", org_id=1, campus_id=1, roles={"PARENT"})

    plan = await create_assessment_plan(
        payload=AssessmentPlanCreate(
            course_id=201,
            section_id=2,
            academic_term_id=2,
            assessment_name="Final Exam",
            weight_percentage=100.0,
            max_score=100.0,
        ),
        session=db, principal=_ADMIN,
    )
    await batch_enter_grades(
        payload=BatchGradebookEntryRequest(
            assessment_plan_id=plan.id,
            entries=[GradebookEntryInput(student_id=601, raw_score=88.0)],
        ),
        session=db,
        principal=_ADMIN,
    )

    # A non-staff caller cannot generate a report card at all.
    with pytest.raises(HTTPException) as excinfo_forbidden:
        await generate_report_card_draft_endpoint(
            student_id=601,
            payload=GenerateReportCardDraftRequest(
                section_id=2, academic_term_id=2, generate_narrative=False
            ),
            session=db,
            principal=parent,
        )
    assert excinfo_forbidden.value.status_code == 403

    # 1. Teacher generates the draft (with AI-assisted narrative).
    draft = await generate_report_card_draft_endpoint(
        student_id=601,
        payload=GenerateReportCardDraftRequest(
            section_id=2, academic_term_id=2, generate_narrative=True
        ),
        session=db,
        principal=teacher,
    )
    assert draft.status.value == "draft"
    assert draft.ai_narrative == "Great progress this term, especially in mathematics."
    assert draft.sent_at is None

    # A PARENT cannot see it yet -- it's still a draft.
    with pytest.raises(HTTPException) as excinfo_draft:
        await get_report_card_by_id_endpoint(
            report_card_id=draft.id, session=db, principal=parent
        )
    assert excinfo_draft.value.status_code == 404

    # 2. Teacher edits the draft before sending.
    edited = await update_report_card_draft_endpoint(
        report_card_id=draft.id,
        payload=ReportCardDraftUpdate(remarks="Reviewed and approved by homeroom teacher."),
        session=db,
        principal=teacher,
    )
    assert edited.remarks == "Reviewed and approved by homeroom teacher."
    assert edited.status.value == "draft"

    # 3. Teacher explicitly sends it -- no auto-send, no separate admin approval.
    sent = await send_report_card_endpoint(
        report_card_id=draft.id, session=db, principal=teacher
    )
    assert sent.status.value == "sent"
    assert sent.sent_by == "teacher-1"
    assert sent.sent_at is not None

    # 4. Now the parent CAN see it.
    parent_view = await get_report_card_by_id_endpoint(
        report_card_id=draft.id, session=db, principal=parent
    )
    assert parent_view.status.value == "sent"
    assert parent_view.ai_narrative == "Great progress this term, especially in mathematics."

    # 5. A sent report card is frozen: sending again conflicts.
    with pytest.raises(HTTPException) as excinfo_resend:
        await send_report_card_endpoint(report_card_id=draft.id, session=db, principal=teacher)
    assert excinfo_resend.value.status_code == 409

    # 6. ...and so does editing it.
    with pytest.raises(HTTPException) as excinfo_edit_sent:
        await update_report_card_draft_endpoint(
            report_card_id=draft.id,
            payload=ReportCardDraftUpdate(remarks="oops"),
            session=db,
            principal=teacher,
        )
    assert excinfo_edit_sent.value.status_code == 409

    # 7. ...and regenerating it.
    with pytest.raises(HTTPException) as excinfo_regen:
        await generate_report_card_draft_endpoint(
            student_id=601,
            payload=GenerateReportCardDraftRequest(
                section_id=2, academic_term_id=2, generate_narrative=False
            ),
            session=db,
            principal=teacher,
        )
    assert excinfo_regen.value.status_code == 409


@pytest.mark.asyncio
async def test_report_card_pdf_export(db: AsyncSession, monkeypatch):
    """M05 PDF export: a SENT report card renders to a real PDF; a DRAFT never
    does -- not even for staff, because a PDF is detachable and carries no
    further authorization once it leaves the system."""

    async def _fake_narrative(**kwargs):
        return "Consistent effort across all subjects."

    monkeypatch.setattr(gradebook_service, "generate", _fake_narrative)

    teacher = KeycloakUserPrincipal(sub="teacher-pdf", org_id=1, campus_id=1, roles={"TEACHER"})
    parent = KeycloakUserPrincipal(sub="parent-pdf", org_id=1, campus_id=1, roles={"PARENT"})

    plan = await create_assessment_plan(
        payload=AssessmentPlanCreate(
            course_id=301,
            section_id=3,
            academic_term_id=3,
            assessment_name="Final Exam",
            weight_percentage=100.0,
            max_score=100.0,
        ),
        session=db, principal=_ADMIN,
    )
    await batch_enter_grades(
        payload=BatchGradebookEntryRequest(
            assessment_plan_id=plan.id,
            entries=[GradebookEntryInput(student_id=701, raw_score=91.0)],
        ),
        session=db,
        principal=_ADMIN,
    )

    draft = await generate_report_card_draft_endpoint(
        student_id=701,
        payload=GenerateReportCardDraftRequest(
            section_id=3, academic_term_id=3, generate_narrative=True
        ),
        session=db,
        principal=teacher,
    )
    assert draft.status.value == "draft"

    # A DRAFT must not be exportable even by the teacher who owns it.
    with pytest.raises(HTTPException) as excinfo_draft_pdf:
        await download_report_card_pdf_endpoint(
            report_card_id=draft.id, session=db, principal=teacher
        )
    assert excinfo_draft_pdf.value.status_code == 409

    # A parent cannot even see the draft exists.
    with pytest.raises(HTTPException) as excinfo_parent_draft:
        await download_report_card_pdf_endpoint(
            report_card_id=draft.id, session=db, principal=parent
        )
    assert excinfo_parent_draft.value.status_code == 404

    await send_report_card_endpoint(report_card_id=draft.id, session=db, principal=teacher)

    # Once SENT, it renders a genuine PDF for the parent.
    response = await download_report_card_pdf_endpoint(
        report_card_id=draft.id, session=db, principal=parent
    )
    assert response.status_code == 200
    assert response.media_type == "application/pdf"
    assert response.body.startswith(b"%PDF")
    assert "attachment" in response.headers["content-disposition"]
    assert "report-card-701-term-3.pdf" in response.headers["content-disposition"]

    # The PDF must agree with the JSON API rather than recomputing grades.
    # Extract real text with pypdf (already a dependency) rather than scanning
    # raw bytes -- reportlab compresses content streams, so the rendered text
    # is not literally present in the file.
    from io import BytesIO

    from pypdf import PdfReader

    json_view = await get_report_card_by_id_endpoint(
        report_card_id=draft.id, session=db, principal=parent
    )
    pdf_text = "".join(page.extract_text() or "" for page in PdfReader(BytesIO(response.body)).pages)
    assert f"{json_view.cumulative_gpa:.2f}" in pdf_text
    assert str(json_view.student_id) in pdf_text
    if json_view.overall_letter_grade:
        assert json_view.overall_letter_grade in pdf_text


@pytest.mark.asyncio
async def test_report_card_pdf_missing_returns_404(db: AsyncSession):
    teacher = KeycloakUserPrincipal(sub="teacher-404", org_id=1, campus_id=1, roles={"TEACHER"})
    with pytest.raises(HTTPException) as excinfo:
        await download_report_card_pdf_endpoint(
            report_card_id=99999, session=db, principal=teacher
        )
    assert excinfo.value.status_code == 404


# ---------------------------------------------------------------------------
# GET /entries -- reading saved marks back (closes the gap that forced the
# grade-entry matrix to start blank on every mount)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_saved_entries_read_back_and_absence_is_not_zero(db: AsyncSession):
    """Entries read back match what was written, and a student who was never
    marked is ABSENT from the response rather than returned as a zero.

    That distinction is the whole point: on a report card "not marked yet" and
    "scored 0" mean opposite things, and this codebase has repeatedly had to
    tear out endpoints that defaulted missing academic data to a value.
    """
    teacher = KeycloakUserPrincipal(
        sub="teacher-entries", org_id=1, campus_id=1, roles={"SCHOOL_ADMIN"}
    )

    plan = await create_assessment_plan(
        payload=AssessmentPlanCreate(
            course_id=701,
            section_id=70,
            academic_term_id=70,
            assessment_name="Unit Test",
            weight_percentage=100.0,
            max_score=50.0,
        ),
        session=db, principal=_ADMIN,
    )

    # Student 7001 is marked; 7002 deliberately is not, and 7003 genuinely
    # scored zero -- the two must remain distinguishable.
    await batch_enter_grades(
        payload=BatchGradebookEntryRequest(
            assessment_plan_id=plan.id,
            entries=[
                GradebookEntryInput(student_id=7001, raw_score=45.0),
                GradebookEntryInput(student_id=7003, raw_score=0.0),
            ],
            graded_by=99,
        ),
        session=db,
        principal=_ADMIN,
    )

    result = await list_section_gradebook_entries(
        section_id=70, session=db, principal=teacher
    )

    assert result.section_id == 70
    assert plan.id in result.assessment_plan_ids

    by_student = {e.student_id: e for e in result.entries}
    # Written value round-trips, including the server-computed fields.
    assert by_student[7001].raw_score == 45.0
    assert by_student[7001].max_score == 50.0
    assert by_student[7001].letter_grade is not None

    # A real zero is present and is genuinely 0 -- not conflated with absence.
    assert 7003 in by_student
    assert by_student[7003].raw_score == 0.0

    # The unmarked student has NO row at all. No zero-filled placeholder.
    assert 7002 not in by_student


@pytest.mark.asyncio
async def test_entries_read_is_scoped_to_sections_you_teach(db: AsyncSession):
    """A teacher who does not own the section is denied, so the endpoint
    cannot be used to read another class's marks."""
    outsider = KeycloakUserPrincipal(
        sub="teacher-outsider",
        org_id=1,
        campus_id=1,
        roles={"TEACHER"},
        raw_claims={"lh_user_id": 424242},
    )

    with pytest.raises(HTTPException) as exc:
        await list_section_gradebook_entries(
            section_id=70, session=db, principal=outsider
        )

    assert exc.value.status_code == 403
    # Message is localised to grades, not the helper's attendance wording.
    assert "grades" in str(exc.value.detail).lower()


@pytest.mark.asyncio
async def test_student_report_card_exposes_its_persisted_id(db: AsyncSession):
    """The live-computed report card now carries the id/status of the row it
    was upserted into, so send and PDF are reachable for a card generated in
    an earlier session -- previously the only source of an id was the draft
    POST response, and a previously-sent card showed as 'not generated yet'."""
    plan = await create_assessment_plan(
        payload=AssessmentPlanCreate(
            course_id=801,
            section_id=80,
            academic_term_id=80,
            assessment_name="Final",
            weight_percentage=100.0,
            max_score=100.0,
        ),
        session=db, principal=_ADMIN,
    )
    await batch_enter_grades(
        payload=BatchGradebookEntryRequest(
            assessment_plan_id=plan.id,
            entries=[GradebookEntryInput(student_id=8001, raw_score=88.0)],
            graded_by=1,
        ),
        session=db,
        principal=_ADMIN,
    )

    report = await get_student_report_card(
        student_id=8001, section_id=80, academic_term_id=80, session=db
    )

    assert report.report_card_id is not None
    # Lowercase on the wire -- the frontend union previously said 'DRAFT'/'SENT'
    # and could never match, which made Send and PDF unreachable in the UI.
    assert report.report_card_status.value == "draft"

    # The id actually resolves to the persisted record.
    fetched = await get_report_card_by_id_endpoint(
        report_card_id=report.report_card_id,
        session=db,
        principal=KeycloakUserPrincipal(
            sub="teacher-rc", org_id=1, campus_id=1, roles={"TEACHER"}
        ),
    )
    assert fetched.id == report.report_card_id
    assert fetched.student_id == 8001


# ---------------------------------------------------------------------------
# No-data must never be reported as a measured grade.
#
# `generate_student_term_report_card` used to compute
# `total_credits > 0 else 0.0`, and 0.0 fell through the letter chain to "F",
# which was then UPSERTED onto TermReportCard -- so a newly enrolled student
# with nothing marked showed a persisted F to their parents. Underneath it,
# an unmarked assessment was scored as 0, and a course with no plans still
# contributed 0.0 quality points over 3.0 credits. Three separate ways for
# missing data to become a real-looking number.
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_student_with_no_marks_gets_no_grade_not_an_f(db: AsyncSession):
    report = await gradebook_service.generate_student_term_report_card(
        session=db, student_id=90210, section_id=77, academic_term_id=77
    )

    assert report.cumulative_gpa is None, "a student with no marks has no GPA, not 0.0"
    assert report.overall_letter_grade is None, "no marks is not an F"
    assert report.total_credits == 0.0


@pytest.mark.asyncio
async def test_unmarked_assessment_is_excluded_not_scored_zero(db: AsyncSession):
    """A teacher who has entered only the first quiz must not see the class
    failing on the strength of work nobody has marked yet."""
    plan_marked = await create_assessment_plan(
        payload=AssessmentPlanCreate(
            course_id=4242,
            section_id=4242,
            academic_term_id=4242,
            assessment_name="Quiz 1",
            weight_percentage=50.0,
            max_score=100.0,
        ),
        session=db,
        principal=_ADMIN,
    )
    # A second plan, deliberately left unmarked.
    await create_assessment_plan(
        payload=AssessmentPlanCreate(
            course_id=4242,
            section_id=4242,
            academic_term_id=4242,
            assessment_name="Quiz 2 (not marked yet)",
            weight_percentage=50.0,
            max_score=100.0,
        ),
        session=db,
        principal=_ADMIN,
    )
    await batch_enter_grades(
        payload=BatchGradebookEntryRequest(
            assessment_plan_id=plan_marked.id,
            entries=[GradebookEntryInput(student_id=4242, raw_score=90.0)],
        ),
        session=db,
        principal=_ADMIN,
    )

    summary = await gradebook_service.calculate_student_course_summary(
        session=db, student_id=4242, course_id=4242, academic_term_id=4242
    )

    assert summary.has_grades is True
    # 90% on the only marked assessment -- NOT 45% (90 averaged against a
    # fabricated 0 for the unmarked half).
    assert summary.total_weighted_percentage == pytest.approx(90.0, abs=0.01)
    unmarked = [b for b in summary.assessment_breakdown if b.get("graded") is False]
    assert len(unmarked) == 1
    assert unmarked[0]["raw_score"] is None, "unmarked work must read as absent, not 0"
