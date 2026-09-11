"""
Concept Knowledge Graph & Student 360 Mastery Matrix Service (M44, M45)
========================================================================
Implements graph dependency traversal, Bayesian/EMA mastery score updates,
gap analysis, prerequisite path resolution, and adaptive learning recommendations.
"""

from datetime import datetime, timezone
import logging
from typing import Any, Dict, List, Optional, Set, Tuple
from sqlmodel import select, col
from sqlmodel.ext.asyncio.session import AsyncSession

from src.db.ai_knowledge_graph import (
    ConceptNode,
    ConceptPrerequisite,
    StudentConceptMastery,
    MasteryRadarItem,
    StudentMasteryRadarResponse,
    LearningPathConceptItem,
    StudentLearningPathResponse,
)

logger = logging.getLogger(__name__)

MASTERY_THRESHOLD = 0.75
PASSING_PREREQUISITE_THRESHOLD = 0.70
GAP_THRESHOLD = 0.60


def _normalize_score(raw_score: float) -> float:
    """Normalizes percentage (0-100) or decimal (0.0-1.0) into [0.0, 1.0]."""
    if raw_score > 1.0:
        return max(0.0, min(1.0, raw_score / 100.0))
    return max(0.0, min(1.0, raw_score))


async def evaluate_mastery_update(
    student_id: str,
    concept_id: int,
    quiz_score: float,
    difficulty: Optional[int] = None,
    db_session: Optional[AsyncSession] = None,
) -> StudentConceptMastery:
    """
    Evaluates assessment performance and updates student mastery using Bayesian/EMA updating.
    
    Mastery calculation incorporates:
    - Normalized assessment score [0.0, 1.0]
    - Difficulty factor (1=easiest, 5=hardest)
    - Prior mastery state and assessment attempt history
    - Asymptotic confidence level growth
    """
    norm_score = _normalize_score(quiz_score)
    now_iso = datetime.now(timezone.utc).isoformat()

    diff_val = 1
    if difficulty is not None:
        diff_val = max(1, min(5, difficulty))
    elif db_session is not None:
        concept = await db_session.get(ConceptNode, concept_id)
        if concept:
            diff_val = concept.difficulty_level

    # Difficulty scaling factor: higher difficulty provides greater mastery reward on high scores
    difficulty_factor = 0.85 + (diff_val * 0.05)
    target_mastery = max(0.0, min(1.0, norm_score * difficulty_factor))

    existing: Optional[StudentConceptMastery] = None
    if db_session is not None:
        stmt = select(StudentConceptMastery).where(
            col(StudentConceptMastery.student_id) == student_id,
            col(StudentConceptMastery.concept_id) == concept_id,
        )
        res = await db_session.execute(stmt)
        existing = res.scalars().first()

    if existing is not None:
        # Exponential moving average with adaptive learning rate
        attempts = existing.attempts_count + 1
        alpha = max(0.25, 0.6 / (1.0 + (attempts * 0.1)))
        
        updated_score = round((1.0 - alpha) * existing.mastery_score + alpha * target_mastery, 4)
        updated_score = max(0.0, min(1.0, updated_score))

        # Confidence increases asymptotically toward 1.0
        updated_confidence = round(
            min(1.0, existing.confidence_level + 0.15 * (1.0 - existing.confidence_level)),
            4
        )

        existing.mastery_score = updated_score
        existing.confidence_level = updated_confidence
        existing.attempts_count = attempts
        existing.last_evaluated_at = now_iso

        if db_session is not None:
            db_session.add(existing)
            await db_session.commit()
            await db_session.refresh(existing)
        return existing

    # Initial mastery state creation
    initial_mastery = round(min(1.0, max(0.0, target_mastery)), 4)
    initial_confidence = round(0.5 + (0.1 if norm_score >= 0.7 else 0.0), 4)

    record = StudentConceptMastery(
        student_id=student_id,
        concept_id=concept_id,
        mastery_score=initial_mastery,
        confidence_level=initial_confidence,
        attempts_count=1,
        last_evaluated_at=now_iso,
    )

    if db_session is not None:
        db_session.add(record)
        await db_session.commit()
        await db_session.refresh(record)

    return record


async def get_concept_dependency_path(
    target_concept_id: int,
    db_session: AsyncSession,
) -> List[ConceptNode]:
    """
    Traverses the prerequisite graph (DAG) starting from target_concept_id
    and returns a topologically sorted list of ConceptNodes needed to understand the target.
    Foundational concepts appear first.
    """
    target_node = await db_session.get(ConceptNode, target_concept_id)
    if not target_node:
        return []

    # Fetch all prerequisites across the knowledge graph
    all_prereqs_res = await db_session.execute(select(ConceptPrerequisite))
    prereq_edges = all_prereqs_res.scalars().all()

    # Build adjacency list: concept_id -> list of prerequisite_concept_ids
    prereq_map: Dict[int, List[int]] = {}
    for edge in prereq_edges:
        prereq_map.setdefault(edge.concept_id, []).append(edge.prerequisite_concept_id)

    # Collect all ancestor prerequisite concept IDs (DFS / reachable set)
    needed_ids: Set[int] = set()
    stack = [target_concept_id]
    visited: Set[int] = set()

    while stack:
        curr = stack.pop()
        if curr in visited:
            continue
        visited.add(curr)
        needed_ids.add(curr)
        for prereq_id in prereq_map.get(curr, []):
            if prereq_id not in visited:
                stack.append(prereq_id)

    # Fetch all needed concept node models
    stmt = select(ConceptNode).where(col(ConceptNode.id).in_(list(needed_ids)))
    nodes_res = await db_session.execute(stmt)
    node_dict = {n.id: n for n in nodes_res.scalars().all() if n.id is not None}

    # Perform Topological Sort on the subgraph
    # In-degree for topological sort: prerequisite -> dependent
    in_degree: Dict[int, int] = {cid: 0 for cid in needed_ids}
    sub_adj: Dict[int, List[int]] = {cid: [] for cid in needed_ids}

    for cid in needed_ids:
        for prereq_id in prereq_map.get(cid, []):
            if prereq_id in needed_ids:
                sub_adj[prereq_id].append(cid)
                in_degree[cid] += 1

    queue = [cid for cid, deg in in_degree.items() if deg == 0]
    sorted_ids: List[int] = []

    while queue:
        # Sort queue by difficulty or id for deterministic ordering
        queue.sort(key=lambda x: (node_dict.get(x).difficulty_level if node_dict.get(x) else 1, x))
        curr = queue.pop(0)
        sorted_ids.append(curr)

        for neighbor in sub_adj.get(curr, []):
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)

    # If any nodes were involved in cycles, append remaining
    for cid in needed_ids:
        if cid not in sorted_ids:
            sorted_ids.append(cid)

    return [node_dict[cid] for cid in sorted_ids if cid in node_dict]


async def get_recommended_next_concepts(
    student_id: str,
    subject: Optional[str] = None,
    db_session: Optional[AsyncSession] = None,
    limit: int = 5,
) -> List[Dict[str, Any]]:
    """
    Finds concept nodes where all prerequisites have been mastered (mastery >= 0.70),
    but the concept itself is not yet mastered (mastery < 0.75).
    """
    if db_session is None:
        return []

    # Fetch concepts
    concept_stmt = select(ConceptNode)
    if subject:
        concept_stmt = concept_stmt.where(col(ConceptNode.subject) == subject)
    concepts_res = await db_session.execute(concept_stmt)
    concepts = concepts_res.scalars().all()

    if not concepts:
        return []

    concept_ids = [c.id for c in concepts if c.id is not None]

    # Fetch student masteries
    mastery_stmt = select(StudentConceptMastery).where(
        col(StudentConceptMastery.student_id) == student_id,
        col(StudentConceptMastery.concept_id).in_(concept_ids),
    )
    mastery_res = await db_session.execute(mastery_stmt)
    mastery_map: Dict[int, StudentConceptMastery] = {
        m.concept_id: m for m in mastery_res.scalars().all()
    }

    # Fetch prerequisite edges
    prereq_stmt = select(ConceptPrerequisite).where(
        col(ConceptPrerequisite.concept_id).in_(concept_ids)
    )
    prereq_res = await db_session.execute(prereq_stmt)
    prereqs = prereq_res.scalars().all()

    prereq_map: Dict[int, List[int]] = {}
    for edge in prereqs:
        prereq_map.setdefault(edge.concept_id, []).append(edge.prerequisite_concept_id)

    recommendations = []

    for concept in concepts:
        cid = concept.id
        if cid is None:
            continue

        mastery_record = mastery_map.get(cid)
        current_score = mastery_record.mastery_score if mastery_record else 0.0
        confidence = mastery_record.confidence_level if mastery_record else 0.5

        # Skip if already mastered
        if current_score >= MASTERY_THRESHOLD:
            continue

        # Check prerequisite mastery
        concept_prereqs = prereq_map.get(cid, [])
        prereqs_met = True
        prereq_scores = []

        for p_id in concept_prereqs:
            p_mastery = mastery_map.get(p_id)
            p_score = p_mastery.mastery_score if p_mastery else 0.0
            prereq_scores.append(p_score)
            if p_score < PASSING_PREREQUISITE_THRESHOLD:
                prereqs_met = False

        avg_prereq_score = (sum(prereq_scores) / len(prereq_scores)) if prereq_scores else 1.0

        if prereqs_met:
            status_str = "IN_PROGRESS" if current_score > 0.0 else "READY_TO_LEARN"
            reason = (
                f"All {len(concept_prereqs)} prerequisite(s) satisfied. Ready for topic mastery."
                if concept_prereqs else
                "Foundational concept with no prerequisite barriers."
            )
            if current_score > 0.0:
                reason = f"In-progress concept ({int(current_score * 100)}% mastery). Reinforce to achieve mastery."

            # Priority score: Higher for ready concepts with good prerequisite base, sorted by difficulty
            priority = (1.0 - current_score) * 0.6 + (avg_prereq_score * 0.4) - (concept.difficulty_level * 0.05)

            recommendations.append({
                "concept": concept,
                "current_mastery": current_score,
                "confidence_level": confidence,
                "status": status_str,
                "prerequisites_met": True,
                "readiness_score": round(avg_prereq_score, 2),
                "priority": priority,
                "recommendation_reason": reason,
            })

    # Sort recommendations by highest priority
    recommendations.sort(key=lambda x: x["priority"], reverse=True)
    return recommendations[:limit]


async def get_student_mastery_radar(
    student_id: str,
    db_session: AsyncSession,
) -> StudentMasteryRadarResponse:
    """
    Computes aggregated subject-level mastery radar metrics for Student 360 profile.
    """
    # Fetch all concepts
    all_concepts_res = await db_session.execute(select(ConceptNode))
    concepts = all_concepts_res.scalars().all()

    # Fetch all student concept masteries
    mastery_stmt = select(StudentConceptMastery).where(
        col(StudentConceptMastery.student_id) == student_id
    )
    mastery_res = await db_session.execute(mastery_stmt)
    mastery_map: Dict[int, StudentConceptMastery] = {
        m.concept_id: m for m in mastery_res.scalars().all()
    }

    # Group by subject
    subject_map: Dict[str, List[ConceptNode]] = {}
    for c in concepts:
        subject_map.setdefault(c.subject, []).append(c)

    radar_items: List[MasteryRadarItem] = []
    total_mastered = 0
    total_scores = []

    for subject, subj_concepts in subject_map.items():
        total_in_subj = len(subj_concepts)
        subj_scores = []
        mastered_count = 0
        in_progress_count = 0

        for c in subj_concepts:
            m = mastery_map.get(c.id) if c.id else None
            score = m.mastery_score if m else 0.0
            subj_scores.append(score)
            total_scores.append(score)

            if score >= MASTERY_THRESHOLD:
                mastered_count += 1
                total_mastered += 1
            elif score > 0.1:
                in_progress_count += 1

        avg_score = round(sum(subj_scores) / total_in_subj, 4) if total_in_subj > 0 else 0.0

        if avg_score >= 0.85:
            tier = "Mastery"
        elif avg_score >= 0.70:
            tier = "Proficient"
        elif avg_score >= 0.40:
            tier = "Developing"
        else:
            tier = "Novice"

        radar_items.append(
            MasteryRadarItem(
                subject=subject,
                average_mastery=avg_score,
                total_concepts=total_in_subj,
                mastered_concepts=mastered_count,
                in_progress_concepts=in_progress_count,
                proficiency_tier=tier,
            )
        )

    overall_avg = round(sum(total_scores) / len(total_scores), 4) if total_scores else 0.0

    return StudentMasteryRadarResponse(
        student_id=student_id,
        radar_data=radar_items,
        overall_mastery_average=overall_avg,
        total_mastered_concepts=total_mastered,
        total_tracked_concepts=len(concepts),
    )


async def get_student_learning_path(
    student_id: str,
    db_session: AsyncSession,
    subject: Optional[str] = None,
) -> StudentLearningPathResponse:
    """
    Generates a personalized dynamic learning path identifying knowledge gaps,
    ready-to-learn concepts, and mastered concepts.
    """
    # Fetch concepts
    concept_stmt = select(ConceptNode)
    if subject:
        concept_stmt = concept_stmt.where(col(ConceptNode.subject) == subject)
    concepts_res = await db_session.execute(concept_stmt)
    concepts = concepts_res.scalars().all()
    concept_ids = [c.id for c in concepts if c.id is not None]

    # Fetch student masteries
    mastery_stmt = select(StudentConceptMastery).where(
        col(StudentConceptMastery.student_id) == student_id,
        col(StudentConceptMastery.concept_id).in_(concept_ids),
    )
    mastery_res = await db_session.execute(mastery_stmt)
    mastery_map: Dict[int, StudentConceptMastery] = {
        m.concept_id: m for m in mastery_res.scalars().all()
    }

    # Fetch prerequisites
    prereq_stmt = select(ConceptPrerequisite).where(
        col(ConceptPrerequisite.concept_id).in_(concept_ids)
    )
    prereq_res = await db_session.execute(prereq_stmt)
    prereqs = prereq_res.scalars().all()

    prereq_map: Dict[int, List[int]] = {}
    for edge in prereqs:
        prereq_map.setdefault(edge.concept_id, []).append(edge.prerequisite_concept_id)

    gap_concepts: List[LearningPathConceptItem] = []
    recommended_next: List[LearningPathConceptItem] = []
    mastered: List[LearningPathConceptItem] = []

    for concept in concepts:
        cid = concept.id
        if cid is None:
            continue

        mastery_record = mastery_map.get(cid)
        current_score = mastery_record.mastery_score if mastery_record else 0.0
        confidence = mastery_record.confidence_level if mastery_record else 0.5

        # Check prerequisites
        concept_prereqs = prereq_map.get(cid, [])
        prereqs_met = True
        for p_id in concept_prereqs:
            p_m = mastery_map.get(p_id)
            if not p_m or p_m.mastery_score < PASSING_PREREQUISITE_THRESHOLD:
                prereqs_met = False
                break

        item = LearningPathConceptItem(
            concept_id=cid,
            subject=concept.subject,
            topic_code=concept.topic_code,
            title=concept.title,
            difficulty_level=concept.difficulty_level,
            current_mastery=current_score,
            confidence_level=confidence,
            status="BLOCKED" if not prereqs_met else ("MASTERED" if current_score >= MASTERY_THRESHOLD else ("IN_PROGRESS" if current_score > 0.0 else "READY_TO_LEARN")),
            prerequisites_met=prereqs_met,
            recommendation_reason="",
        )

        if current_score >= MASTERY_THRESHOLD:
            item.recommendation_reason = "Concept mastered. Available for peer teaching and advanced application."
            mastered.append(item)
        elif current_score > 0.0 and current_score < GAP_THRESHOLD:
            item.recommendation_reason = f"Mastery gap identified ({int(current_score * 100)}%). Remediation recommended."
            gap_concepts.append(item)
        elif prereqs_met:
            item.recommendation_reason = "Prerequisites satisfied. Optimal next concept for progressive learning."
            recommended_next.append(item)

    # Sort gaps by lowest mastery (highest urgency)
    gap_concepts.sort(key=lambda x: x.current_mastery)
    # Sort next recommendations by difficulty ascending
    recommended_next.sort(key=lambda x: (x.difficulty_level, -x.current_mastery))

    # Calculate estimated study time (e.g. 20 mins per gap, 30 mins per new concept)
    estimated_mins = (len(gap_concepts) * 20) + (len(recommended_next) * 30)

    summary = (
        f"Student has mastered {len(mastered)} concepts. "
        f"{len(gap_concepts)} knowledge gap(s) require review and {len(recommended_next)} next concept(s) are unlocked."
    )

    return StudentLearningPathResponse(
        student_id=student_id,
        subject=subject,
        readiness_summary=summary,
        gap_concepts=gap_concepts,
        recommended_next_concepts=recommended_next,
        mastered_concepts=mastered,
        estimated_study_time_mins=estimated_mins,
    )
