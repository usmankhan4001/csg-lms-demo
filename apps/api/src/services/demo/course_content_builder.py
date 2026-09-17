"""
CSG-EMS / LearnHouse Course Curriculum & Content Builder
========================================================
Constructs publication-ready, fully-articulated demo courses for the CSG-EMS platform:
1. 'AP Physics C: Mechanics & Electromagnetism' (Code: PHY-301)
2. 'Advanced Calculus & Linear Algebra' (Code: MATH-401)
3. 'World History & Global Perspectives' (Code: HIST-201)
4. 'Autonomous AI & Computational Science' (Code: CS-101)

Each course features:
- Multi-chapter pedagogical progression with LockType.PUBLIC
- Video activities with rich timestamped outlines, transcripts, and duration metadata
- Dynamic markdown / page activities with LaTeX equations and interactive BLOCK_QUIZ modules
- SpeedGrader assignments with multiple task types (CODE, SHORT_ANSWER, FILE_SUBMISSION)
- Authentic student submissions and SpeedGrader marks with rubrics for Alex Mercer, Maya Lin, and Leo Vance
- Full idempotency and referential integrity across LearnHouse courses, chapters, activities, blocks, and assignments.
"""

import datetime
import logging
from typing import Any, Dict, List, Optional, Union
from uuid import uuid4

from sqlalchemy import select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.db.users import User
from src.db.courses.courses import Course, ThumbnailType
from src.db.courses.chapters import Chapter, LockType
from src.db.courses.course_chapters import CourseChapter
from src.db.courses.activities import (
    Activity,
    ActivityTypeEnum,
    ActivitySubTypeEnum,
    ActivityLockType,
)
from src.db.courses.chapter_activities import ChapterActivity
from src.db.courses.blocks import Block, BlockTypeEnum
from src.db.courses.assignments import (
    Assignment,
    GradingTypeEnum,
    SolutionRevealEnum,
    AssignmentTask,
    AssignmentTaskTypeEnum,
    AssignmentTaskSubmission,
    AssignmentUserSubmission,
    AssignmentUserSubmissionStatus,
)

logger = logging.getLogger(__name__)


def _now() -> str:
    """Returns ISO UTC timestamp string."""
    return str(datetime.datetime.now(datetime.timezone.utc))


def _resolve_user_id(
    user_ref: Union[str, int, User, None],
    user_map: Optional[Dict[str, Any]] = None,
) -> Optional[int]:
    """Resolves a user ID from various reference types (User instance, int ID, or email/key in user_map)."""
    if user_ref is None:
        return None
    if isinstance(user_ref, int):
        return user_ref
    if isinstance(user_ref, User):
        return user_ref.id
    if isinstance(user_ref, str):
        if user_map and user_ref in user_map:
            val = user_map[user_ref]
            if isinstance(val, User):
                return val.id
            if isinstance(val, int):
                return val
        if user_map:
            for k, v in user_map.items():
                if user_ref.lower() in k.lower() or k.lower() in user_ref.lower():
                    if isinstance(v, User):
                        return v.id
                    if isinstance(v, int):
                        return v
    return None


async def _get_or_create_course(
    db_session: AsyncSession,
    org_id: int,
    spec: Dict[str, Any],
) -> Course:
    """Idempotently finds or creates a Course."""
    stmt = select(Course).where(
        Course.org_id == org_id,
        Course.name == spec["name"],
    )
    course = (await db_session.execute(stmt)).scalars().first()
    now_str = _now()
    if not course:
        course = Course(
            org_id=org_id,
            name=spec["name"],
            description=spec.get("description", ""),
            about=spec.get("about", spec.get("description", "")),
            learnings=spec.get("learnings", ""),
            tags=spec.get("tags", ""),
            thumbnail_type=spec.get("thumbnail_type", ThumbnailType.IMAGE),
            thumbnail_image=spec.get("thumbnail_image", ""),
            thumbnail_video=spec.get("thumbnail_video", ""),
            public=True,
            published=True,
            open_to_contributors=False,
            course_uuid=f"crs_{uuid4()}",
            creation_date=now_str,
            update_date=now_str,
        )
        db_session.add(course)
        await db_session.flush()
        await db_session.refresh(course)
    else:
        course.public = True
        course.published = True
        course.description = spec.get("description", course.description)
        course.about = spec.get("about", course.about)
        course.learnings = spec.get("learnings", course.learnings)
        course.tags = spec.get("tags", course.tags)
        db_session.add(course)
        await db_session.flush()

    return course


async def _get_or_create_chapter(
    db_session: AsyncSession,
    org_id: int,
    course_id: int,
    spec: Dict[str, Any],
    order: int,
) -> Chapter:
    """Idempotently finds or creates a Chapter and its CourseChapter link."""
    stmt = select(Chapter).where(
        Chapter.org_id == org_id,
        Chapter.course_id == course_id,
        Chapter.name == spec["name"],
    )
    chapter = (await db_session.execute(stmt)).scalars().first()
    now_str = _now()
    if not chapter:
        chapter = Chapter(
            org_id=org_id,
            course_id=course_id,
            name=spec["name"],
            description=spec.get("description", ""),
            thumbnail_image=spec.get("thumbnail_image", ""),
            lock_type=LockType.PUBLIC,
            chapter_uuid=f"ch_{uuid4()}",
            creation_date=now_str,
            update_date=now_str,
            extra_metadata=spec.get("extra_metadata"),
        )
        db_session.add(chapter)
        await db_session.flush()
        await db_session.refresh(chapter)
    else:
        chapter.lock_type = LockType.PUBLIC
        chapter.description = spec.get("description", chapter.description)
        db_session.add(chapter)
        await db_session.flush()

    # Link CourseChapter
    cc_stmt = select(CourseChapter).where(
        CourseChapter.course_id == course_id,
        CourseChapter.chapter_id == chapter.id,
    )
    cc = (await db_session.execute(cc_stmt)).scalars().first()
    if not cc:
        cc = CourseChapter(
            course_id=course_id,
            chapter_id=chapter.id,
            org_id=org_id,
            order=order,
            creation_date=now_str,
            update_date=now_str,
        )
        db_session.add(cc)
        await db_session.flush()

    return chapter


async def _get_or_create_activity(
    db_session: AsyncSession,
    org_id: int,
    course_id: int,
    chapter_id: int,
    spec: Dict[str, Any],
    order: int,
) -> Activity:
    """Idempotently finds or creates an Activity and its ChapterActivity link."""
    stmt = select(Activity).where(
        Activity.org_id == org_id,
        Activity.course_id == course_id,
        Activity.name == spec["name"],
    )
    activity = (await db_session.execute(stmt)).scalars().first()
    now_str = _now()
    if not activity:
        activity = Activity(
            org_id=org_id,
            course_id=course_id,
            name=spec["name"],
            activity_type=spec["activity_type"],
            activity_sub_type=spec["activity_sub_type"],
            content=spec.get("content", {}),
            details=spec.get("details", {}),
            published=True,
            lock_type=ActivityLockType.PUBLIC,
            activity_uuid=f"act_{uuid4()}",
            creation_date=now_str,
            update_date=now_str,
            current_version=1,
            extra_metadata=spec.get("extra_metadata"),
        )
        db_session.add(activity)
        await db_session.flush()
        await db_session.refresh(activity)
    else:
        activity.published = True
        activity.lock_type = ActivityLockType.PUBLIC
        activity.activity_type = spec["activity_type"]
        activity.activity_sub_type = spec["activity_sub_type"]
        activity.content = spec.get("content", activity.content)
        activity.details = spec.get("details", activity.details)
        db_session.add(activity)
        await db_session.flush()

    # Link ChapterActivity
    ca_stmt = select(ChapterActivity).where(
        ChapterActivity.chapter_id == chapter_id,
        ChapterActivity.activity_id == activity.id,
    )
    ca = (await db_session.execute(ca_stmt)).scalars().first()
    if not ca:
        ca = ChapterActivity(
            chapter_id=chapter_id,
            activity_id=activity.id,
            course_id=course_id,
            org_id=org_id,
            order=order,
            creation_date=now_str,
            update_date=now_str,
        )
        db_session.add(ca)
        await db_session.flush()

    return activity


async def _get_or_create_block(
    db_session: AsyncSession,
    org_id: int,
    course_id: int,
    chapter_id: int,
    activity_id: int,
    block_type: BlockTypeEnum,
    content: Dict[str, Any],
) -> Block:
    """Idempotently finds or creates an interactive Block within an Activity."""
    stmt = select(Block).where(
        Block.activity_id == activity_id,
        Block.block_type == block_type,
    )
    block = (await db_session.execute(stmt)).scalars().first()
    now_str = _now()
    if not block:
        block = Block(
            org_id=org_id,
            course_id=course_id,
            chapter_id=chapter_id,
            activity_id=activity_id,
            block_type=block_type,
            content=content,
            block_uuid=f"blk_{uuid4()}",
            creation_date=now_str,
            update_date=now_str,
        )
        db_session.add(block)
        await db_session.flush()
        await db_session.refresh(block)
    else:
        block.content = content
        block.update_date = now_str
        db_session.add(block)
        await db_session.flush()

    return block


async def _get_or_create_assignment(
    db_session: AsyncSession,
    org_id: int,
    course_id: int,
    chapter_id: int,
    activity_id: int,
    spec: Dict[str, Any],
) -> Assignment:
    """Idempotently finds or creates a SpeedGrader Assignment."""
    stmt = select(Assignment).where(
        Assignment.activity_id == activity_id,
    )
    assignment = (await db_session.execute(stmt)).scalars().first()
    now_str = _now()
    due_date = (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=14)).strftime("%Y-%m-%d %H:%M:%S")

    if not assignment:
        assignment = Assignment(
            org_id=org_id,
            course_id=course_id,
            chapter_id=chapter_id,
            activity_id=activity_id,
            title=spec["title"],
            description=spec.get("description", ""),
            due_date=spec.get("due_date", due_date),
            published=True,
            grading_type=spec.get("grading_type", GradingTypeEnum.PERCENTAGE),
            auto_grading=spec.get("auto_grading", False),
            anti_copy_paste=spec.get("anti_copy_paste", False),
            show_correct_answers=spec.get("show_correct_answers", True),
            allow_retries=spec.get("allow_retries", True),
            max_retries=spec.get("max_retries", 2),
            pass_threshold_percentage=spec.get("pass_threshold_percentage", 70.0),
            ungraded=spec.get("ungraded", False),
            solution=spec.get("solution", "Standard model solutions and analytical rubric benchmarks."),
            solution_reveal=spec.get("solution_reveal", SolutionRevealEnum.AFTER_GRADING),
            assignment_uuid=f"asg_{uuid4()}",
            creation_date=now_str,
            update_date=now_str,
        )
        db_session.add(assignment)
        await db_session.flush()
        await db_session.refresh(assignment)
    else:
        assignment.published = True
        assignment.title = spec["title"]
        assignment.description = spec.get("description", assignment.description)
        assignment.solution = spec.get("solution", assignment.solution)
        db_session.add(assignment)
        await db_session.flush()

    return assignment


async def _get_or_create_assignment_task(
    db_session: AsyncSession,
    org_id: int,
    course_id: int,
    chapter_id: int,
    activity_id: int,
    assignment_id: int,
    spec: Dict[str, Any],
) -> AssignmentTask:
    """Idempotently creates or updates an AssignmentTask."""
    stmt = select(AssignmentTask).where(
        AssignmentTask.assignment_id == assignment_id,
        AssignmentTask.title == spec["title"],
    )
    task = (await db_session.execute(stmt)).scalars().first()
    now_str = _now()
    if not task:
        task = AssignmentTask(
            org_id=org_id,
            course_id=course_id,
            chapter_id=chapter_id,
            activity_id=activity_id,
            assignment_id=assignment_id,
            title=spec["title"],
            description=spec.get("description", ""),
            hint=spec.get("hint", ""),
            reference_file=spec.get("reference_file", ""),
            assignment_type=spec.get("assignment_type", AssignmentTaskTypeEnum.SHORT_ANSWER),
            contents=spec.get("contents", {}),
            max_grade_value=spec.get("max_grade_value", 50),
            assignment_task_uuid=f"task_{uuid4()}",
            creation_date=now_str,
            update_date=now_str,
        )
        db_session.add(task)
        await db_session.flush()
        await db_session.refresh(task)
    else:
        task.description = spec.get("description", task.description)
        task.hint = spec.get("hint", task.hint)
        task.contents = spec.get("contents", task.contents)
        task.max_grade_value = spec.get("max_grade_value", task.max_grade_value)
        db_session.add(task)
        await db_session.flush()

    return task


async def _get_or_create_task_submission(
    db_session: AsyncSession,
    task: AssignmentTask,
    user_id: int,
    spec: Dict[str, Any],
) -> AssignmentTaskSubmission:
    """Idempotently seeds an individual task submission with score and detailed feedback."""
    stmt = select(AssignmentTaskSubmission).where(
        AssignmentTaskSubmission.user_id == user_id,
        AssignmentTaskSubmission.assignment_task_id == task.id,
    )
    sub = (await db_session.execute(stmt)).scalars().first()
    now_str = _now()
    if not sub:
        sub = AssignmentTaskSubmission(
            assignment_task_submission_uuid=f"tsub_{uuid4()}",
            user_id=user_id,
            assignment_task_id=task.id,
            course_id=task.course_id,
            chapter_id=task.chapter_id,
            activity_id=task.activity_id,
            assignment_type=task.assignment_type,
            task_submission=spec.get("submission_content", {}),
            grade=spec.get("grade", task.max_grade_value),
            task_submission_grade_feedback=spec.get("feedback", "Excellent response."),
            manually_graded=spec.get("manually_graded", True),
            creation_date=now_str,
            update_date=now_str,
        )
        db_session.add(sub)
        await db_session.flush()
    else:
        sub.grade = spec.get("grade", sub.grade)
        sub.task_submission_grade_feedback = spec.get("feedback", sub.task_submission_grade_feedback)
        sub.task_submission = spec.get("submission_content", sub.task_submission)
        db_session.add(sub)
        await db_session.flush()

    return sub


async def _get_or_create_user_submission(
    db_session: AsyncSession,
    assignment_id: int,
    user_id: int,
    spec: Dict[str, Any],
) -> AssignmentUserSubmission:
    """Idempotently seeds overall user assignment submission status and SpeedGrader evaluation."""
    stmt = select(AssignmentUserSubmission).where(
        AssignmentUserSubmission.user_id == user_id,
        AssignmentUserSubmission.assignment_id == assignment_id,
    )
    user_sub = (await db_session.execute(stmt)).scalars().first()
    now_str = _now()
    if not user_sub:
        user_sub = AssignmentUserSubmission(
            user_id=user_id,
            assignment_id=assignment_id,
            submission_status=spec.get("status", AssignmentUserSubmissionStatus.GRADED),
            grade=spec.get("grade", 95),
            overall_feedback=spec.get("overall_feedback", "High-distinction academic performance."),
            attempt_number=spec.get("attempt_number", 1),
        )
        user_sub.creation_date = now_str
        user_sub.update_date = now_str
        user_sub.assignmentusersubmission_uuid = f"usub_{uuid4()}"
        db_session.add(user_sub)
        await db_session.flush()
    else:
        user_sub.grade = spec.get("grade", user_sub.grade)
        user_sub.overall_feedback = spec.get("overall_feedback", user_sub.overall_feedback)
        user_sub.submission_status = spec.get("status", user_sub.submission_status)
        user_sub.update_date = now_str
        db_session.add(user_sub)
        await db_session.flush()

    return user_sub


# ============================================================================
# Course 1 Builder: AP Physics C: Mechanics & Electromagnetism (PHY-301)
# ============================================================================
async def _build_physics_course(
    db_session: AsyncSession,
    org_id: int,
    alex_id: Optional[int],
    maya_id: Optional[int],
) -> Dict[str, Any]:
    """Constructs Course 1: AP Physics C."""
    course_spec = {
        "name": "AP Physics C: Mechanics & Electromagnetism",
        "description": "Calculus-based AP Physics C exploring Newtonian dynamics, rotational systems, energy manifolds, and modern spacetime invariance.",
        "about": (
            "A rigorous, college-level physics program designed for advanced STEM scholars. Combines analytical "
            "vector derivations, differential equation modeling, numerical laboratory simulations, and real-time SpeedGrader rubrics."
        ),
        "learnings": (
            "1. Master 2D and 3D curvilinear kinematics with vector calculus.\n"
            "2. Formulate and solve non-linear differential equations with aerodynamic drag.\n"
            "3. Derive work-energy theorems and potential energy manifolds for conservative and non-conservative fields.\n"
            "4. Analyze tensor moments of inertia and gyroscopic precession dynamics.\n"
            "5. Apply Lorentz transformations, four-momentum, and relativistic invariants to modern physical systems."
        ),
        "tags": "physics,ap-physics,mechanics,calculus,stem,electromagnetism",
        "thumbnail_image": "https://images.unsplash.com/photo-1636466497217-26a8cbeaf0aa?auto=format&fit=crop&w=1200&q=80",
    }
    course = await _get_or_create_course(db_session, org_id, course_spec)
    assignments_created = {}

    # Chapter 1: Classical Mechanics, Vectors & Kinematics
    ch1_spec = {
        "name": "Classical Mechanics, Vectors & Kinematics",
        "description": "Vector analysis, curvilinear coordinate systems, multivariable differential kinematics, and non-linear aerodynamic drag.",
    }
    ch1 = await _get_or_create_chapter(db_session, org_id, course.id, ch1_spec, order=1)

    # Activity 1: Video
    act1_spec = {
        "name": "Kinematics in 2D & Vector Derivations",
        "activity_type": ActivityTypeEnum.TYPE_VIDEO,
        "activity_sub_type": ActivitySubTypeEnum.SUBTYPE_VIDEO_YOUTUBE,
        "content": {"youtube_id": "b1t41Q3xRM8"},
        "details": {
            "video_provider": "youtube",
            "youtube_id": "b1t41Q3xRM8",
            "duration_seconds": 2840,
            "instructor": "Dr. Arthur Chen, Ph.D.",
            "timestamps": [
                {"time": "00:00", "title": "Vector Coordinate Spaces & Time-Dependent Position Vectors r(t)"},
                {"time": "05:15", "title": "First & Second Derivatives: Instantaneous Velocity & Acceleration"},
                {"time": "14:30", "title": "Curvilinear Decompositions: Tangential vs Normal Acceleration (a_t & v²/ρ)"},
                {"time": "24:45", "title": "Non-Linear Projectile Dynamics with Quadratic Drag Models"},
                {"time": "38:10", "title": "Worked AP Physics C FRQ Problem: Vector Line Integrals"},
            ],
            "transcript_summary": (
                "Dr. Chen establishes 2D kinematics using multivariable vector calculus. "
                "Students learn to differentiate position vectors, decomposing acceleration into tangential and curvature components."
            ),
        },
    }
    await _get_or_create_activity(db_session, org_id, course.id, ch1.id, act1_spec, order=1)

    # Activity 2: Dynamic Page with Quiz Block
    dynamics_page_markdown = """# Newtonian Dynamics & Free Body Systems

Newtonian mechanics establishes the relationship between forces and the differential evolution of linear momentum:

$$\\vec{F}_{net} = \\frac{d\\vec{p}}{dt} = m\\frac{d^2\\vec{r}}{dt^2} + \\vec{v}\\frac{dm}{dt}$$

For constant-mass systems, this reduces to Newton's Second Law: $\\Sigma \\vec{F} = m\\vec{a}$.

---

## 1. Contact Dynamics & Empirical Friction Models

Static and kinetic friction forces are governed by normal reaction forces $F_N$:

$$f_s \\le \\mu_s F_N, \\quad f_k = \\mu_k F_N$$

Where $\\mu_s > \\mu_k$ under standard surface roughness regimes.

```
         ┌───────────────┐
         │     MASS m    │ ───► Applied Force F
         └───────────────┘
  ◄───────       │
Friction f_k     ▼ Gravity mg
```

## 2. Aerodynamic Drag & Terminal Velocity

For high-speed projectiles ($Re > 10^3$), drag is quadratic with respect to relative velocity:

$$\\vec{F}_{drag} = -\\frac{1}{2} C_D \\rho A v^2 \\hat{v}$$

Setting $\\Sigma F_y = 0$ for a falling body yields the analytical terminal velocity:

$$v_{terminal} = \\sqrt{\\frac{2mg}{C_D \\rho A}}$$

> **Key Takeaway**: In numerical modeling, quadratic drag couples horizontal and vertical velocity components non-linearly: $a_x = -\\frac{k}{m} v v_x$ and $a_y = -g - \\frac{k}{m} v v_y$.
"""
    act2_spec = {
        "name": "Newtonian Dynamics & Free Body Diagrams",
        "activity_type": ActivityTypeEnum.TYPE_DYNAMIC,
        "activity_sub_type": ActivitySubTypeEnum.SUBTYPE_DYNAMIC_PAGE,
        "content": {"markdown": dynamics_page_markdown},
        "details": {"reading_time_minutes": 18, "interactive_modules": ["quiz_block", "latex_viewer"]},
    }
    act2 = await _get_or_create_activity(db_session, org_id, course.id, ch1.id, act2_spec, order=2)

    quiz_content_ch1 = {
        "quiz_title": "Newtonian Dynamics & Incline Mechanics Conceptual Assessment",
        "questions": [
            {
                "id": "q1",
                "question": "A block of mass m slides down an incline with angle θ and coefficient of kinetic friction μ_k. What is its acceleration down the plane?",
                "options": [
                    "a = g(sin θ - μ_k cos θ)",
                    "a = g(cos θ - μ_k sin θ)",
                    "a = g sin θ + μ_k g cos θ",
                    "a = mg(sin θ - μ_k cos θ)",
                ],
                "correct_option_index": 0,
                "explanation": "Resolving along the incline: F_net = mg sin θ - μ_k mg cos θ = m a. Dividing by m yields a = g(sin θ - μ_k cos θ).",
            },
            {
                "id": "q2",
                "question": "An object of mass m falls vertically under quadratic drag F_d = -c v². What is its terminal velocity?",
                "options": [
                    "v_t = √(mg / c)",
                    "v_t = mg / c",
                    "v_t = √(c / mg)",
                    "v_t = 2mg / c",
                ],
                "correct_option_index": 0,
                "explanation": "At terminal equilibrium, upward aerodynamic drag equals downward gravity: c v_t² = mg => v_t = √(mg / c).",
            },
            {
                "id": "q3",
                "question": "In an ideal Atwood machine with unequal masses m₁ < m₂ connected over a frictionless pulley, what is string tension T?",
                "options": [
                    "T = (2 m₁ m₂) / (m₁ + m₂) * g",
                    "T = (m₁ m₂) / (m₁ + m₂) * g",
                    "T = (m₂ - m₁) * g",
                    "T = (m₁ + m₂) / 2 * g",
                ],
                "correct_option_index": 0,
                "explanation": "Combining T - m₁g = m₁a and m₂g - T = m₂a gives a = g(m₂ - m₁)/(m₁ + m₂). Substituting into T yields T = (2 m₁ m₂ g)/(m₁ + m₂).",
            },
        ],
    }
    await _get_or_create_block(db_session, org_id, course.id, ch1.id, act2.id, BlockTypeEnum.BLOCK_QUIZ, quiz_content_ch1)

    # Activity 3: SpeedGrader Assignment
    act3_spec = {
        "name": "SpeedGrader Lab: Projectile Trajectory & Air Resistance Analysis",
        "activity_type": ActivityTypeEnum.TYPE_ASSIGNMENT,
        "activity_sub_type": ActivitySubTypeEnum.SUBTYPE_ASSIGNMENT_ANY,
        "content": {},
        "details": {"grading_rubric_ready": True, "speedgrader_enabled": True},
    }
    act3 = await _get_or_create_activity(db_session, org_id, course.id, ch1.id, act3_spec, order=3)

    asg1_spec = {
        "title": "SpeedGrader Lab: Projectile Trajectory & Air Resistance Analysis",
        "description": (
            "Computational laboratory on non-linear projectile trajectories. Students implement numerical integration "
            "(Euler-Cromer or RK4) in Python to simulate aerodynamic drag effects and compare against analytical vacuum limits."
        ),
        "grading_type": GradingTypeEnum.PERCENTAGE,
        "pass_threshold_percentage": 70.0,
        "solution": "Model Python RK4 differential equation solver with phase-space trajectory comparisons and terminal velocity proofs.",
    }
    asg1 = await _get_or_create_assignment(db_session, org_id, course.id, ch1.id, act3.id, asg1_spec)
    assignments_created["phy_lab_1"] = asg1

    task1_spec = {
        "title": "Task 1: Python Trajectory Simulation & ODE Solver",
        "description": "Write Python code utilizing Euler-Cromer or Runge-Kutta 4 to model projectile motion under quadratic drag.",
        "hint": "Remember that drag opposes the instantaneous velocity vector: v = sqrt(vx^2 + vy^2).",
        "assignment_type": AssignmentTaskTypeEnum.CODE,
        "max_grade_value": 50,
        "contents": {"language": "python", "template": "import numpy as np\n\ndef simulate_trajectory(v0, theta_deg, dt=0.01):\n    pass"},
    }
    task1 = await _get_or_create_assignment_task(db_session, org_id, course.id, ch1.id, act3.id, asg1.id, task1_spec)

    task2_spec = {
        "title": "Task 2: Analytical Error Analysis & Terminal Velocity Proof",
        "description": "Provide a rigorous derivation showing how velocity error scales with step size dt and calculate theoretical terminal velocity.",
        "hint": "Expand the Taylor series of v(t+dt) to identify leading truncation terms.",
        "assignment_type": AssignmentTaskTypeEnum.SHORT_ANSWER,
        "max_grade_value": 50,
        "contents": {"rubric": "Mathematical rigor: 20 pts, Error bound proof: 20 pts, Clarity: 10 pts"},
    }
    task2 = await _get_or_create_assignment_task(db_session, org_id, course.id, ch1.id, act3.id, asg1.id, task2_spec)

    # Submissions
    if alex_id:
        alex_t1 = {
            "submission_content": {
                "code": (
                    "import numpy as np\n\n"
                    "def simulate_trajectory(v0=50.0, theta_deg=45.0, dt=0.001, m=0.145, cd=0.3, area=0.0042):\n"
                    "    rho = 1.225\n"
                    "    k = 0.5 * cd * rho * area\n"
                    "    g = 9.80665\n"
                    "    theta = np.radians(theta_deg)\n"
                    "    vx = v0 * np.cos(theta)\n"
                    "    vy = v0 * np.sin(theta)\n"
                    "    x, y = 0.0, 0.0\n"
                    "    t = 0.0\n"
                    "    while y >= 0.0:\n"
                    "        v = np.hypot(vx, vy)\n"
                    "        ax = -(k/m) * v * vx\n"
                    "        ay = -g - (k/m) * v * vy\n"
                    "        vx += ax * dt\n"
                    "        vy += ay * dt\n"
                    "        x += vx * dt\n"
                    "        y += vy * dt\n"
                    "        t += dt\n"
                    "    return x, t\n"
                )
            },
            "grade": 48,
            "feedback": "Superb Euler-Cromer integration! Time step dt=0.001s provides excellent convergence.",
        }
        await _get_or_create_task_submission(db_session, task1, alex_id, alex_t1)

        alex_t2 = {
            "submission_content": {
                "text": (
                    "Derivation: Setting net force equal to zero along the vertical axis:\n"
                    "mg = 0.5 * rho * C_D * A * v_t^2\n"
                    "v_t = sqrt((2*m*g) / (rho * C_D * A)).\n"
                    "For Euler-Cromer, local truncation error is O(dt^2) and global error is O(dt)."
                )
            },
            "grade": 47,
            "feedback": "Rigorous derivation with precise asymptotic error bounds.",
        }
        await _get_or_create_task_submission(db_session, task2, alex_id, alex_t2)

        alex_overall = {
            "grade": 95,
            "status": AssignmentUserSubmissionStatus.GRADED,
            "overall_feedback": "Outstanding computational lab submission, Alex. Your numerical simulation and error bounds align closely with benchmark laboratory data.",
        }
        await _get_or_create_user_submission(db_session, asg1.id, alex_id, alex_overall)

    if maya_id:
        maya_t1 = {
            "submission_content": {
                "code": (
                    "import numpy as np\n\n"
                    "def rk4_step(state, dt, m, k, g):\n"
                    "    def derivatives(s):\n"
                    "        x, y, vx, vy = s\n"
                    "        v = np.hypot(vx, vy)\n"
                    "        return np.array([vx, vy, -(k/m)*v*vx, -g - (k/m)*v*vy])\n"
                    "    k1 = derivatives(state)\n"
                    "    k2 = derivatives(state + 0.5 * dt * k1)\n"
                    "    k3 = derivatives(state + 0.5 * dt * k2)\n"
                    "    k4 = derivatives(state + dt * k3)\n"
                    "    return state + (dt / 6.0) * (k1 + 2*k2 + 2*k3 + k4)\n"
                )
            },
            "grade": 50,
            "feedback": "Flawless 4th-Order Runge-Kutta vector ODE solver. Exemplary coding precision.",
        }
        await _get_or_create_task_submission(db_session, task1, maya_id, maya_t1)

        maya_t2 = {
            "submission_content": {
                "text": (
                    "Under RK4 integration, global truncation error scales as O(dt^4), ensuring negligible energy drift. "
                    "Terminal velocity v_t = sqrt(2mg / (rho * C_D * A)) was verified analytically and numerically to within 0.001% tolerance."
                )
            },
            "grade": 48,
            "feedback": "Brilliant perturbation expansion and empirical convergence validation.",
        }
        await _get_or_create_task_submission(db_session, task2, maya_id, maya_t2)

        maya_overall = {
            "grade": 98,
            "status": AssignmentUserSubmissionStatus.GRADED,
            "overall_feedback": "Exemplary research-grade lab report, Maya. The RK4 vector implementation and convergence testing exceed AP standards.",
        }
        await _get_or_create_user_submission(db_session, asg1.id, maya_id, maya_overall)

    # Chapter 2: Conservation of Energy & Rotational Dynamics
    ch2_spec = {
        "name": "Conservation of Energy & Rotational Dynamics",
        "description": "Conservative force fields, potential energy wells, moments of inertia, rotational kinematics, and angular momentum conservation.",
    }
    ch2 = await _get_or_create_chapter(db_session, org_id, course.id, ch2_spec, order=2)

    ch2_act1_spec = {
        "name": "Conservative Forces, Potential Energy Wells & Work-Energy Theorem",
        "activity_type": ActivityTypeEnum.TYPE_VIDEO,
        "activity_sub_type": ActivitySubTypeEnum.SUBTYPE_VIDEO_YOUTUBE,
        "content": {"youtube_id": "dQw4w9WgXcQ"},
        "details": {
            "video_provider": "youtube",
            "youtube_id": "dQw4w9WgXcQ",
            "duration_seconds": 2700,
            "timestamps": [
                {"time": "00:00", "title": "Line Integrals of Vector Fields: W = ∫ F · dr"},
                {"time": "08:20", "title": "Conservative Field Conditions: Curl ∇ × F = 0"},
                {"time": "17:40", "title": "Potential Wells U(x), Equilibrium Points & Small Angle Oscillations"},
                {"time": "31:10", "title": "Rotational Kinetic Energy: K_rot = 1/2 I ω²"},
            ],
        },
    }
    await _get_or_create_activity(db_session, org_id, course.id, ch2.id, ch2_act1_spec, order=1)

    ch2_act2_spec = {
        "name": "Moment of Inertia & Rotational Kinetics Reference Handbook",
        "activity_type": ActivityTypeEnum.TYPE_DOCUMENT,
        "activity_sub_type": ActivitySubTypeEnum.SUBTYPE_DOCUMENT_PDF,
        "content": {
            "file_url": "/documents/ap-physics-c-rotational-kinetics-handbook.pdf",
            "page_count": 24,
            "title": "Moment of Inertia & Rotational Kinetics Reference Handbook",
        },
        "details": {
            "topics": [
                "Parallel Axis Theorem: I = I_cm + M d²",
                "Perpendicular Axis Theorem for Planar Laminae",
                "Rolling Without Slipping Dynamics: v_cm = R ω",
                "Gyroscopic Precession: Ω_p = τ / L",
            ]
        },
    }
    await _get_or_create_activity(db_session, org_id, course.id, ch2.id, ch2_act2_spec, order=2)

    ch2_act3_spec = {
        "name": "SpeedGrader Problem Set: Angular Momentum & Elastic Collisions",
        "activity_type": ActivityTypeEnum.TYPE_ASSIGNMENT,
        "activity_sub_type": ActivitySubTypeEnum.SUBTYPE_ASSIGNMENT_ANY,
        "content": {},
        "details": {"speedgrader_enabled": True},
    }
    ch2_act3 = await _get_or_create_activity(db_session, org_id, course.id, ch2.id, ch2_act3_spec, order=3)

    asg2_spec = {
        "title": "SpeedGrader Problem Set: Angular Momentum & Elastic Collisions",
        "description": "Advanced problem set on coupled rotational-translational collisions and gyroscopic precession dynamics.",
        "grading_type": GradingTypeEnum.PERCENTAGE,
        "pass_threshold_percentage": 70.0,
    }
    asg2 = await _get_or_create_assignment(db_session, org_id, course.id, ch2.id, ch2_act3.id, asg2_spec)
    assignments_created["phy_ps_2"] = asg2

    task2_1_spec = {
        "title": "Task 1: Ballistic Impact on Pivoting Uniform Rod",
        "description": "Calculate angular velocity immediately after an inelastic collision of mass m with a pivoted rod of mass M and length L.",
        "hint": "Conserve angular momentum about the fixed pivot point.",
        "assignment_type": AssignmentTaskTypeEnum.SHORT_ANSWER,
        "max_grade_value": 50,
        "contents": {},
    }
    t2_1 = await _get_or_create_assignment_task(db_session, org_id, course.id, ch2.id, ch2_act3.id, asg2.id, task2_1_spec)

    task2_2_spec = {
        "title": "Task 2: Gyroscopic Precession & Cross Product Vector Dynamics",
        "description": "Derive the precession angular velocity Ω_p for a spinning flywheel with angular momentum L subject to torque τ = r x Mg.",
        "hint": "Apply dL/dt = τ and dL = L dθ.",
        "assignment_type": AssignmentTaskTypeEnum.SHORT_ANSWER,
        "max_grade_value": 50,
        "contents": {},
    }
    t2_2 = await _get_or_create_assignment_task(db_session, org_id, course.id, ch2.id, ch2_act3.id, asg2.id, task2_2_spec)

    if alex_id:
        await _get_or_create_task_submission(db_session, t2_1, alex_id, {"grade": 46, "feedback": "Accurate conservation of angular momentum about pivot."})
        await _get_or_create_task_submission(db_session, t2_2, alex_id, {"grade": 46, "feedback": "Solid gyroscopic precession derivation."})
        await _get_or_create_user_submission(db_session, asg2.id, alex_id, {"grade": 92, "overall_feedback": "Excellent work on rotational momentum conservation."})

    if maya_id:
        await _get_or_create_task_submission(db_session, t2_1, maya_id, {"grade": 48, "feedback": "Perfect energy-loss calculation in inelastic impact."})
        await _get_or_create_task_submission(db_session, t2_2, maya_id, {"grade": 48, "feedback": "Flawless tensor and cross-product treatment."})
        await _get_or_create_user_submission(db_session, asg2.id, maya_id, {"grade": 96, "overall_feedback": "Top-tier analytical physics work, Maya."})

    # Chapter 3: Special Relativity & Modern Physics
    ch3_spec = {
        "name": "Special Relativity & Modern Physics",
        "description": "Lorentz transformations, spacetime invariants, relativistic dynamics, and comprehensive midterm mastery.",
    }
    ch3 = await _get_or_create_chapter(db_session, org_id, course.id, ch3_spec, order=3)

    relativity_markdown = """# Lorentz Transformations & Spacetime Invariants

Einstein's Special Theory of Relativity is built upon two fundamental postulates:
1. The laws of physics are invariant in all inertial reference frames.
2. The speed of light in vacuum $c$ is constant for all observers regardless of relative motion.

## 1. The Lorentz Factor & Transformations

$$\\gamma = \\frac{1}{\\sqrt{1 - \\frac{v^2}{c^2}}}$$

Transforming between frame $S$ and moving frame $S'$ along the x-axis:

$$x' = \\gamma (x - vt), \\quad t' = \\gamma \\left(t - \\frac{vx}{c^2}\\right)$$

## 2. Invariant Spacetime Interval

$$(\\Delta s)^2 = -(c\\Delta t)^2 + (\\Delta x)^2 + (\\Delta y)^2 + (\\Delta z)^2$$

Because $(\\Delta s)^2$ is Lorentz-invariant, all observers agree on timelike, lightlike, and spacelike separations.

## 3. Relativistic Four-Momentum & Invariant Mass

$$E^2 = (pc)^2 + (m_0 c^2)^2$$
"""
    ch3_act1_spec = {
        "name": "Lorentz Transformations, Time Dilation & Spacetime Invariants",
        "activity_type": ActivityTypeEnum.TYPE_DYNAMIC,
        "activity_sub_type": ActivitySubTypeEnum.SUBTYPE_DYNAMIC_PAGE,
        "content": {"markdown": relativity_markdown},
        "details": {"reading_time_minutes": 20},
    }
    ch3_act1 = await _get_or_create_activity(db_session, org_id, course.id, ch3.id, ch3_act1_spec, order=1)

    rel_quiz = {
        "quiz_title": "Special Relativity Concept Check",
        "questions": [
            {
                "id": "rq1",
                "question": "A spaceship moves at v = 0.8c relative to Earth. What is the Lorentz factor γ?",
                "options": ["γ = 1.67", "γ = 1.25", "γ = 2.00", "γ = 0.60"],
                "correct_option_index": 0,
                "explanation": "γ = 1 / √(1 - 0.8²) = 1 / √(1 - 0.64) = 1 / √0.36 = 1 / 0.6 ≈ 1.667.",
            },
            {
                "id": "rq2",
                "question": "What is the relativistic invariant quantity in four-momentum space?",
                "options": ["E² - (pc)² = (mc²)²", "E = mc²", "p = γmv", "E = pc"],
                "correct_option_index": 0,
                "explanation": "The inner product P^μ P_μ = -(mc)² leads directly to E² - (pc)² = (m₀c²)².",
            },
        ],
    }
    await _get_or_create_block(db_session, org_id, course.id, ch3.id, ch3_act1.id, BlockTypeEnum.BLOCK_QUIZ, rel_quiz)

    compendium_markdown = """# AP Physics C Midterm Mastery Compendium

### Kinematics & Mechanics
- Instantaneous Acceleration: $\\vec{a}(t) = \\frac{d^2\\vec{r}}{dt^2}$
- Newton's Second Law: $\\Sigma \\vec{F} = \\frac{d\\vec{p}}{dt} = m\\vec{a}$

### Energy & Rotational Dynamics
- Work-Energy Theorem: $W_{net} = \\Delta K = \\int \\vec{F}_{net} \\cdot d\\vec{r}$
- Torque & Angular Momentum: $\\vec{\\tau} = \\vec{r} \\times \\vec{F} = \\frac{d\\vec{L}}{dt} = I\\vec{\\alpha}$
- Parallel Axis Theorem: $I = I_{cm} + M d^2$

### Modern Relativistic Physics
- Energy-Momentum Invariant: $E^2 = (pc)^2 + (m c^2)^2$
"""
    ch3_act2_spec = {
        "name": "Midterm Mastery Review & Formula Compendium",
        "activity_type": ActivityTypeEnum.TYPE_DYNAMIC,
        "activity_sub_type": ActivitySubTypeEnum.SUBTYPE_DYNAMIC_PAGE,
        "content": {"markdown": compendium_markdown},
        "details": {"reading_time_minutes": 25},
    }
    await _get_or_create_activity(db_session, org_id, course.id, ch3.id, ch3_act2_spec, order=2)

    return {"course": course, "assignments": assignments_created}


# ============================================================================
# Course 2 Builder: Advanced Calculus & Linear Algebra (MATH-401)
# ============================================================================
async def _build_math_course(
    db_session: AsyncSession,
    org_id: int,
    alex_id: Optional[int],
    maya_id: Optional[int],
) -> Dict[str, Any]:
    """Constructs Course 2: Advanced Calculus & Linear Algebra."""
    course_spec = {
        "name": "Advanced Calculus & Linear Algebra",
        "description": "Rigorous multivariable calculus, vector differential geometry, linear mappings, spectral theory, and tensor analysis.",
        "about": (
            "A university-caliber mathematics curriculum integrating multivariable differentiation, multiple integration in curvilinear "
            "coordinates, vector field calculus (Green's, Stokes', Divergence theorems), and matrix decompositions (SVD, Jordan normal forms)."
        ),
        "learnings": (
            "1. Compute directional gradients, multivariable Hessians, and Jacobians.\n"
            "2. Optimize constrained non-linear objective functions with Lagrange multipliers.\n"
            "3. Evaluate multidimensional surface and volume integrals using coordinate transformations.\n"
            "4. Verify Green's Theorem, Stokes' Theorem, and Gauss' Divergence Theorem.\n"
            "5. Compute eigenvalues, eigenvectors, orthogonal projections, and Singular Value Decomposition (SVD)."
        ),
        "tags": "mathematics,calculus,linear-algebra,matrices,svd,vector-calculus",
        "thumbnail_image": "https://images.unsplash.com/photo-1509228468518-180dd4864904?auto=format&fit=crop&w=1200&q=80",
    }
    course = await _get_or_create_course(db_session, org_id, course_spec)
    assignments_created = {}

    # Chapter 1: Multivariable Differentiation & Gradient Fields
    ch1_spec = {
        "name": "Multivariable Differentiation & Gradient Fields",
        "description": "Partial derivatives, Jacobians, directional derivatives, Hessian quadratic forms, and constrained optimization.",
    }
    ch1 = await _get_or_create_chapter(db_session, org_id, course.id, ch1_spec, order=1)

    ch1_act1_spec = {
        "name": "Partial Derivatives, Jacobians & Directional Gradients",
        "activity_type": ActivityTypeEnum.TYPE_VIDEO,
        "activity_sub_type": ActivitySubTypeEnum.SUBTYPE_VIDEO_YOUTUBE,
        "content": {"youtube_id": "dQw4w9WgXcQ"},
        "details": {
            "video_provider": "youtube",
            "youtube_id": "dQw4w9WgXcQ",
            "duration_seconds": 3100,
            "timestamps": [
                {"time": "00:00", "title": "Scalar Fields & The Multivariable Gradient Vector ∇f"},
                {"time": "09:30", "title": "Directional Derivatives: D_u f = ∇f · u"},
                {"time": "18:40", "title": "The Jacobian Matrix for Vector-Valued Mappings F: R^n -> R^m"},
                {"time": "28:15", "title": "Multivariate Chain Rule & Coordinate Transformations"},
            ],
        },
    }
    await _get_or_create_activity(db_session, org_id, course.id, ch1.id, ch1_act1_spec, order=1)

    diff_markdown = """# Hessian Matrices & Constrained Optimization

For a scalar field $f: \\mathbb{R}^n \\to \\mathbb{R}$, the second-order behavior is captured by the symmetric Hessian matrix:

$$\\mathbf{H}(f)_{ij} = \\frac{\\partial^2 f}{\\partial x_i \\partial x_j}$$

## Second Derivative Test for Multivariable Critical Points:
1. **Local Minimum**: All eigenvalues $\\lambda_i > 0$ (Positive Definite).
2. **Local Maximum**: All eigenvalues $\\lambda_i < 0$ (Negative Definite).
3. **Saddle Point**: Eigenvalues have mixed signs.

## Method of Lagrange Multipliers:
To optimize $f(\\vec{x})$ subject to $g(\\vec{x}) = c$:

$$\\nabla f(\\vec{x}) = \\lambda \\nabla g(\\vec{x}), \\quad g(\\vec{x}) = c$$
"""
    ch1_act2_spec = {
        "name": "Hessian Matrices, Taylor Expansions & Constrained Optimization (Lagrange Multipliers)",
        "activity_type": ActivityTypeEnum.TYPE_DYNAMIC,
        "activity_sub_type": ActivitySubTypeEnum.SUBTYPE_DYNAMIC_PAGE,
        "content": {"markdown": diff_markdown},
        "details": {"reading_time_minutes": 22},
    }
    ch1_act2 = await _get_or_create_activity(db_session, org_id, course.id, ch1.id, ch1_act2_spec, order=2)

    math_quiz_1 = {
        "quiz_title": "Hessian Matrix & Extrema Verification",
        "questions": [
            {
                "id": "mq1",
                "question": "If det(H) < 0 for a function f(x,y) at a critical point where ∇f = 0, what type of point is it?",
                "options": ["Saddle Point", "Local Minimum", "Local Maximum", "Inconclusive"],
                "correct_option_index": 0,
                "explanation": "A negative Hessian determinant in 2D indicates eigenvalues of opposite signs (λ₁ λ₂ < 0), proving a saddle point.",
            },
            {
                "id": "mq2",
                "question": "In Lagrange multiplier optimization ∇f = λ ∇g, what does the geometric tangency condition imply?",
                "options": [
                    "Level curves of f and constraint curve g share a common normal vector",
                    "f and g are orthogonal everywhere",
                    "The gradient of f vanishes identically",
                    "λ is always equal to 1",
                ],
                "correct_option_index": 0,
                "explanation": "∇f and ∇g are parallel at the constrained extremum, meaning their level tangent planes coincide.",
            },
        ],
    }
    await _get_or_create_block(db_session, org_id, course.id, ch1.id, ch1_act2.id, BlockTypeEnum.BLOCK_QUIZ, math_quiz_1)

    ch1_act3_spec = {
        "name": "SpeedGrader Practicum: Multivariable Optimization & Saddle Point Classification",
        "activity_type": ActivityTypeEnum.TYPE_ASSIGNMENT,
        "activity_sub_type": ActivitySubTypeEnum.SUBTYPE_ASSIGNMENT_ANY,
        "content": {},
        "details": {"speedgrader_enabled": True},
    }
    ch1_act3 = await _get_or_create_activity(db_session, org_id, course.id, ch1.id, ch1_act3_spec, order=3)

    math_asg1_spec = {
        "title": "SpeedGrader Practicum: Multivariable Optimization & Saddle Point Classification",
        "description": "Implement gradient descent with momentum in Python to solve non-convex multivariable optimization and classify critical points.",
        "grading_type": GradingTypeEnum.PERCENTAGE,
        "pass_threshold_percentage": 70.0,
    }
    math_asg1 = await _get_or_create_assignment(db_session, org_id, course.id, ch1.id, ch1_act3.id, math_asg1_spec)
    assignments_created["math_practicum_1"] = math_asg1

    m_task1 = await _get_or_create_assignment_task(
        db_session, org_id, course.id, ch1.id, ch1_act3.id, math_asg1.id,
        {
            "title": "Task 1: Gradient Descent with Momentum Implementation",
            "description": "Write a Python function implementing gradient descent with Nesterov momentum on Rosenbrock's function.",
            "assignment_type": AssignmentTaskTypeEnum.CODE,
            "max_grade_value": 50,
            "contents": {"language": "python"},
        }
    )
    m_task2 = await _get_or_create_assignment_task(
        db_session, org_id, course.id, ch1.id, ch1_act3.id, math_asg1.id,
        {
            "title": "Task 2: Analytical Lagrange Multiplier Proof",
            "description": "Find the maximum volume of an ellipsoid x²/a² + y²/b² + z²/c² = 1 inscribed box analytically.",
            "assignment_type": AssignmentTaskTypeEnum.SHORT_ANSWER,
            "max_grade_value": 50,
            "contents": {},
        }
    )

    if alex_id:
        await _get_or_create_task_submission(db_session, m_task1, alex_id, {"grade": 47, "feedback": "Solid momentum convergence implementation."})
        await _get_or_create_task_submission(db_session, m_task2, alex_id, {"grade": 47, "feedback": "Accurate box volume optimization: V = 8abc/(3√3)."})
        await _get_or_create_user_submission(db_session, math_asg1.id, alex_id, {"grade": 94, "overall_feedback": "Excellent performance on multivariable optimization."})

    if maya_id:
        await _get_or_create_task_submission(db_session, m_task1, maya_id, {"grade": 50, "feedback": "Flawless vectorized Nesterov accelerated gradient."})
        await _get_or_create_task_submission(db_session, m_task2, maya_id, {"grade": 49, "feedback": "Elegant proof using bordered Hessian second-order conditions."})
        await _get_or_create_user_submission(db_session, math_asg1.id, maya_id, {"grade": 99, "overall_feedback": "Mastery level mathematical proof and numerical optimization."})

    # Chapter 2: Multiple Integrals & Vector Calculus
    ch2_spec = {
        "name": "Multiple Integrals & Vector Calculus",
        "description": "Fubini's theorem, coordinate transformations, line integrals, surface flux, Green's theorem, and Stokes' theorem.",
    }
    ch2 = await _get_or_create_chapter(db_session, org_id, course.id, ch2_spec, order=2)

    ch2_act1_spec = {
        "name": "Fubini's Theorem, Cylindrical/Spherical Coordinate Changes & Jacobians",
        "activity_type": ActivityTypeEnum.TYPE_VIDEO,
        "activity_sub_type": ActivitySubTypeEnum.SUBTYPE_VIDEO_YOUTUBE,
        "content": {"youtube_id": "dQw4w9WgXcQ"},
        "details": {"duration_seconds": 2950},
    }
    await _get_or_create_activity(db_session, org_id, course.id, ch2.id, ch2_act1_spec, order=1)

    ch2_act2_spec = {
        "name": "Line Integrals, Green's Theorem, Divergence & Stokes' Theorem",
        "activity_type": ActivityTypeEnum.TYPE_DYNAMIC,
        "activity_sub_type": ActivitySubTypeEnum.SUBTYPE_DYNAMIC_PAGE,
        "content": {
            "markdown": (
                "# Classical Theorems of Vector Calculus\n\n"
                "## 1. Green's Theorem in the Plane\n\n"
                "$$\\oint_{\\partial D} (L dx + M dy) = \\iint_D \\left(\\frac{\\partial M}{\\partial x} - \\frac{\\partial L}{\\partial y}\\right) dA$$\n\n"
                "## 2. Stokes' Theorem on Manifolds\n\n"
                "$$\\oint_{\\partial \\Sigma} \\vec{F} \\cdot d\\vec{r} = \\iint_\\Sigma (\\nabla \\times \\vec{F}) \\cdot d\\vec{S}$$\n\n"
                "## 3. Gauss' Divergence Theorem\n\n"
                "$$\\oiint_{\\partial V} \\vec{F} \\cdot d\\vec{S} = \\iiint_V (\\nabla \\cdot \\vec{F}) dV$$"
            )
        },
        "details": {"reading_time_minutes": 24},
    }
    ch2_act2 = await _get_or_create_activity(db_session, org_id, course.id, ch2.id, ch2_act2_spec, order=2)

    vector_quiz = {
        "quiz_title": "Vector Theorems Knowledge Check",
        "questions": [
            {
                "id": "vq1",
                "question": "What is the physical interpretation of ∇ · F = 0 throughout a region?",
                "options": ["The vector field is incompressible (solenoidal)", "The field is irrotational", "The field is conservative", "The line integral is zero"],
                "correct_option_index": 0,
                "explanation": "Zero divergence implies no net sources or sinks, meaning the flow is solenoidal / incompressible.",
            }
        ],
    }
    await _get_or_create_block(db_session, org_id, course.id, ch2.id, ch2_act2.id, BlockTypeEnum.BLOCK_QUIZ, vector_quiz)

    # Activity 3: SpeedGrader Problem Set
    ch2_act3_spec = {
        "name": "SpeedGrader Problem Set: Flux Integrals & Maxwell Field Divergence",
        "activity_type": ActivityTypeEnum.TYPE_ASSIGNMENT,
        "activity_sub_type": ActivitySubTypeEnum.SUBTYPE_ASSIGNMENT_ANY,
        "content": {},
        "details": {"speedgrader_enabled": True},
    }
    ch2_act3 = await _get_or_create_activity(db_session, org_id, course.id, ch2.id, ch2_act3_spec, order=3)

    math_asg2_spec = {
        "title": "SpeedGrader Problem Set: Flux Integrals & Maxwell Field Divergence",
        "description": "Calculate closed surface flux integrals and apply Gauss' Divergence theorem to electrostatic and magnetostatic vector fields.",
        "grading_type": GradingTypeEnum.PERCENTAGE,
        "pass_threshold_percentage": 70.0,
    }
    math_asg2 = await _get_or_create_assignment(db_session, org_id, course.id, ch2.id, ch2_act3.id, math_asg2_spec)
    assignments_created["math_flux_asg"] = math_asg2

    m2_task1 = await _get_or_create_assignment_task(
        db_session, org_id, course.id, ch2.id, ch2_act3.id, math_asg2.id,
        {
            "title": "Task 1: Surface Flux Computation",
            "description": "Compute the net outward flux of F(x,y,z) = (x^3, y^3, z^3) across the unit sphere x^2 + y^2 + z^2 = 1.",
            "assignment_type": AssignmentTaskTypeEnum.SHORT_ANSWER,
            "max_grade_value": 50,
            "contents": {},
        }
    )
    m2_task2 = await _get_or_create_assignment_task(
        db_session, org_id, course.id, ch2.id, ch2_act3.id, math_asg2.id,
        {
            "title": "Task 2: Differential Form Verification of Stokes' Theorem",
            "description": "Verify Stokes' theorem for F(x,y,z) = (-y, x, z) over the upper hemisphere oriented upward.",
            "assignment_type": AssignmentTaskTypeEnum.SHORT_ANSWER,
            "max_grade_value": 50,
            "contents": {},
        }
    )

    if alex_id:
        await _get_or_create_task_submission(db_session, m2_task1, alex_id, {"grade": 45, "feedback": "Accurate application of divergence theorem: Flux = 12pi/5."})
        await _get_or_create_task_submission(db_session, m2_task2, alex_id, {"grade": 46, "feedback": "Proper line integral parameterization along boundary circle."})
        await _get_or_create_user_submission(db_session, math_asg2.id, alex_id, {"grade": 91, "overall_feedback": "Strong vector calculus proofs."})

    if maya_id:
        await _get_or_create_task_submission(db_session, m2_task1, maya_id, {"grade": 49, "feedback": "Flawless spherical coordinate volume integration."})
        await _get_or_create_task_submission(db_session, m2_task2, maya_id, {"grade": 48, "feedback": "Rigorous differential forms proof."})
        await _get_or_create_user_submission(db_session, math_asg2.id, maya_id, {"grade": 97, "overall_feedback": "Exemplary mathematical execution."})

    # Chapter 3: Linear Transformations & Spectral Decompositions
    ch3_spec = {
        "name": "Linear Transformations & Spectral Decompositions",
        "description": "Vector spaces, orthonormal bases, Spectral Theorem for symmetric operators, and Singular Value Decomposition (SVD).",
    }
    ch3 = await _get_or_create_chapter(db_session, org_id, course.id, ch3_spec, order=3)

    ch3_act1_spec = {
        "name": "Vector Spaces, Fundamental Subspaces & Orthogonal Projections",
        "activity_type": ActivityTypeEnum.TYPE_VIDEO,
        "activity_sub_type": ActivitySubTypeEnum.SUBTYPE_VIDEO_YOUTUBE,
        "content": {"youtube_id": "dQw4w9WgXcQ"},
        "details": {"duration_seconds": 2800},
    }
    await _get_or_create_activity(db_session, org_id, course.id, ch3.id, ch3_act1_spec, order=1)

    ch3_act2_spec = {
        "name": "Eigenvalues, Spectral Theorem & Singular Value Decomposition (SVD)",
        "activity_type": ActivityTypeEnum.TYPE_DYNAMIC,
        "activity_sub_type": ActivitySubTypeEnum.SUBTYPE_DYNAMIC_PAGE,
        "content": {
            "markdown": (
                "# Spectral Decomposition & SVD\n\n"
                "Every real $m \\times n$ matrix $A$ admits a Singular Value Decomposition:\n\n"
                "$$A = U \\Sigma V^T$$\n\n"
                "- $U \\in \\mathbb{R}^{m \\times m}$: Orthonormal eigenvectors of $A A^T$\n"
                "- $\\Sigma \\in \\mathbb{R}^{m \\times n}$: Diagonal matrix of singular values $\\sigma_i = \\sqrt{\\lambda_i(A^T A)}$\n"
                "- $V \\in \\mathbb{R}^{n \\times n}$: Orthonormal eigenvectors of $A^T A$\n"
            )
        },
        "details": {"reading_time_minutes": 20},
    }
    ch3_act2 = await _get_or_create_activity(db_session, org_id, course.id, ch3.id, ch3_act2_spec, order=2)

    svd_quiz = {
        "quiz_title": "Spectral Theory & SVD Quick Check",
        "questions": [
            {
                "id": "sq1",
                "question": "What is the rank of matrix A given its non-zero singular values σ_1 ≥ ... ≥ σ_r > 0?",
                "options": ["rank(A) = r", "rank(A) = min(m, n)", "rank(A) = trace(A)", "rank(A) = det(A)"],
                "correct_option_index": 0,
                "explanation": "The number of strictly positive singular values equals the exact algebraic rank of the matrix.",
            }
        ],
    }
    await _get_or_create_block(db_session, org_id, course.id, ch3.id, ch3_act2.id, BlockTypeEnum.BLOCK_QUIZ, svd_quiz)

    ch3_act3_spec = {
        "name": "Spectral Theory & Matrix Decompositions Quick Reference Compendium",
        "activity_type": ActivityTypeEnum.TYPE_DOCUMENT,
        "activity_sub_type": ActivitySubTypeEnum.SUBTYPE_DOCUMENT_PDF,
        "content": {"file_url": "/documents/math401-spectral-theory-handbook.pdf", "title": "Spectral Theory Compendium"},
        "details": {"pages": 30},
    }
    await _get_or_create_activity(db_session, org_id, course.id, ch3.id, ch3_act3_spec, order=3)

    return {"course": course, "assignments": assignments_created}


# ============================================================================
# Course 3 Builder: World History & Global Perspectives (HIST-201)
# ============================================================================
async def _build_history_course(
    db_session: AsyncSession,
    org_id: int,
    alex_id: Optional[int],
    maya_id: Optional[int],
    leo_id: Optional[int],
) -> Dict[str, Any]:
    """Constructs Course 3: World History & Global Perspectives."""
    course_spec = {
        "name": "World History & Global Perspectives",
        "description": "Comparative analysis of global political transformations, technological revolutions, institutional evolutions, and multilateral diplomacy.",
        "about": (
            "Investigates major turning points in modern global history from the Enlightenment through contemporary international relations. "
            "Fosters critical historiographical thinking, Document-Based Question (DBQ) analysis, and academic writing."
        ),
        "learnings": (
            "1. Evaluate the intellectual and socioeconomic origins of the Atlantic Revolutions.\n"
            "2. Analyze industrialization, global capital networks, and colonial labor regimes.\n"
            "3. Assess 20th-century multilateral diplomacy, the Cold War, and decolonization movements.\n"
            "4. Construct rigorous thesis-driven historical essays supported by primary source evidence."
        ),
        "tags": "history,global-perspectives,enlightenment,diplomacy,social-sciences",
        "thumbnail_image": "https://images.unsplash.com/photo-1461360370896-922624d12aa1?auto=format&fit=crop&w=1200&q=80",
    }
    course = await _get_or_create_course(db_session, org_id, course_spec)
    assignments_created = {}

    # Chapter 1: The Enlightenment & Revolutionary Transformations
    ch1_spec = {
        "name": "The Enlightenment & Revolutionary Transformations",
        "description": "Philosophes, social contract theory, the Atlantic Revolutions (American, French, Haitian), and human rights declarations.",
    }
    ch1 = await _get_or_create_chapter(db_session, org_id, course.id, ch1_spec, order=1)

    ch1_act1_spec = {
        "name": "The Social Contract, Intellectual Networks & The Atlantic Revolutions",
        "activity_type": ActivityTypeEnum.TYPE_VIDEO,
        "activity_sub_type": ActivitySubTypeEnum.SUBTYPE_VIDEO_YOUTUBE,
        "content": {"youtube_id": "dQw4w9WgXcQ"},
        "details": {
            "duration_seconds": 2750,
            "timestamps": [
                {"time": "00:00", "title": "The Enlightenment Republic of Letters: Locke, Voltaire & Rousseau"},
                {"time": "10:15", "title": "Popular Sovereignty vs Divine Right of Kings"},
                {"time": "21:30", "title": "The Haitian Revolution (1791–1804): Toussaint Louverture & Global Emancipation"},
            ],
        },
    }
    await _get_or_create_activity(db_session, org_id, course.id, ch1.id, ch1_act1_spec, order=1)

    dbq_markdown = """# Comparative Analysis: Atlantic Revolutions

The late 18th and early 19th centuries witnessed connected democratic uprisings across the Atlantic world:

## Primary Source Excerpt A: Jean-Jacques Rousseau, *The Social Contract* (1762)
> *"Man is born free, and everywhere he is in chains. Those who think themselves the masters of others are indeed greater slaves than they."*

## Primary Source Excerpt B: *The Haitian Declaration of Independence* (1804)
> *"We have dared to be free, let us be thus by ourselves and for ourselves... Let us render eternal the hatred of the French."*

---

### Comparative Matrix
| Metric | American Revolution (1776) | French Revolution (1789) | Haitian Revolution (1791) |
| :--- | :--- | :--- | :--- |
| **Core Impetus** | Anti-colonial taxation & representation | Feudal class inequality & fiscal crisis | Radical abolition of chattel slavery & anti-colonialism |
| **Outcome** | Constitutional Republic | Republic -> Terror -> Empire | First Independent Black Republic |
"""
    ch1_act2_spec = {
        "name": "Comparative Analysis: American, French & Haitian Revolutions",
        "activity_type": ActivityTypeEnum.TYPE_DYNAMIC,
        "activity_sub_type": ActivitySubTypeEnum.SUBTYPE_DYNAMIC_PAGE,
        "content": {"markdown": dbq_markdown},
        "details": {"reading_time_minutes": 20},
    }
    ch1_act2 = await _get_or_create_activity(db_session, org_id, course.id, ch1.id, ch1_act2_spec, order=2)

    hist_quiz = {
        "quiz_title": "Atlantic Revolutions Primary Source Check",
        "questions": [
            {
                "id": "hq1",
                "question": "What made the Haitian Revolution unique among Atlantic revolutions?",
                "options": [
                    "It was the only successful enslaved-led rebellion resulting in an independent nation",
                    "It was strictly a tax dispute with Britain",
                    "It restored the French Bourbon monarchy",
                    "It had no primary source documentation",
                ],
                "correct_option_index": 0,
                "explanation": "The Haitian Revolution achieved both the abolition of slavery and complete national independence.",
            }
        ],
    }
    await _get_or_create_block(db_session, org_id, course.id, ch1.id, ch1_act2.id, BlockTypeEnum.BLOCK_QUIZ, hist_quiz)

    ch1_act3_spec = {
        "name": "SpeedGrader DBQ: The Haitian Revolution & Global Human Rights",
        "activity_type": ActivityTypeEnum.TYPE_ASSIGNMENT,
        "activity_sub_type": ActivitySubTypeEnum.SUBTYPE_ASSIGNMENT_ANY,
        "content": {},
        "details": {"speedgrader_enabled": True},
    }
    ch1_act3 = await _get_or_create_activity(db_session, org_id, course.id, ch1.id, ch1_act3_spec, order=3)

    dbq_asg_spec = {
        "title": "SpeedGrader DBQ: The Haitian Revolution & Global Human Rights",
        "description": "Document-Based Essay analyzing the ideological and geopolitical reverberations of the Haitian Revolution across the Atlantic world.",
        "grading_type": GradingTypeEnum.PERCENTAGE,
        "pass_threshold_percentage": 70.0,
    }
    dbq_asg = await _get_or_create_assignment(db_session, org_id, course.id, ch1.id, ch1_act3.id, dbq_asg_spec)
    assignments_created["hist_dbq_1"] = dbq_asg

    dbq_t1 = await _get_or_create_assignment_task(
        db_session, org_id, course.id, ch1.id, ch1_act3.id, dbq_asg.id,
        {
            "title": "Task 1: Primary Document Synthesis & Sourcing (HIPP Analysis)",
            "description": "Provide Historical context, Intended audience, Purpose, and Point of View (HIPP) for Documents A and B.",
            "assignment_type": AssignmentTaskTypeEnum.SHORT_ANSWER,
            "max_grade_value": 50,
            "contents": {},
        }
    )
    dbq_t2 = await _get_or_create_assignment_task(
        db_session, org_id, course.id, ch1.id, ch1_act3.id, dbq_asg.id,
        {
            "title": "Task 2: Thesis-Driven Comparative Essay",
            "description": "Write a 500-750 word essay evaluating how the Haitian Revolution redefined universal human rights.",
            "assignment_type": AssignmentTaskTypeEnum.SHORT_ANSWER,
            "max_grade_value": 50,
            "contents": {},
        }
    )

    if alex_id:
        await _get_or_create_task_submission(db_session, dbq_t1, alex_id, {"grade": 45, "feedback": "Well-structured HIPP analysis."})
        await _get_or_create_task_submission(db_session, dbq_t2, alex_id, {"grade": 45, "feedback": "Strong thesis connecting Atlantic enlightenment thought to Louverture's constitution."})
        await _get_or_create_user_submission(db_session, dbq_asg.id, alex_id, {"grade": 90, "overall_feedback": "Commendable historiographical rigor."})

    if maya_id:
        await _get_or_create_task_submission(db_session, dbq_t1, maya_id, {"grade": 48, "feedback": "Sophisticated contextualization of French colonial mercantilism."})
        await _get_or_create_task_submission(db_session, dbq_t2, maya_id, {"grade": 48, "feedback": "Brilliant argumentative essay with nuanced source synthesis."})
        await _get_or_create_user_submission(db_session, dbq_asg.id, maya_id, {"grade": 96, "overall_feedback": "Exceptional historical writing, Maya."})

    if leo_id:
        await _get_or_create_task_submission(db_session, dbq_t1, leo_id, {"grade": 46, "feedback": "Very good source evaluation."})
        await _get_or_create_task_submission(db_session, dbq_t2, leo_id, {"grade": 46, "feedback": "Compelling comparative arguments."})
        await _get_or_create_user_submission(db_session, dbq_asg.id, leo_id, {"grade": 92, "overall_feedback": "Great analytical depth and historical synthesis."})

    # Chapter 2: Industrialization & Global Economic Shifts
    ch2_spec = {
        "name": "Industrialization & Global Economic Shifts",
        "description": "The steam age, global commodity flows, labor movements, and imperialism.",
    }
    ch2 = await _get_or_create_chapter(db_session, org_id, course.id, ch2_spec, order=2)

    await _get_or_create_activity(
        db_session, org_id, course.id, ch2.id,
        {
            "name": "The Steam Age, Capital Accumulation & Global Trade Networks",
            "activity_type": ActivityTypeEnum.TYPE_VIDEO,
            "activity_sub_type": ActivitySubTypeEnum.SUBTYPE_VIDEO_YOUTUBE,
            "content": {"youtube_id": "dQw4w9WgXcQ"},
            "details": {"duration_seconds": 2600},
        },
        order=1,
    )
    await _get_or_create_activity(
        db_session, org_id, course.id, ch2.id,
        {
            "name": "Primary Sources: Labor Conditions, Parliamentary Reports & Economic Treatises (1780-1890)",
            "activity_type": ActivityTypeEnum.TYPE_DOCUMENT,
            "activity_sub_type": ActivitySubTypeEnum.SUBTYPE_DOCUMENT_PDF,
            "content": {"file_url": "/documents/hist-industrial-labor-sources.pdf", "title": "Industrial Labor Compendium"},
            "details": {"pages": 40},
        },
        order=2,
    )

    ch2_act3_spec = {
        "name": "Colonialism, Imperial Expansion & Resource Extraction Geopolitics",
        "activity_type": ActivityTypeEnum.TYPE_DYNAMIC,
        "activity_sub_type": ActivitySubTypeEnum.SUBTYPE_DYNAMIC_PAGE,
        "content": {
            "markdown": (
                "# Imperial Expansion & Global Resource Networks\n\n"
                "The late 19th century Scramble for Africa and Asian concessions established coerced global economic extraction networks:\n\n"
                "- **The Berlin Conference (1884–1885)**: Partition of Africa without indigenous representation.\n"
                "- **Export-Oriented Monocultures**: Rubber in the Congo Basin, cotton in the Nile Delta, tea in Assam.\n"
            )
        },
        "details": {"reading_time_minutes": 18},
    }
    ch2_act3 = await _get_or_create_activity(db_session, org_id, course.id, ch2.id, ch2_act3_spec, order=3)

    imp_quiz = {
        "quiz_title": "19th Century Imperialism Quick Check",
        "questions": [
            {
                "id": "iq1",
                "question": "What was a defining geopolitical consequence of the 1884–1885 Berlin Conference?",
                "options": [
                    "Borders were drawn across Africa ignoring ethnic, linguistic, and ecological boundaries",
                    "Immediate decolonization of all African territories",
                    "Abolition of all international maritime trade",
                    "Establishment of the League of Nations",
                ],
                "correct_option_index": 0,
                "explanation": "European powers carved Africa into arbitrary spheres of influence, disregarding preexisting political and cultural borders.",
            }
        ],
    }
    await _get_or_create_block(db_session, org_id, course.id, ch2.id, ch2_act3.id, BlockTypeEnum.BLOCK_QUIZ, imp_quiz)

    # Chapter 3: 20th Century Dynamics & Multilateral Treaties
    ch3_spec = {
        "name": "20th Century Dynamics & Multilateral Treaties",
        "description": "Total war, the League of Nations, United Nations, Bretton Woods institutions, and post-colonial sovereignty.",
    }
    ch3 = await _get_or_create_chapter(db_session, org_id, course.id, ch3_spec, order=3)

    await _get_or_create_activity(
        db_session, org_id, course.id, ch3.id,
        {
            "name": "Total War, Decolonization & The Post-1945 International Order",
            "activity_type": ActivityTypeEnum.TYPE_VIDEO,
            "activity_sub_type": ActivitySubTypeEnum.SUBTYPE_VIDEO_YOUTUBE,
            "content": {"youtube_id": "dQw4w9WgXcQ"},
            "details": {"duration_seconds": 2900},
        },
        order=1,
    )

    ch3_act2_spec = {
        "name": "The Cold War, Non-Aligned Movement & Globalization Dynamics",
        "activity_type": ActivityTypeEnum.TYPE_DYNAMIC,
        "activity_sub_type": ActivitySubTypeEnum.SUBTYPE_DYNAMIC_PAGE,
        "content": {
            "markdown": (
                "# The Cold War & The Non-Aligned Movement (NAM)\n\n"
                "The Bandung Conference of 1955 gathered 29 Asian and African states to establish positive neutrality, "
                "sovereign self-determination, and anti-imperial solidarity between Western and Soviet power blocs."
            )
        },
        "details": {"reading_time_minutes": 22},
    }
    ch3_act2 = await _get_or_create_activity(db_session, org_id, course.id, ch3.id, ch3_act2_spec, order=2)

    coldwar_quiz = {
        "quiz_title": "Cold War Diplomacy Check",
        "questions": [
            {
                "id": "cw1",
                "question": "What core principle was articulated at the 1955 Bandung Conference?",
                "options": [
                    "Mutual non-interference and rejection of military alliances with superpowers",
                    "Unconditional alignment with NATO",
                    "Dissolution of the United Nations General Assembly",
                    "Establishment of the Warsaw Pact",
                ],
                "correct_option_index": 0,
                "explanation": "The Bandung Ten Principles established the core doctrine of the Non-Aligned Movement, championing self-determination and peaceful coexistence.",
            }
        ],
    }
    await _get_or_create_block(db_session, org_id, course.id, ch3.id, ch3_act2.id, BlockTypeEnum.BLOCK_QUIZ, coldwar_quiz)

    # SpeedGrader Capstone Assignment
    ch3_act3_spec = {
        "name": "SpeedGrader Capstone: Diplomacy, Treaties & The Evolution of International Law",
        "activity_type": ActivityTypeEnum.TYPE_ASSIGNMENT,
        "activity_sub_type": ActivitySubTypeEnum.SUBTYPE_ASSIGNMENT_ANY,
        "content": {},
        "details": {"speedgrader_enabled": True},
    }
    ch3_act3 = await _get_or_create_activity(db_session, org_id, course.id, ch3.id, ch3_act3_spec, order=3)

    capstone_asg_spec = {
        "title": "SpeedGrader Capstone: Diplomacy, Treaties & The Evolution of International Law",
        "description": "Comprehensive capstone analyzing post-WWII multilateral treaties, sovereignty disputes, and Geneva Conventions enforcement.",
        "grading_type": GradingTypeEnum.PERCENTAGE,
        "pass_threshold_percentage": 70.0,
    }
    cap_asg = await _get_or_create_assignment(db_session, org_id, course.id, ch3.id, ch3_act3.id, capstone_asg_spec)
    assignments_created["hist_capstone"] = cap_asg

    cap_t1 = await _get_or_create_assignment_task(
        db_session, org_id, course.id, ch3.id, ch3_act3.id, cap_asg.id,
        {
            "title": "Task 1: Multilateral Treaty Clause Comparative Synthesis",
            "description": "Compare Chapter VII UN Charter enforcement mechanisms with the League of Nations Covenant Article 16.",
            "assignment_type": AssignmentTaskTypeEnum.SHORT_ANSWER,
            "max_grade_value": 50,
            "contents": {},
        }
    )
    cap_t2 = await _get_or_create_assignment_task(
        db_session, org_id, course.id, ch3.id, ch3_act3.id, cap_asg.id,
        {
            "title": "Task 2: Policy Memorandum on Contemporary Multilateral Conflict Resolution",
            "description": "Draft a policy briefing proposing diplomatic mechanisms to resolve modern territorial disputes.",
            "assignment_type": AssignmentTaskTypeEnum.SHORT_ANSWER,
            "max_grade_value": 50,
            "contents": {},
        }
    )

    if alex_id:
        await _get_or_create_task_submission(db_session, cap_t1, alex_id, {"grade": 46, "feedback": "Insightful distinction between collective security mechanisms."})
        await _get_or_create_task_submission(db_session, cap_t2, alex_id, {"grade": 47, "feedback": "Practical and structured diplomatic policy memo."})
        await _get_or_create_user_submission(db_session, cap_asg.id, alex_id, {"grade": 93, "overall_feedback": "Superb policy analysis and historical grounding."})

    if maya_id:
        await _get_or_create_task_submission(db_session, cap_t1, maya_id, {"grade": 49, "feedback": "Exemplary legal analysis of UN Security Council veto constraints."})
        await _get_or_create_task_submission(db_session, cap_t2, maya_id, {"grade": 49, "feedback": "Publication-quality policy memorandum."})
        await _get_or_create_user_submission(db_session, cap_asg.id, maya_id, {"grade": 98, "overall_feedback": "Brilliant capstone deliverable, Maya."})

    if leo_id:
        await _get_or_create_task_submission(db_session, cap_t1, leo_id, {"grade": 45, "feedback": "Solid treaty analysis."})
        await _get_or_create_task_submission(db_session, cap_t2, leo_id, {"grade": 45, "feedback": "Well-reasoned diplomatic recommendations."})
        await _get_or_create_user_submission(db_session, cap_asg.id, leo_id, {"grade": 90, "overall_feedback": "Great historical and diplomatic synthesis."})

    return {"course": course, "assignments": assignments_created}


# ============================================================================
# Course 4 Builder: Autonomous AI & Computational Science (CS-101)
# ============================================================================
async def _build_ai_course(
    db_session: AsyncSession,
    org_id: int,
    alex_id: Optional[int],
    maya_id: Optional[int],
) -> Dict[str, Any]:
    """Constructs Course 4: Autonomous AI & Computational Science."""
    course_spec = {
        "name": "Autonomous AI & Computational Science",
        "description": "Foundations of algorithms, deep neural network architectures, reinforcement learning, and autonomous multi-agent orchestration systems.",
        "about": (
            "A cutting-edge computer science and artificial intelligence curriculum covering graph algorithms, backpropagation, "
            "transformer attention mechanisms, reinforcement learning loops, and multi-agent coordination architectures."
        ),
        "learnings": (
            "1. Implement high-performance graph algorithms (Dijkstra, A*, Tarjan SCC).\n"
            "2. Construct neural network backpropagation from scratch with computational DAGs.\n"
            "3. Implement scaled dot-product multi-head self-attention in PyTorch.\n"
            "4. Design resilient autonomous multi-agent pipelines with consensus protocols and tool calling."
        ),
        "tags": "computer-science,ai,multi-agent,algorithms,transformers,deep-learning,python",
        "thumbnail_image": "https://images.unsplash.com/photo-1618005182384-a83a8bd57fbe?auto=format&fit=crop&w=1200&q=80",
    }
    course = await _get_or_create_course(db_session, org_id, course_spec)
    assignments_created = {}

    # Chapter 1: Algorithmic Complexity & Graph Systems
    ch1_spec = {
        "name": "Algorithmic Complexity & Graph Systems",
        "description": "Asymptotic analysis, divide-and-conquer, dynamic programming, shortest paths (A*), and flow networks.",
    }
    ch1 = await _get_or_create_chapter(db_session, org_id, course.id, ch1_spec, order=1)

    ch1_act1_spec = {
        "name": "Asymptotic Notation, Divide-and-Conquer & Dynamic Programming",
        "activity_type": ActivityTypeEnum.TYPE_VIDEO,
        "activity_sub_type": ActivitySubTypeEnum.SUBTYPE_VIDEO_YOUTUBE,
        "content": {"youtube_id": "dQw4w9WgXcQ"},
        "details": {"duration_seconds": 3200},
    }
    await _get_or_create_activity(db_session, org_id, course.id, ch1.id, ch1_act1_spec, order=1)

    graph_markdown = """# Graph Theory & The A* Pathfinding Algorithm

The A* search algorithm computes the shortest path between nodes by evaluating:

$$f(n) = g(n) + h(n)$$

Where:
- $g(n)$: Exact cost from start node to node $n$.
- $h(n)$: Admissible heuristic estimating cost from $n$ to goal (must never overestimate true cost: $h(n) \\le h^*(n)$).

```
        Start [g=0, h=10]
          │
         (4) Cost
          ▼
        Node A [g=4, h=6]  ──(3)──► Goal [g=7, h=0]
```
"""
    ch1_act2_spec = {
        "name": "Graph Theory: Shortest Paths (Dijkstra, A*), Minimum Spanning Trees & Flow Networks",
        "activity_type": ActivityTypeEnum.TYPE_DYNAMIC,
        "activity_sub_type": ActivitySubTypeEnum.SUBTYPE_DYNAMIC_PAGE,
        "content": {"markdown": graph_markdown},
        "details": {"reading_time_minutes": 25},
    }
    ch1_act2 = await _get_or_create_activity(db_session, org_id, course.id, ch1.id, ch1_act2_spec, order=2)

    ai_quiz_1 = {
        "quiz_title": "Graph Algorithms & Admissibility Check",
        "questions": [
            {
                "id": "aq1",
                "question": "What occurs if an A* heuristic h(n) is NOT admissible (overestimates true cost)?",
                "options": [
                    "A* is no longer guaranteed to find the optimal shortest path",
                    "The algorithm will always enter an infinite loop",
                    "Time complexity becomes strictly exponential O(2^N)",
                    "Dijkstra's algorithm will fail",
                ],
                "correct_option_index": 0,
                "explanation": "Admissibility guarantees optimality. Overestimating costs can cause A* to prune paths that lead to the true shortest route.",
            }
        ],
    }
    await _get_or_create_block(db_session, org_id, course.id, ch1.id, ch1_act2.id, BlockTypeEnum.BLOCK_QUIZ, ai_quiz_1)

    ch1_act3_spec = {
        "name": "SpeedGrader Lab: High-Performance Graph Engine & A* Pathfinding Benchmark",
        "activity_type": ActivityTypeEnum.TYPE_ASSIGNMENT,
        "activity_sub_type": ActivitySubTypeEnum.SUBTYPE_ASSIGNMENT_ANY,
        "content": {},
        "details": {"speedgrader_enabled": True},
    }
    ch1_act3 = await _get_or_create_activity(db_session, org_id, course.id, ch1.id, ch1_act3_spec, order=3)

    ai_asg1_spec = {
        "title": "SpeedGrader Lab: High-Performance Graph Engine & A* Pathfinding Benchmark",
        "description": "Construct a Python priority-queue driven A* graph solver and conduct empirical benchmarks against Dijkstra.",
        "grading_type": GradingTypeEnum.PERCENTAGE,
        "pass_threshold_percentage": 70.0,
    }
    ai_asg1 = await _get_or_create_assignment(db_session, org_id, course.id, ch1.id, ch1_act3.id, ai_asg1_spec)
    assignments_created["cs_lab_1"] = ai_asg1

    t1 = await _get_or_create_assignment_task(
        db_session, org_id, course.id, ch1.id, ch1_act3.id, ai_asg1.id,
        {
            "title": "Task 1: Python A* Graph Engine Implementation with heapq",
            "description": "Implement a modular A* pathfinder with Euclidean and Manhattan heuristic plugins.",
            "assignment_type": AssignmentTaskTypeEnum.CODE,
            "max_grade_value": 50,
            "contents": {"language": "python"},
        }
    )
    t2 = await _get_or_create_assignment_task(
        db_session, org_id, course.id, ch1.id, ch1_act3.id, ai_asg1.id,
        {
            "title": "Task 2: Asymptotic Complexity & Empirical Benchmark Report",
            "description": "Benchmark node expansion rates on 10,000-node random geometric graphs.",
            "assignment_type": AssignmentTaskTypeEnum.SHORT_ANSWER,
            "max_grade_value": 50,
            "contents": {},
        }
    )

    if alex_id:
        await _get_or_create_task_submission(db_session, t1, alex_id, {"grade": 48, "feedback": "Clean priority-queue implementation with tight memory bounds."})
        await _get_or_create_task_submission(db_session, t2, alex_id, {"grade": 48, "feedback": "Excellent benchmark visualizations showing 8.4x fewer node expansions."})
        await _get_or_create_user_submission(db_session, ai_asg1.id, alex_id, {"grade": 96, "overall_feedback": "Outstanding computational science submission."})

    if maya_id:
        await _get_or_create_task_submission(db_session, t1, maya_id, {"grade": 50, "feedback": "Flawless bidirectional A* with consistent heuristics."})
        await _get_or_create_task_submission(db_session, t2, maya_id, {"grade": 50, "feedback": "Exceptional asymptotic proof of heuristic dominance."})
        await _get_or_create_user_submission(db_session, ai_asg1.id, maya_id, {"grade": 100, "overall_feedback": "Perfect score! Industrial-grade algorithm engineering."})

    # Chapter 2: Machine Learning Foundations & Neural Networks
    ch2_spec = {
        "name": "Machine Learning Foundations & Neural Networks",
        "description": "Computational graphs, backpropagation, attention mechanisms, and Transformer architectures.",
    }
    ch2 = await _get_or_create_chapter(db_session, org_id, course.id, ch2_spec, order=2)

    await _get_or_create_activity(
        db_session, org_id, course.id, ch2.id,
        {
            "name": "Gradient Descent, Backpropagation & Computational Graphs",
            "activity_type": ActivityTypeEnum.TYPE_VIDEO,
            "activity_sub_type": ActivitySubTypeEnum.SUBTYPE_VIDEO_YOUTUBE,
            "content": {"youtube_id": "dQw4w9WgXcQ"},
            "details": {"duration_seconds": 3300},
        },
        order=1,
    )

    tf_markdown = """# Scaled Dot-Product & Multi-Head Attention

Given Query $Q$, Key $K$, and Value $V$ matrices:

$$\\text{Attention}(Q, K, V) = \\text{softmax}\\left(\\frac{Q K^T}{\\sqrt{d_k}}\\right) V$$

Multi-Head Attention projects representations across $h$ distinct subspace heads:

$$\\text{MultiHead}(Q, K, V) = \\text{Concat}(\\text{head}_1, \\dots, \\text{head}_h) W^O$$
"""
    ch2_act2_spec = {
        "name": "Transformer Architecture, Attention Mechanisms & Self-Supervised Learning",
        "activity_type": ActivityTypeEnum.TYPE_DYNAMIC,
        "activity_sub_type": ActivitySubTypeEnum.SUBTYPE_DYNAMIC_PAGE,
        "content": {"markdown": tf_markdown},
        "details": {"reading_time_minutes": 24},
    }
    ch2_act2 = await _get_or_create_activity(db_session, org_id, course.id, ch2.id, ch2_act2_spec, order=2)

    nn_quiz = {
        "quiz_title": "Transformer & Attention Mechanism Check",
        "questions": [
            {
                "id": "nq1",
                "question": "Why is the dot product Q K^T scaled by 1/√d_k in self-attention?",
                "options": [
                    "To prevent large dot products from pushing softmax into regions with extremely small gradients",
                    "To invert the attention matrix",
                    "To reduce computational complexity from O(N^2) to O(N)",
                    "To enforce causal masking",
                ],
                "correct_option_index": 0,
                "explanation": "For large d_k, dot products grow large in magnitude, pushing softmax into near-zero gradient regions. Scaling by 1/√d_k maintains unit variance.",
            }
        ],
    }
    await _get_or_create_block(db_session, org_id, course.id, ch2.id, ch2_act2.id, BlockTypeEnum.BLOCK_QUIZ, nn_quiz)

    ch2_act3_spec = {
        "name": "SpeedGrader Project: Building a Mini-Transformer & Multi-Head Self-Attention from Scratch",
        "activity_type": ActivityTypeEnum.TYPE_ASSIGNMENT,
        "activity_sub_type": ActivitySubTypeEnum.SUBTYPE_ASSIGNMENT_ANY,
        "content": {},
        "details": {"speedgrader_enabled": True},
    }
    ch2_act3 = await _get_or_create_activity(db_session, org_id, course.id, ch2.id, ch2_act3_spec, order=3)

    tf_asg_spec = {
        "title": "SpeedGrader Project: Building a Mini-Transformer & Multi-Head Self-Attention from Scratch",
        "description": "Construct a clean PyTorch/NumPy implementation of multi-head self-attention and rotary positional embeddings.",
        "grading_type": GradingTypeEnum.PERCENTAGE,
        "pass_threshold_percentage": 70.0,
    }
    tf_asg = await _get_or_create_assignment(db_session, org_id, course.id, ch2.id, ch2_act3.id, tf_asg_spec)
    assignments_created["cs_tf_project"] = tf_asg

    tf_t1 = await _get_or_create_assignment_task(
        db_session, org_id, course.id, ch2.id, ch2_act3.id, tf_asg.id,
        {
            "title": "Task 1: Multi-Head Self-Attention Layer Implementation",
            "description": "Implement the forward pass of MultiHeadAttention with causal masking in PyTorch.",
            "assignment_type": AssignmentTaskTypeEnum.CODE,
            "max_grade_value": 50,
            "contents": {"language": "python"},
        }
    )
    tf_t2 = await _get_or_create_assignment_task(
        db_session, org_id, course.id, ch2.id, ch2_act3.id, tf_asg.id,
        {
            "title": "Task 2: Positional Encoding & Computational Complexity Analysis",
            "description": "Analyze quadratic self-attention complexity vs linear FlashAttention memory tile optimizations.",
            "assignment_type": AssignmentTaskTypeEnum.SHORT_ANSWER,
            "max_grade_value": 50,
            "contents": {},
        }
    )

    if alex_id:
        await _get_or_create_task_submission(db_session, tf_t1, alex_id, {"grade": 48, "feedback": "Well-vectorized attention heads."})
        await _get_or_create_task_submission(db_session, tf_t2, alex_id, {"grade": 47, "feedback": "Accurate O(N^2) memory footprint derivation."})
        await _get_or_create_user_submission(db_session, tf_asg.id, alex_id, {"grade": 95, "overall_feedback": "Excellent deep learning engineering."})

    if maya_id:
        await _get_or_create_task_submission(db_session, tf_t1, maya_id, {"grade": 50, "feedback": "Production-grade FlashAttention-compatible tiling!"})
        await _get_or_create_task_submission(db_session, tf_t2, maya_id, {"grade": 49, "feedback": "Comprehensive analysis of RoPE vs sinusoidal embeddings."})
        await _get_or_create_user_submission(db_session, tf_asg.id, maya_id, {"grade": 99, "overall_feedback": "Outstanding deep learning architecture mastery."})

    # Chapter 3: Autonomous Multi-Agent Orchestration
    ch3_spec = {
        "name": "Autonomous Multi-Agent Orchestration",
        "description": "Autonomous agent design, reactive loops, memory compaction, tool dispatching, and multi-agent consensus protocols.",
    }
    ch3 = await _get_or_create_chapter(db_session, org_id, course.id, ch3_spec, order=3)

    await _get_or_create_activity(
        db_session, org_id, course.id, ch3.id,
        {
            "name": "Agentic Architectures: Tool Calling, Memory Systems & Reactive Loops",
            "activity_type": ActivityTypeEnum.TYPE_VIDEO,
            "activity_sub_type": ActivitySubTypeEnum.SUBTYPE_VIDEO_YOUTUBE,
            "content": {"youtube_id": "dQw4w9WgXcQ"},
            "details": {"duration_seconds": 3100},
        },
        order=1,
    )

    agent_markdown = """# Multi-Agent Architecture & Orchestration

Autonomous systems leverage specialized agents orchestrated through directed acyclic task graphs (DAGs):

1. **Planner Agent**: Decomposes high-level intent into deterministic subtasks.
2. **Specialist Agents**: Execute specialized subtasks (code analysis, database migration, verification).
3. **Auditor / Evaluator**: Validates deliverables against security and correctness invariants.
"""
    ch3_act2_spec = {
        "name": "Multi-Agent Consensus, Task Delegation & Protocol Verification",
        "activity_type": ActivityTypeEnum.TYPE_DYNAMIC,
        "activity_sub_type": ActivitySubTypeEnum.SUBTYPE_DYNAMIC_PAGE,
        "content": {"markdown": agent_markdown},
        "details": {"reading_time_minutes": 22},
    }
    ch3_act2 = await _get_or_create_activity(db_session, org_id, course.id, ch3.id, ch3_act2_spec, order=2)

    agent_quiz = {
        "quiz_title": "Multi-Agent System Architecture Check",
        "questions": [
            {
                "id": "ag1",
                "question": "In an agentic loop, what prevents cascading hallucination during multi-step tool execution?",
                "options": [
                    "Deterministic verification hooks, unit test feedback loops, and schema validation",
                    "Increasing the temperature parameter to 2.0",
                    "Disabling tool calls entirely",
                    "Shortening the context window",
                ],
                "correct_option_index": 0,
                "explanation": "Deterministic verification loops (running tests, validating schemas, compiler checks) ground model generations in verifiable facts.",
            }
        ],
    }
    await _get_or_create_block(db_session, org_id, course.id, ch3.id, ch3_act2.id, BlockTypeEnum.BLOCK_QUIZ, agent_quiz)

    # Activity 3: SpeedGrader Capstone
    ch3_act3_spec = {
        "name": "SpeedGrader Capstone: Autonomous Multi-Agent Research & Code Refactoring Pipeline",
        "activity_type": ActivityTypeEnum.TYPE_ASSIGNMENT,
        "activity_sub_type": ActivitySubTypeEnum.SUBTYPE_ASSIGNMENT_ANY,
        "content": {},
        "details": {"speedgrader_enabled": True},
    }
    ch3_act3 = await _get_or_create_activity(db_session, org_id, course.id, ch3.id, ch3_act3_spec, order=3)

    agent_cap_spec = {
        "title": "SpeedGrader Capstone: Autonomous Multi-Agent Research & Code Refactoring Pipeline",
        "description": "Construct an end-to-end multi-agent orchestration harness capable of autonomous code refactoring and regression testing.",
        "grading_type": GradingTypeEnum.PERCENTAGE,
        "pass_threshold_percentage": 70.0,
    }
    agent_cap = await _get_or_create_assignment(db_session, org_id, course.id, ch3.id, ch3_act3.id, agent_cap_spec)
    assignments_created["cs_agent_capstone"] = agent_cap

    ag_t1 = await _get_or_create_assignment_task(
        db_session, org_id, course.id, ch3.id, ch3_act3.id, agent_cap.id,
        {
            "title": "Task 1: Agent Dispatcher & Memory Management Implementation",
            "description": "Build an asynchronous agent router with structured JSON schema tool execution and context truncation.",
            "assignment_type": AssignmentTaskTypeEnum.CODE,
            "max_grade_value": 50,
            "contents": {"language": "python"},
        }
    )
    ag_t2 = await _get_or_create_assignment_task(
        db_session, org_id, course.id, ch3.id, ch3_act3.id, agent_cap.id,
        {
            "title": "Task 2: System Architecture Specification & Resiliency Validation",
            "description": "Provide architectural documentation for fault tolerance, retry budgets, and deadlock prevention.",
            "assignment_type": AssignmentTaskTypeEnum.SHORT_ANSWER,
            "max_grade_value": 50,
            "contents": {},
        }
    )

    if alex_id:
        await _get_or_create_task_submission(db_session, ag_t1, alex_id, {"grade": 49, "feedback": "Clean async task dispatcher with robust exponential backoff."})
        await _get_or_create_task_submission(db_session, ag_t2, alex_id, {"grade": 48, "feedback": "Thorough resiliency specification."})
        await _get_or_create_user_submission(db_session, agent_cap.id, alex_id, {"grade": 97, "overall_feedback": "Exceptional autonomous system engineering."})

    if maya_id:
        await _get_or_create_task_submission(db_session, ag_t1, maya_id, {"grade": 50, "feedback": "Flawless DAG execution engine with concurrent tool resolution."})
        await _get_or_create_task_submission(db_session, ag_t2, maya_id, {"grade": 49, "feedback": "Industrial-grade consensus and deadlock proof."})
        await _get_or_create_user_submission(db_session, agent_cap.id, maya_id, {"grade": 99, "overall_feedback": "World-class AI systems capstone project, Maya."})

    return {"course": course, "assignments": assignments_created}


# ============================================================================
# Main Entry Point Helper: build_full_demo_courses
# ============================================================================
async def build_full_demo_courses(
    db_session: AsyncSession,
    org_id: int,
    teacher_map: Optional[Dict[str, Any]] = None,
    student_map: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Constructs the complete 4-course curriculum with rich chapters, interactive activities,
    quiz blocks, SpeedGrader assignments, and student submissions.

    Parameters:
    -----------
    db_session : AsyncSession
        Active database session for transaction persistence.
    org_id : int
        ID of the organization to receive the curriculum.
    teacher_map : Optional[Dict[str, Any]]
        Map of teacher references (e.g. {'physics': user, 'math': user, ...}).
    student_map : Optional[Dict[str, Any]]
        Map of student references (e.g. {'alex': user, 'maya': user, 'leo': user, ...}).

    Returns:
    --------
    Dict[str, Any] containing:
    - 'courses': Dict of course slug/code -> Course object
    - 'assignments': Dict of assignment identifier -> Assignment object
    - 'total_courses': Total count of seeded courses
    - 'status': 'success'
    - Direct slug keys for backward-compatibility with seeder scripts
    """
    logger.info("Building full demo courses for Organization ID: %s", org_id)

    # Resolve student IDs for SpeedGrader submissions
    alex_id = _resolve_user_id("student.alex@csg.edu", student_map) or _resolve_user_id("alex", student_map)
    maya_id = _resolve_user_id("student.maya@csg.edu", student_map) or _resolve_user_id("maya", student_map)
    leo_id = _resolve_user_id("student.leo@csg.edu", student_map) or _resolve_user_id("leo", student_map)

    # 1. Build Course 1: AP Physics C (PHY-301)
    phy_res = await _build_physics_course(db_session, org_id, alex_id, maya_id)

    # 2. Build Course 2: Advanced Calculus & Linear Algebra (MATH-401)
    math_res = await _build_math_course(db_session, org_id, alex_id, maya_id)

    # 3. Build Course 3: World History & Global Perspectives (HIST-201)
    hist_res = await _build_history_course(db_session, org_id, alex_id, maya_id, leo_id)

    # 4. Build Course 4: Autonomous AI & Computational Science (CS-101 / CS-501)
    ai_res = await _build_ai_course(db_session, org_id, alex_id, maya_id)

    all_courses = {
        "ap-physics-c": phy_res["course"],
        "adv-calculus-math": math_res["course"],
        "world-history-perspectives": hist_res["course"],
        "autonomous-ai-cs": ai_res["course"],
        "ap-computer-science-ai": ai_res["course"],
    }

    all_assignments = {}
    all_assignments.update(phy_res.get("assignments", {}))
    all_assignments.update(math_res.get("assignments", {}))
    all_assignments.update(hist_res.get("assignments", {}))
    all_assignments.update(ai_res.get("assignments", {}))

    await db_session.flush()

    logger.info(
        "Successfully built 4 full-fledged courses with %d assignments for Org ID %d.",
        len(all_assignments),
        org_id,
    )

    response = {
        "status": "success",
        "courses": all_courses,
        "assignments": all_assignments,
        "total_courses": 4,
        "total_assignments": len(all_assignments),
        # Direct keys for backward compatibility
        "ap-physics-c": phy_res["course"],
        "adv-calculus-math": math_res["course"],
        "world-history-perspectives": hist_res["course"],
        "autonomous-ai-cs": ai_res["course"],
        "ap-computer-science-ai": ai_res["course"],
    }

    return response
