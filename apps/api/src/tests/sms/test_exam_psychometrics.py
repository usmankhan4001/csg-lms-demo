"""
Unit tests for the IRT 2PL Psychometrics & Reliability Engine (M04 / Phase 2 CBT).
"""

import math
import random
import pytest

from src.schemas.sms_exam import ExamPsychometricsReport
from src.services.sms.exam_psychometrics import (
    calculate_cronbach_alpha,
    calculate_irt_2pl_psychometrics,
    categorize_difficulty,
    categorize_discrimination,
    estimate_irt_2pl,
    interpret_cronbach_alpha,
    synthesize_response_matrix_from_scores,
)


def test_categorize_discrimination():
    # Low discrimination (< 0.20) must be flagged
    cat, is_flagged, reason = categorize_discrimination(0.12)
    assert is_flagged is True
    assert "Very Poor" in cat
    assert reason is not None
    assert "0.12" in reason

    # Threshold 0.20
    cat, is_flagged, reason = categorize_discrimination(0.20)
    assert is_flagged is False
    assert reason is None

    # Good discrimination
    cat, is_flagged, reason = categorize_discrimination(1.45)
    assert is_flagged is False
    assert "High" in cat


def test_categorize_difficulty():
    assert categorize_difficulty(-2.5) == "Very Easy"
    assert categorize_difficulty(-1.0) == "Easy"
    assert categorize_difficulty(0.0) == "Moderate"
    assert categorize_difficulty(1.2) == "Hard"
    assert categorize_difficulty(2.5) == "Very Hard"


def test_cronbach_alpha_calculation():
    # Identical responses (no variance in total or items)
    mat_zero = [[0] * 5 for _ in range(10)]
    assert calculate_cronbach_alpha(mat_zero) == 0.0

    # Strong positive internal consistency test
    rng = random.Random(42)
    thetas = [-2.5 + (5.0 * i / 59) for i in range(60)]
    betas = [-1.5 + (3.0 * j / 7) for j in range(8)]
    alphas = [1.5] * 8

    responses = []
    for th in thetas:
        row = []
        for j in range(8):
            z = alphas[j] * (th - betas[j])
            p = 1.0 / (1.0 + math.exp(-max(-30.0, min(30.0, z))))
            row.append(1 if (rng.random() < p) else 0)
        responses.append(row)

    alpha_val = calculate_cronbach_alpha(responses)
    assert alpha_val > 0.6  # Demonstrates strong positive internal consistency


def test_irt_2pl_estimation_and_flagging():
    # 80 students, 6 items. Force item 2 to have low discrimination
    rng = random.Random(101)
    thetas_true = [rng.gauss(0, 1) for _ in range(80)]
    
    betas_true = [-1.5, 0.0, 1.0, -0.5, 0.8, 0.0]
    alphas_true = [1.4, 0.05, 1.6, 1.2, 1.3, 0.9]
    
    X = []
    for i in range(80):
        row = []
        th = thetas_true[i]
        for j in range(6):
            z = alphas_true[j] * (th - betas_true[j])
            p = 1.0 / (1.0 + math.exp(-max(-30.0, min(30.0, z))))
            row.append(1 if (rng.random() < p) else 0)
        X.append(row)
    
    report: ExamPsychometricsReport = calculate_irt_2pl_psychometrics(
        response_matrix=X,
        exam_id=42,
        exam_title="Physics Midterm CBT",
    )

    assert report.exam_id == 42
    assert report.total_examinees == 80
    assert report.total_items == 6
    assert len(report.items) == 6
    
    # Item 2 has alpha_true = 0.05, so estimated alpha should be low and flagged
    item_2 = report.items[1]
    assert item_2.discrimination_alpha < 0.30
    if item_2.discrimination_alpha < 0.20:
        assert item_2.is_low_discrimination is True
        assert item_2.flag_reason is not None
        assert report.items_flagged_count >= 1

    # Check ICC curve points
    assert len(item_2.icc_curve) == 25
    assert item_2.icc_curve[0].theta == -3.0
    assert item_2.icc_curve[-1].theta == 3.0


def test_synthesize_response_matrix():
    scores = [10.0, 20.0, 45.0, 80.0, 95.0]
    matrix = synthesize_response_matrix_from_scores(scores, total_marks=100.0, num_items=5)
    assert len(matrix) == 5
    assert len(matrix[0]) == 5
    for row in matrix:
        for val in row:
            assert val in (0, 1)


import datetime
from sqlmodel.ext.asyncio.session import AsyncSession
from src.db.sms_exam import Exam, ExamResult, ExamAttendanceStatus
from src.services.sms.exam_psychometrics import get_exam_psychometrics
from src.core.keycloak_auth import KeycloakUserPrincipal
from src.routers.sms_exam import get_psychometrics

_TEACHER = KeycloakUserPrincipal(
    sub="teacher-uuid", org_id=1, campus_id=1, roles={"TEACHER"}
)


@pytest.mark.asyncio
async def test_get_exam_psychometrics_service(db: AsyncSession):
    exam = Exam(
        campus_id=1,
        academic_term_id=1,
        course_id=101,
        title="Mathematics CBT Final",
        exam_date=datetime.date.today(),
        total_marks=100.0,
        pass_marks=40.0,
    )
    db.add(exam)
    await db.commit()
    await db.refresh(exam)

    # Add 10 students with various scores
    for i, score in enumerate([30.0, 45.0, 60.0, 75.0, 90.0, 85.0, 70.0, 55.0, 40.0, 95.0]):
        res = ExamResult(
            exam_id=exam.id,
            student_id=100 + i,
            marks_obtained=score,
            attendance_status=ExamAttendanceStatus.PRESENT,
        )
        db.add(res)
    await db.commit()

    report = await get_exam_psychometrics(session=db, exam_id=exam.id, num_items=8)
    assert report.exam_id == exam.id
    assert report.total_examinees == 10
    assert report.total_items == 8
    assert len(report.items) == 8
    assert report.mean_score > 0
    assert len(report.recommendations) > 0

    # Test via router function directly
    router_report = await get_psychometrics(
        exam_id=exam.id,
        num_items=8,
        session=db,
        principal=_TEACHER,
    )
    assert router_report.exam_id == exam.id
    assert router_report.total_examinees == 10

