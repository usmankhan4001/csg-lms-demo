"""
SM-2 Spaced Repetition & Knowledge Graph DAG Learning Engine (Phase 4 / M44, M45)
================================================================================
Implements:
1. SuperMemo SM-2 memory retention curve and interval calculations:
   - EF' = EF + (0.1 - (5 - q) * (0.08 + (5 - q) * 0.02)), EF' >= 1.3
   - Repetition interval scaling: I(1) = 1, I(2) = 6, I(n) = I(n-1) * EF
   - Retention probability estimation based on elapsed review intervals.
2. Knowledge Graph Directed Acyclic Graph (DAG) validation & topological traversal.
3. Recursive prerequisite validation & root-cause remedial pathfinder.
4. Concept gap heatmap computation across student cohorts.
"""

import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Set, Tuple


# ---------------------------------------------------------------------------
# 1. SuperMemo SM-2 Spaced Repetition Engine
# ---------------------------------------------------------------------------

INITIAL_EASE_FACTOR = 2.5
MINIMUM_EASE_FACTOR = 1.3


@dataclass
class SM2ReviewState:
    concept_id: int
    student_id: str
    repetitions: int = 0
    interval_days: int = 1
    ease_factor: float = INITIAL_EASE_FACTOR
    last_reviewed_at: Optional[datetime] = None
    next_review_at: Optional[datetime] = None
    total_reviews: int = 0
    consecutive_correct: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "concept_id": self.concept_id,
            "student_id": self.student_id,
            "repetitions": self.repetitions,
            "interval_days": self.interval_days,
            "ease_factor": round(self.ease_factor, 4),
            "last_reviewed_at": self.last_reviewed_at.isoformat() if self.last_reviewed_at else None,
            "next_review_at": self.next_review_at.isoformat() if self.next_review_at else None,
            "total_reviews": self.total_reviews,
            "consecutive_correct": self.consecutive_correct,
        }


def calculate_sm2_interval(
    current_state: SM2ReviewState,
    quality: int,  # Quality score q in [0, 5]
    review_time: Optional[datetime] = None,
) -> SM2ReviewState:
    """
    Computes updated SuperMemo SM-2 parameters after a review response.
    
    Parameters:
    - quality (q): Integer 0 to 5.
      5: Perfect response
      4: Correct response after hesitation
      3: Correct response with serious difficulty
      2: Incorrect response; where the correct one seemed easy to recall
      1: Incorrect response; the correct one remembered
      0: Complete blackout
    """
    q = max(0, min(5, int(quality)))
    now = review_time or datetime.now(timezone.utc)

    ef = current_state.ease_factor
    # SM-2 EF calculation formula:
    # EF' = EF + (0.1 - (5 - q) * (0.08 + (5 - q) * 0.02))
    delta_ef = 0.1 - (5 - q) * (0.08 + (5 - q) * 0.02)
    new_ef = max(MINIMUM_EASE_FACTOR, ef + delta_ef)

    if q < 3:
        # Failed recall: reset repetitions count and set interval to 1 day
        new_reps = 0
        new_interval = 1
        new_consecutive = 0
    else:
        # Successful recall: advance repetition counter
        new_reps = current_state.repetitions + 1
        new_consecutive = current_state.consecutive_correct + 1
        if new_reps == 1:
            new_interval = 1
        elif new_reps == 2:
            new_interval = 6
        else:
            new_interval = max(1, int(round(current_state.interval_days * new_ef)))

    next_review = now + timedelta(days=new_interval)

    return SM2ReviewState(
        concept_id=current_state.concept_id,
        student_id=current_state.student_id,
        repetitions=new_reps,
        interval_days=new_interval,
        ease_factor=round(new_ef, 4),
        last_reviewed_at=now,
        next_review_at=next_review,
        total_reviews=current_state.total_reviews + 1,
        consecutive_correct=new_consecutive,
    )


def estimate_retention_probability(
    state: SM2ReviewState,
    as_of: Optional[datetime] = None,
) -> float:
    """
    Estimates current memory retention probability R(t) based on the Ebbinghaus forgetting curve:
    R(t) = exp(-t / S), where S is the stability approximated by the SM-2 interval.
    """
    if not state.last_reviewed_at:
        return 0.5  # Neutral prior for unreviewed concept

    ref_time = as_of or datetime.now(timezone.utc)
    elapsed_days = max(0.0, (ref_time - state.last_reviewed_at).total_seconds() / 86400.0)

    # Stability S in days (proportional to interval and ease factor)
    stability = max(1.0, float(state.interval_days) * (state.ease_factor / INITIAL_EASE_FACTOR))
    retention = math.exp(-elapsed_days / stability)
    return max(0.0, min(1.0, round(retention, 4)))


# ---------------------------------------------------------------------------
# 2. Knowledge Graph DAG & Remedial Pathfinder
# ---------------------------------------------------------------------------

@dataclass
class DAGNode:
    id: int
    title: str
    subject: str
    topic_code: str
    difficulty_level: int = 1
    bloom_level: str = "REMEMBER"


@dataclass
class DAGEdge:
    concept_id: int              # Target/dependent concept
    prerequisite_id: int         # Required foundational concept
    weight: float = 1.0


class KnowledgeGraphDAG:
    """
    Directed Acyclic Graph (DAG) manager for academic curriculum prerequisites,
    prerequisite verification, topological ordering, and remedial pathfinding.
    """

    def __init__(self):
        self.nodes: Dict[int, DAGNode] = {}
        self.edges: List[DAGEdge] = []
        self._adj: Dict[int, List[int]] = {}       # prereq_id -> list of dependent_ids
        self._rev_adj: Dict[int, List[int]] = {}   # dependent_id -> list of prereq_ids

    def add_node(self, node: DAGNode) -> None:
        self.nodes[node.id] = node
        self._adj.setdefault(node.id, [])
        self._rev_adj.setdefault(node.id, [])

    def add_edge(self, concept_id: int, prerequisite_id: int, weight: float = 1.0) -> None:
        edge = DAGEdge(concept_id=concept_id, prerequisite_id=prerequisite_id, weight=weight)
        self.edges.append(edge)
        self._adj.setdefault(prerequisite_id, []).append(concept_id)
        self._rev_adj.setdefault(concept_id, []).append(prerequisite_id)

    def validate_acyclic(self) -> Tuple[bool, Optional[List[int]]]:
        """
        Validates that the knowledge graph is a valid DAG with no circular dependencies.
        Returns (is_acyclic, cycle_nodes).
        """
        visited: Dict[int, int] = {}  # 0 = unvisited, 1 = visiting (in stack), 2 = visited
        cycle_path: List[int] = []

        def dfs(node_id: int, stack: List[int]) -> bool:
            visited[node_id] = 1
            stack.append(node_id)

            for neighbor in self._adj.get(node_id, []):
                state = visited.get(neighbor, 0)
                if state == 1:
                    # Cycle detected
                    idx = stack.index(neighbor)
                    cycle_path.extend(stack[idx:] + [neighbor])
                    return False
                if state == 0:
                    if not dfs(neighbor, stack):
                        return False

            visited[node_id] = 2
            stack.pop()
            return True

        for nid in self.nodes:
            if visited.get(nid, 0) == 0:
                if not dfs(nid, []):
                    return False, cycle_path

        return True, None

    def topological_sort(self, subset_ids: Optional[Set[int]] = None) -> List[DAGNode]:
        """
        Returns a topologically sorted list of DAG nodes (foundational concepts first).
        """
        active_ids = set(self.nodes.keys()) if subset_ids is None else subset_ids
        in_degree = {nid: 0 for nid in active_ids}

        for nid in active_ids:
            for prereq in self._rev_adj.get(nid, []):
                if prereq in active_ids:
                    in_degree[nid] += 1

        queue = [nid for nid, deg in in_degree.items() if deg == 0]
        sorted_nodes: List[DAGNode] = []

        while queue:
            # Deterministic sorting by difficulty then id
            queue.sort(key=lambda x: (self.nodes[x].difficulty_level, x))
            curr = queue.pop(0)
            sorted_nodes.append(self.nodes[curr])

            for dep in self._adj.get(curr, []):
                if dep in active_ids:
                    in_degree[dep] -= 1
                    if in_degree[dep] == 0:
                        queue.append(dep)

        return sorted_nodes

    def check_prerequisites_met(
        self,
        target_concept_id: int,
        student_mastery_map: Dict[int, float],
        passing_threshold: float = 0.70,
    ) -> Tuple[bool, List[Dict[str, Any]]]:
        """
        Validates if all direct prerequisites for a target concept have been mastered.
        Returns (all_met, prerequisite_details).
        """
        prereqs = self._rev_adj.get(target_concept_id, [])
        details = []
        all_met = True

        for p_id in prereqs:
            node = self.nodes.get(p_id)
            score = student_mastery_map.get(p_id, 0.0)
            is_satisfied = score >= passing_threshold
            if not is_satisfied:
                all_met = False

            details.append({
                "concept_id": p_id,
                "title": node.title if node else f"Concept {p_id}",
                "current_mastery": round(score, 2),
                "passing_threshold": passing_threshold,
                "satisfied": is_satisfied,
            })

        return all_met, details

    def find_remedial_path(
        self,
        struggling_concept_id: int,
        student_mastery_map: Dict[int, float],
        passing_threshold: float = 0.70,
    ) -> List[Dict[str, Any]]:
        """
        Root-cause remedial pathfinder:
        Recursively traverses prerequisite ancestors of a struggling concept to identify
        all unmastered foundational gaps, returning a topologically ordered remediation roadmap.
        """
        if struggling_concept_id not in self.nodes:
            return []

        needed_ancestors: Set[int] = set()
        stack = [struggling_concept_id]
        visited: Set[int] = set()

        while stack:
            curr = stack.pop()
            if curr in visited:
                continue
            visited.add(curr)

            for prereq_id in self._rev_adj.get(curr, []):
                needed_ancestors.add(prereq_id)
                if prereq_id not in visited:
                    stack.append(prereq_id)

        # Include struggling concept itself
        needed_ancestors.add(struggling_concept_id)

        # Topological sort of the needed subgraph
        sorted_nodes = self.topological_sort(needed_ancestors)

        remedial_steps = []
        for node in sorted_nodes:
            score = student_mastery_map.get(node.id, 0.0)
            is_gap = score < passing_threshold
            remedial_steps.append({
                "concept_id": node.id,
                "title": node.title,
                "topic_code": node.topic_code,
                "difficulty_level": node.difficulty_level,
                "bloom_level": node.bloom_level,
                "current_mastery": round(score, 2),
                "is_knowledge_gap": is_gap,
                "step_type": "FOUNDATIONAL_REMEDIATION" if node.id != struggling_concept_id else "TARGET_CONCEPT",
                "recommended_action": (
                    f"Review foundational concept '{node.title}' (Mastery: {int(score*100)}%)"
                    if is_gap else
                    f"Verified prerequisite '{node.title}'"
                ),
            })

        return remedial_steps

    def generate_cohort_gap_heatmap(
        self,
        cohort_mastery: Dict[str, Dict[int, float]],  # student_id -> (concept_id -> score)
    ) -> Dict[str, Any]:
        """
        Calculates a concept gap heatmap matrix for an entire class or cohort.
        Identifies high-frequency concept bottlenecks across all students.
        """
        concept_stats: Dict[int, Dict[str, Any]] = {}

        for cid, node in self.nodes.items():
            scores = []
            for s_id, s_map in cohort_mastery.items():
                if cid in s_map:
                    scores.append(s_map[cid])

            count = len(scores)
            avg_score = round(sum(scores) / count, 2) if count > 0 else 0.0
            struggling_count = sum(1 for s in scores if s < 0.60)
            gap_rate = round(struggling_count / count, 2) if count > 0 else 0.0

            concept_stats[cid] = {
                "concept_id": cid,
                "title": node.title,
                "topic_code": node.topic_code,
                "subject": node.subject,
                "difficulty_level": node.difficulty_level,
                "students_assessed": count,
                "average_mastery": avg_score,
                "struggling_students": struggling_count,
                "gap_rate": gap_rate,
                "is_critical_bottleneck": gap_rate >= 0.35,
            }

        sorted_bottlenecks = sorted(
            concept_stats.values(),
            key=lambda x: x["gap_rate"],
            reverse=True,
        )

        return {
            "total_concepts": len(self.nodes),
            "total_students": len(cohort_mastery),
            "concept_matrix": concept_stats,
            "ranked_bottlenecks": sorted_bottlenecks,
        }
