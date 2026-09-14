"""
Curriculum Knowledge Graph & Mastery Map Router (M44).

Builds a Directed Acyclic Graph (DAG) of curriculum prerequisites and maps
real-time student concept mastery levels (0-100%) to recommend optimal learning paths.
"""

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlmodel.ext.asyncio.session import AsyncSession

from src.core.events.database import get_db_session
from src.core.keycloak_auth import (
    KeycloakUserPrincipal,
    get_current_user_principal,
)
from src.security.school_ownership import require_own_student_or_privileged

router = APIRouter()


class ConceptNode(BaseModel):
    id: str
    title: str
    subject: str
    grade_level: str
    bloom_taxonomy_level: str
    prerequisites: List[str]
    estimated_hours: float


class StudentMasteryNode(BaseModel):
    concept_id: str
    title: str
    mastery_percentage: float
    status: str  # locked | in_progress | mastered
    last_assessed: Optional[str] = None


class KnowledgeGraphResponse(BaseModel):
    subject: str
    grade_level: str
    total_nodes: int
    nodes: List[ConceptNode]
    edges: List[Dict[str, str]]


# The hardcoded CURRICULUM_KNOWLEDGE_BASE that used to sit here was removed
# with the endpoints that served it. Nothing outside this file referenced it.


@router.get(
    "/graph",
    summary="Get Curriculum Concept Knowledge Graph (M44) — NOT IMPLEMENTED",
    description=(
        "Not implemented. This endpoint returned a hardcoded Maths/Physics "
        "curriculum dict rather than the school's own concepts, so it "
        "described a curriculum no school here teaches. The real concept "
        "catalogue is GET /api/v1/ai/concepts, backed by the ConceptNode "
        "table."
    ),
    responses={501: {"description": "Superseded by GET /api/v1/ai/concepts"}},
)
async def get_curriculum_graph(
    subject: str = Query("math_high_school", description="Curriculum domain key"),
    principal: KeycloakUserPrincipal = Depends(get_current_user_principal),
) -> Dict[str, Any]:
    # Previously returned CURRICULUM_KNOWLEDGE_BASE: a hardcoded six-node
    # Maths graph and a three-node Physics one, identical for every school,
    # every campus and every grade. A real concept graph already exists in the
    # ConceptNode / ConceptPrerequisite tables and is served by
    # GET /api/v1/ai/concepts and /concepts/{id}/dependency-path.
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail=(
            "Curriculum graph is not available from this endpoint. It "
            "previously returned a fixed demo curriculum that no school "
            "here teaches. Use GET /api/v1/ai/concepts for the real "
            "concept catalogue."
        ),
    )


@router.get(
    "/students/{student_id}/mastery",
    summary="Get Student Concept Mastery Map (M44) — NOT IMPLEMENTED",
    description=(
        "Not implemented. This endpoint returned the SAME hardcoded mastery "
        "scores for every student, including students who do not exist. Use "
        "GET /api/v1/ai/student/{student_id}/mastery-radar, which computes "
        "from the StudentConceptMastery table."
    ),
    responses={501: {"description": "Superseded by /api/v1/ai/student/{id}/mastery-radar"}},
)
async def get_student_mastery_map(
    student_id: int,
    subject: str = Query("math_high_school"),
    principal: KeycloakUserPrincipal = Depends(require_own_student_or_privileged()),
    session: AsyncSession = Depends(get_db_session),
) -> Dict[str, Any]:
    # THIS ENDPOINT FABRICATED. It held `scores = [95.0, 88.0, 72.0, 84.0,
    # 45.0, 10.0]` under the comment "Dynamic simulation for demo" and never
    # touched `session` at all. Proven live before removal:
    #
    #   student 1   -> 65.7%  2/6 mastered
    #   student 37  -> 65.7%  2/6
    #   student 999 -> 65.7%  2/6   <- a student who does not exist
    #
    # A teacher would have been shown "95% mastered" for a child never
    # assessed. It refuses rather than returning zeros, because a fabricated
    # zero is still a fabrication: "no data" and "scored nothing" demand
    # opposite responses from a teacher.
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail=(
            "Concept mastery is not available from this endpoint. It "
            "previously returned identical simulated scores for every "
            "student. Use GET /api/v1/ai/student/{student_id}/mastery-radar, "
            "which is computed from recorded mastery data."
        ),
    )
