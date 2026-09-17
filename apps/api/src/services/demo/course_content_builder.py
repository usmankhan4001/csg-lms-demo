"""
CSG-EMS Course Content & SpeedGrader Demo Builder
==================================================
Builds rich, multi-chapter academic courses, activities, interactive blocks,
and SpeedGrader assignments with realistic student submissions and feedback.
"""

import datetime
from typing import Dict, Any, Optional
from uuid import uuid4
from sqlalchemy import select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.db.users import User
from src.db.courses.courses import Course
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
    AssignmentUserSubmission,
    AssignmentUserSubmissionStatus,
    AssignmentTaskSubmission,
)


def get_utc_now_str() -> str:
    return str(datetime.datetime.now(datetime.timezone.utc))


async def build_full_demo_courses(
    db_session: AsyncSession,
    org_id: int,
    teacher_map: Dict[str, User],
    student_map: Optional[Dict[str, User]] = None,
) -> Dict[str, Course]:
    """
    Creates 4 full-fledged courses with chapters, activities, blocks,
    and SpeedGrader assignments complete with rubric tasks and graded submissions.
    """
    now_str = get_utc_now_str()

    courses_spec = [
        {
            "slug": "ap-physics-c",
            "name": "AP Physics C: Mechanics & Electromagnetism",
            "code": "PHY-301",
            "desc": "Calculus-based university-level physics covering classical mechanics, rotational dynamics, harmonic oscillations, and Maxwell's electromagnetic theory.",
            "teacher_email": "teacher.physics@csg.edu",
            "chapters": [
                {
                    "title": "Unit 1: Kinematics & Newton's Laws of Motion",
                    "desc": "Differential and integral kinematics, friction, circular motion, and non-inertial reference frames.",
                    "activities": [
                        {
                            "name": "Lecture 1.1: Vector Calculus in Classical Kinematics",
                            "type": ActivityTypeEnum.TYPE_DOCUMENT,
                            "sub_type": ActivitySubTypeEnum.SUBTYPE_DYNAMIC_PAGE,
                            "content": {
                                "title": "Vector Derivatives & Curvilinear Trajectories",
                                "markdown": "# Kinematics via Vector Calculus\n\nPosition vector $\\vec{r}(t)$ can be differentiated with respect to time:\n\n$$\\vec{v}(t) = \\frac{d\\vec{r}}{dt}$$\n$$\\vec{a}(t) = \\frac{d\\vec{v}}{dt} = \\frac{d^2\\vec{r}}{dt^2}$$\n\nIn polar coordinates:\n$$\\vec{v} = \\dot{r}\\hat{r} + r\\dot{\\theta}\\hat{\\theta}$$",
                            },
                            "blocks": [
                                {
                                    "type": BlockTypeEnum.BLOCK_CUSTOM,
                                    "content": {
                                        "block_type": "theory_callout",
                                        "title": "Key Takeaway",
                                        "text": "Tangential and centripetal accelerations decompose the total acceleration vector orthogonally.",
                                    },
                                },
                            ],
                        },
                        {
                            "name": "Lab Practicum 1: Air Resistance & Terminal Velocity",
                            "type": ActivityTypeEnum.TYPE_ASSIGNMENT,
                            "sub_type": ActivitySubTypeEnum.SUBTYPE_ASSIGNMENT_ANY,
                            "assignment": {
                                "title": "Lab 1 SpeedGrader: Non-Linear Drag Modeling",
                                "desc": "Derive the analytical equation for quadratic drag $F_d = -\\frac{1}{2} C_d \\rho A v^2$ and evaluate experimental wind tunnel data.",
                                "grading_type": GradingTypeEnum.GPA_SCALE,
                                "due_date": "2025-10-15T23:59:59Z",
                                "tasks": [
                                    {
                                        "title": "Task 1: Differential Equation Formulation",
                                        "desc": "Set up and solve $m \\frac{dv}{dt} = mg - kv^2$ for $v(t)$ assuming $v(0)=0$.",
                                        "type": AssignmentTaskTypeEnum.SHORT_ANSWER,
                                        "hint": "Use separation of variables with hyperbolic tangent substitutions.",
                                        "contents": {"max_words": 500},
                                        "submissions": {
                                            "student.alex@csg.edu": {
                                                "answer": "Separating variables: \\int \\frac{dv}{g - (k/m)v^2} = \\int dt. Let v_t = \\sqrt{mg/k}. Integrating yields v(t) = v_t \\tanh(gt / v_t).",
                                                "grade": 95,
                                                "feedback": "Flawless derivation with correct asymptotic limit validation.",
                                            },
                                            "student.maya@csg.edu": {
                                                "answer": "Using \\frac{dv}{dt} = g(1 - (v/v_t)^2), we integrate to obtain v(t) = v_t \\tanh(\\frac{gt}{v_t}) where v_t = \\sqrt{\\frac{mg}{k}}.",
                                                "grade": 98,
                                                "feedback": "Exceptional mathematical clarity and boundary condition verification.",
                                            },
                                        },
                                    },
                                    {
                                        "title": "Task 2: Computational Python Curve Fit",
                                        "desc": "Upload Python code fitting experimental velocity data points to compute the drag coefficient $C_d$.",
                                        "type": AssignmentTaskTypeEnum.CODE,
                                        "hint": "Use scipy.optimize.curve_fit on the provided CSV array.",
                                        "contents": {"language": "python"},
                                        "submissions": {
                                            "student.alex@csg.edu": {
                                                "answer": "import numpy as np\nfrom scipy.optimize import curve_fit\n\ndef model(t, vt, tau):\n    return vt * np.tanh(t / tau)\n\npopt, pcov = curve_fit(model, t_data, v_data)\nprint(f'Fitted vt={popt[0]:.2f} m/s')",
                                                "grade": 94,
                                                "feedback": "Clean implementation; covariance matrix analysis was well documented.",
                                            },
                                            "student.maya@csg.edu": {
                                                "answer": "import numpy as np\nfrom scipy.optimize import curve_fit\nimport matplotlib.pyplot as plt\n\ndef v_drag(t, vt, k_m):\n    return vt * np.tanh(np.sqrt(9.81 * k_m) * t)\n\npopt, _ = curve_fit(v_drag, t_exp, v_exp)\nresiduals = v_exp - v_drag(t_exp, *popt)\nprint(f'Residual RMSE: {np.sqrt(np.mean(residuals**2)):.4f}')",
                                                "grade": 100,
                                                "feedback": "Superb work adding residual root-mean-square error diagnostics.",
                                            },
                                        },
                                    },
                                ],
                            },
                        },
                    ],
                },
                {
                    "title": "Unit 2: Work, Energy & Conservation Laws",
                    "desc": "Line integrals of force fields, conservative forces, potential energy landscapes, and Lagrangian mechanics preview.",
                    "activities": [
                        {
                            "name": "Lecture 2.1: Conservative Force Fields & Potential Gradients",
                            "type": ActivityTypeEnum.TYPE_DOCUMENT,
                            "sub_type": ActivitySubTypeEnum.SUBTYPE_DYNAMIC_PAGE,
                            "content": {
                                "title": "Conservative Fields and Gradient Operators",
                                "markdown": "# Conservative Vector Fields\n\nA force $\\vec{F}$ is conservative if and only if:\n\n$$\\nabla \\times \\vec{F} = 0$$\n$$\\vec{F} = -\\nabla U$$\n\nWork done along path $C$ is path-independent:\n$$W = \\int_A^B \\vec{F} \\cdot d\\vec{r} = -\\Delta U$$",
                            },
                        },
                    ],
                },
            ],
        },
        {
            "slug": "adv-calculus-math",
            "name": "Advanced Calculus & Linear Algebra",
            "code": "MATH-401",
            "desc": "Multivariable differential and integral calculus, Green's/Stokes' theorems, vector spaces, eigenvalues, and linear transformations.",
            "teacher_email": "teacher.math@csg.edu",
            "chapters": [
                {
                    "title": "Unit 1: Vector Spaces & Linear Transformations",
                    "desc": "Bases, dimension, nullity-rank theorem, inner product spaces, and Gram-Schmidt orthogonalization.",
                    "activities": [
                        {
                            "name": "Seminar 1: Orthogonal Subspaces & Projection Matrices",
                            "type": ActivityTypeEnum.TYPE_DOCUMENT,
                            "sub_type": ActivitySubTypeEnum.SUBTYPE_DYNAMIC_PAGE,
                            "content": {
                                "title": "Fundamental Theorem of Linear Algebra",
                                "markdown": "# The Four Fundamental Subspaces\n\nFor an $m \\times n$ matrix $A$:\n1. $\\text{Col}(A) \\perp \\text{Null}(A^T)$ in $\\mathbb{R}^m$\n2. $\\text{Row}(A) \\perp \\text{Null}(A)$ in $\\mathbb{R}^n$\n\nProjection matrix onto column space:\n$$P = A(A^T A)^{-1} A^T$$",
                            },
                        },
                        {
                            "name": "Problem Set 1: Singular Value Decomposition & Least Squares",
                            "type": ActivityTypeEnum.TYPE_ASSIGNMENT,
                            "sub_type": ActivitySubTypeEnum.SUBTYPE_ASSIGNMENT_ANY,
                            "assignment": {
                                "title": "Problem Set 1 SpeedGrader: SVD Derivations",
                                "desc": "Decompose matrix $A = U \\Sigma V^T$ and compute the Moore-Penrose pseudoinverse $A^+$.",
                                "grading_type": GradingTypeEnum.NUMERIC,
                                "due_date": "2025-10-20T23:59:59Z",
                                "tasks": [
                                    {
                                        "title": "Task 1: SVD Matrix Computation",
                                        "desc": "Compute the singular values $\\sigma_1, \\sigma_2$ for matrix $A = [[3, 2, 2], [2, 3, -2]]$.",
                                        "type": AssignmentTaskTypeEnum.SHORT_ANSWER,
                                        "hint": "Find the eigenvalues of $A A^T$.",
                                        "contents": {},
                                        "submissions": {
                                            "student.alex@csg.edu": {
                                                "answer": "AA^T = [[17, 8], [8, 17]]. Characteristic equation: (17-\\lambda)^2 - 64 = 0 => \\lambda_1 = 25, \\lambda_2 = 9. Therefore \\sigma_1 = 5, \\sigma_2 = 3.",
                                                "grade": 92,
                                                "feedback": "Correct eigenvalues and singular values derived cleanly.",
                                            },
                                            "student.maya@csg.edu": {
                                                "answer": "Computing AA^T gives eigenvalues 25 and 9. Singular values are sqrt(25)=5 and sqrt(9)=3. Right singular vectors orthonormalized via Gram-Schmidt.",
                                                "grade": 96,
                                                "feedback": "Rigorous and concise mathematical presentation.",
                                            },
                                        },
                                    },
                                ],
                            },
                        },
                    ],
                },
            ],
        },
        {
            "slug": "world-history-perspectives",
            "name": "World History & Global Perspectives",
            "code": "HIST-201",
            "desc": "Comparative analysis of civilization dynamics, trade networks, Enlightenment philosophies, and global economic revolutions.",
            "teacher_email": "teacher.humanities@csg.edu",
            "chapters": [
                {
                    "title": "Unit 1: The Enlightenment & Constitutional Revolutions",
                    "desc": "Social contract theories of Locke, Rousseau, and Montesquieu, and their manifestations in 18th-century constitutional frameworks.",
                    "activities": [
                        {
                            "name": "Primary Source Analysis: The Social Contract & Rights of Man",
                            "type": ActivityTypeEnum.TYPE_DOCUMENT,
                            "sub_type": ActivitySubTypeEnum.SUBTYPE_DYNAMIC_PAGE,
                            "content": {
                                "title": "Philosophical Foundations of Modern Democracy",
                                "markdown": "# The Enlightenment Dialectic\n\nComparing Hobbesian Leviathan sovereign authority against Locke's tabula rasa natural rights (life, liberty, estate) and Rousseau's general will.",
                            },
                        },
                        {
                            "name": "Historical Essay: Comparative Analysis of 1789 & 1776",
                            "type": ActivityTypeEnum.TYPE_ASSIGNMENT,
                            "sub_type": ActivitySubTypeEnum.SUBTYPE_ASSIGNMENT_ANY,
                            "assignment": {
                                "title": "Essay SpeedGrader: Revolutionary Historiography",
                                "desc": "Write a 1,200-word comparative essay on institutional origins of the American and French Revolutions.",
                                "grading_type": GradingTypeEnum.ALPHABET,
                                "due_date": "2025-11-05T23:59:59Z",
                                "tasks": [
                                    {
                                        "title": "Thesis Statement & Primary Source Synthesis",
                                        "desc": "Formulate a comparative thesis evaluating fiscal crisis vs ideological mobilization.",
                                        "type": AssignmentTaskTypeEnum.SHORT_ANSWER,
                                        "hint": "Cite Alexis de Tocqueville and Thomas Paine.",
                                        "contents": {"min_words": 150},
                                        "submissions": {
                                            "student.leo@csg.edu": {
                                                "answer": "While the American Revolution prioritized procedural self-governance and colonial autonomy against parliamentary overreach, the French Revolution sought fundamental structural leveling of the Ancien Regime's feudal estates through radical popular sovereignty.",
                                                "grade": 91,
                                                "feedback": "Insightful historiographical distinction with strong contextual framing.",
                                            },
                                        },
                                    },
                                ],
                            },
                        },
                    ],
                },
            ],
        },
        {
            "slug": "ap-computer-science-ai",
            "name": "AP Computer Science & Artificial Intelligence",
            "code": "CS-501",
            "desc": "Algorithmic thinking, object-oriented design in Python & Java, data structures, search algorithms, neural network foundations, and ethical AI deployment.",
            "teacher_email": "teacher.physics@csg.edu",
            "chapters": [
                {
                    "title": "Unit 1: Data Structures, Search & Graph Algorithms",
                    "desc": "Asymptotic time-space complexity, trees, graphs, Dijkstra's shortest path, and A* heuristic search.",
                    "activities": [
                        {
                            "name": "Module 1.1: Graph Traversal & Heuristic Pathfinding",
                            "type": ActivityTypeEnum.TYPE_DOCUMENT,
                            "sub_type": ActivitySubTypeEnum.SUBTYPE_DYNAMIC_PAGE,
                            "content": {
                                "title": "A* Search Algorithm Principles",
                                "markdown": "# A* Search & Admissible Heuristics\n\nEvaluation function:\n$$f(n) = g(n) + h(n)$$\n\nWhere $g(n)$ is actual cost from start to node $n$, and $h(n)$ is the estimated cost from $n$ to goal. If $h(n)$ is admissible ($h(n) \\le h^*(n)$), A* is guaranteed optimal.",
                            },
                        },
                        {
                            "name": "Capstone Project: Autonomous Maze Solver & Neural Perceptron",
                            "type": ActivityTypeEnum.TYPE_ASSIGNMENT,
                            "sub_type": ActivitySubTypeEnum.SUBTYPE_ASSIGNMENT_ANY,
                            "assignment": {
                                "title": "AI Project SpeedGrader: Perceptron Classifier",
                                "desc": "Implement a binary classification single-layer perceptron from scratch with gradient descent weight updates.",
                                "grading_type": GradingTypeEnum.GPA_SCALE,
                                "due_date": "2025-11-20T23:59:59Z",
                                "tasks": [
                                    {
                                        "title": "Task 1: Perceptron Convergence Implementation",
                                        "desc": "Submit Python code implementing $w_{i} \\leftarrow w_i + \\eta (y - \\hat{y}) x_i$.",
                                        "type": AssignmentTaskTypeEnum.CODE,
                                        "hint": "Include bias term and step activation function.",
                                        "contents": {"language": "python"},
                                        "submissions": {
                                            "student.alex@csg.edu": {
                                                "answer": "class Perceptron:\n    def __init__(self, lr=0.01, epochs=100):\n        self.lr = lr\n        self.epochs = epochs\n    def fit(self, X, y):\n        self.weights = np.zeros(1 + X.shape[1])\n        for _ in range(self.epochs):\n            for xi, target in zip(X, y):\n                update = self.lr * (target - self.predict(xi))\n                self.weights[1:] += update * xi\n                self.weights[0] += update\n    def predict(self, X):\n        return np.where(np.dot(X, self.weights[1:]) + self.weights[0] >= 0.0, 1, 0)",
                                                "grade": 96,
                                                "feedback": "Clean OOP implementation. Vectorized prediction handled correctly.",
                                            },
                                        },
                                    },
                                ],
                            },
                        },
                    ],
                },
            ],
        },
    ]

    seeded_courses: Dict[str, Course] = {}

    for c_spec in courses_spec:
        stmt = select(Course).where(Course.org_id == org_id, Course.name == c_spec["name"])
        course = (await db_session.execute(stmt)).scalars().first()
        if not course:
            course = Course(
                org_id=org_id,
                name=c_spec["name"],
                description=c_spec["desc"],
                about=c_spec["desc"],
                learnings=c_spec["desc"],
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

        seeded_courses[c_spec["slug"]] = course

        # Chapters & Activities
        for chap_idx, chap_spec in enumerate(c_spec.get("chapters", [])):
            chap_stmt = select(Chapter).where(
                Chapter.course_id == course.id,
                Chapter.name == chap_spec["title"],
            )
            chapter = (await db_session.execute(chap_stmt)).scalars().first()
            if not chapter:
                chapter = Chapter(
                    name=chap_spec["title"],
                    description=chap_spec["desc"],
                    lock_type=LockType.PUBLIC,
                    org_id=org_id,
                    course_id=course.id,
                    chapter_uuid=f"chp_{uuid4()}",
                    creation_date=now_str,
                    update_date=now_str,
                )
                db_session.add(chapter)
                await db_session.flush()
                await db_session.refresh(chapter)

                # CourseChapter link
                db_session.add(
                    CourseChapter(
                        order=chap_idx + 1,
                        course_id=course.id,
                        chapter_id=chapter.id,
                        org_id=org_id,
                        creation_date=now_str,
                        update_date=now_str,
                    )
                )
                await db_session.flush()

            # Activities
            for act_idx, act_spec in enumerate(chap_spec.get("activities", [])):
                act_stmt = select(Activity).where(
                    Activity.course_id == course.id,
                    Activity.name == act_spec["name"],
                )
                activity = (await db_session.execute(act_stmt)).scalars().first()
                if not activity:
                    activity = Activity(
                        name=act_spec["name"],
                        activity_type=act_spec["type"],
                        activity_sub_type=act_spec["sub_type"],
                        content=act_spec.get("content", {}),
                        details={},
                        published=True,
                        lock_type=ActivityLockType.PUBLIC,
                        org_id=org_id,
                        course_id=course.id,
                        activity_uuid=f"act_{uuid4()}",
                        creation_date=now_str,
                        update_date=now_str,
                    )
                    db_session.add(activity)
                    await db_session.flush()
                    await db_session.refresh(activity)

                    # ChapterActivity link
                    db_session.add(
                        ChapterActivity(
                            order=act_idx + 1,
                            chapter_id=chapter.id,
                            activity_id=activity.id,
                            course_id=course.id,
                            org_id=org_id,
                            creation_date=now_str,
                            update_date=now_str,
                        )
                    )
                    await db_session.flush()

                # Blocks
                for b_spec in act_spec.get("blocks", []):
                    b_stmt = select(Block).where(
                        Block.activity_id == activity.id,
                        Block.block_type == b_spec["type"],
                    )
                    if not (await db_session.execute(b_stmt)).scalars().first():
                        db_session.add(
                            Block(
                                block_type=b_spec["type"],
                                content=b_spec["content"],
                                org_id=org_id,
                                course_id=course.id,
                                chapter_id=chapter.id,
                                activity_id=activity.id,
                                block_uuid=f"blk_{uuid4()}",
                                creation_date=now_str,
                                update_date=now_str,
                            )
                        )

                # SpeedGrader Assignments
                assign_spec = act_spec.get("assignment")
                if assign_spec:
                    as_stmt = select(Assignment).where(
                        Assignment.course_id == course.id,
                        Assignment.activity_id == activity.id,
                    )
                    assignment = (await db_session.execute(as_stmt)).scalars().first()
                    if not assignment:
                        assignment = Assignment(
                            title=assign_spec["title"],
                            description=assign_spec["desc"],
                            due_date=assign_spec.get("due_date"),
                            published=True,
                            grading_type=assign_spec["grading_type"],
                            auto_grading=False,
                            show_correct_answers=True,
                            allow_retries=True,
                            max_retries=3,
                            pass_threshold_percentage=60.0,
                            solution_reveal=SolutionRevealEnum.AFTER_GRADING,
                            org_id=org_id,
                            course_id=course.id,
                            chapter_id=chapter.id,
                            activity_id=activity.id,
                            assignment_uuid=f"asg_{uuid4()}",
                            creation_date=now_str,
                            update_date=now_str,
                        )
                        db_session.add(assignment)
                        await db_session.flush()
                        await db_session.refresh(assignment)

                    # Tasks & Submissions
                    for task_spec in assign_spec.get("tasks", []):
                        t_stmt = select(AssignmentTask).where(
                            AssignmentTask.assignment_id == assignment.id,
                            AssignmentTask.title == task_spec["title"],
                        )
                        task = (await db_session.execute(t_stmt)).scalars().first()
                        if not task:
                            task = AssignmentTask(
                                title=task_spec["title"],
                                description=task_spec["desc"],
                                hint=task_spec.get("hint", ""),
                                assignment_type=task_spec["type"],
                                contents=task_spec.get("contents", {}),
                                max_grade_value=100,
                                assignment_id=assignment.id,
                                org_id=org_id,
                                course_id=course.id,
                                chapter_id=chapter.id,
                                activity_id=activity.id,
                                assignment_task_uuid=f"tsk_{uuid4()}",
                                creation_date=now_str,
                                update_date=now_str,
                            )
                            db_session.add(task)
                            await db_session.flush()
                            await db_session.refresh(task)

                        # Student submissions
                        if student_map:
                            for student_email, sub_data in task_spec.get("submissions", {}).items():
                                student = student_map.get(student_email)
                                if not student:
                                    continue

                                # Task submission
                                ts_stmt = select(AssignmentTaskSubmission).where(
                                    AssignmentTaskSubmission.user_id == student.id,
                                    AssignmentTaskSubmission.assignment_task_id == task.id,
                                )
                                if not (await db_session.execute(ts_stmt)).scalars().first():
                                    db_session.add(
                                        AssignmentTaskSubmission(
                                            assignment_task_submission_uuid=f"tsub_{uuid4()}",
                                            task_submission={"response": sub_data["answer"]},
                                            grade=sub_data["grade"],
                                            task_submission_grade_feedback=sub_data["feedback"],
                                            manually_graded=True,
                                            assignment_type=task_spec["type"],
                                            user_id=student.id,
                                            activity_id=activity.id,
                                            course_id=course.id,
                                            chapter_id=chapter.id,
                                            assignment_task_id=task.id,
                                            creation_date=now_str,
                                            update_date=now_str,
                                        )
                                    )

                                # User overall submission
                                us_stmt = select(AssignmentUserSubmission).where(
                                    AssignmentUserSubmission.user_id == student.id,
                                    AssignmentUserSubmission.assignment_id == assignment.id,
                                )
                                user_sub = (await db_session.execute(us_stmt)).scalars().first()
                                if not user_sub:
                                    db_session.add(
                                        AssignmentUserSubmission(
                                            submission_status=AssignmentUserSubmissionStatus.GRADED,
                                            grade=sub_data["grade"],
                                            overall_feedback=f"SpeedGrader: Graded by faculty with score {sub_data['grade']}/100.",
                                            attempt_number=1,
                                            user_id=student.id,
                                            assignment_id=assignment.id,
                                        )
                                    )

    await db_session.flush()
    return seeded_courses
