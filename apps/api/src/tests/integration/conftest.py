"""
Integration Test Harness Configuration.
=========================================
Provides real PostgreSQL test database lifecycle with graceful fallback to
in-memory SQLite (with JSONB conversion) when PostgreSQL is not configured or reachable.
Also provides HTTP client, AsyncSession, principals, and academic environment fixtures.
"""

import os
import sys
import logging
from datetime import datetime
from typing import AsyncGenerator
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import JSON, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession
from httpx import AsyncClient, ASGITransport

# Ensure repository root and apps/api are on sys.path
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

os.environ["TESTING"] = "true"
os.environ["LEARNHOUSE_DISABLE_EE"] = "1"
os.environ["LEARNHOUSE_DEMO_ENABLED"] = "0"
os.environ["LEARNHOUSE_AUTH_JWT_SECRET_KEY"] = "integration-test-secret-key-32chars-min!"

from src.core.keycloak_auth import KeycloakUserPrincipal
from src.db.organizations import Organization
from src.db.roles import Role, RoleTypeEnum
from src.db.users import User
from src.db.sms_campus import (
    Campus,
    AcademicYear,
    AcademicTerm,
    ClassSection,
    StudentEnrollment,
)
from src.db.sms_gradebook import GradingScale, AssessmentPlan
from src.db.sms_fees import FeeStructure
from app import app
from src.services.database.database import get_session

logger = logging.getLogger(__name__)


def get_target_db_url() -> str:
    """Detects PostgreSQL test database URL or falls back to in-memory SQLite."""
    pg_url = (
        os.getenv("TEST_DATABASE_URL")
        or os.getenv("POSTGRES_TEST_URL")
        or os.getenv("DATABASE_URL")
    )
    if pg_url and ("postgres" in pg_url or "postgresql" in pg_url):
        # Normalize driver for asyncpg if not specified
        if pg_url.startswith("postgres://"):
            pg_url = pg_url.replace("postgres://", "postgresql+asyncpg://", 1)
        elif pg_url.startswith("postgresql://") and not pg_url.startswith("postgresql+asyncpg://"):
            pg_url = pg_url.replace("postgresql://", "postgresql+asyncpg://", 1)
        return pg_url
    return "sqlite+aiosqlite://"


@pytest.fixture(scope="session")
async def engine():
    """Session-level Async Engine with PostgreSQL lifecycle or SQLite fallback."""
    db_url = get_target_db_url()
    is_postgres = "postgres" in db_url

    if is_postgres:
        try:
            eng = create_async_engine(db_url, echo=False)
            async with eng.begin() as conn:
                # Test connection
                await conn.execute(text("SELECT 1"))
                await conn.run_sync(SQLModel.metadata.create_all)
            logger.info("Integration tests running against real PostgreSQL: %s", db_url)
            yield eng
            async with eng.begin() as conn:
                await conn.run_sync(SQLModel.metadata.drop_all)
            await eng.dispose()
            return
        except Exception as e:
            logger.warning(
                "PostgreSQL connection failed (%s). Falling back to in-memory SQLite.", e
            )

    # SQLite fallback
    for table in SQLModel.metadata.tables.values():
        for col in table.columns:
            if isinstance(col.type, JSONB):
                col.type = JSON()

    eng = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        echo=False,
    )
    async with eng.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    logger.info("Integration tests running against in-memory SQLite engine.")
    yield eng
    await eng.dispose()


@pytest.fixture
async def db(engine) -> AsyncGenerator[AsyncSession, None]:
    """Yields an isolated AsyncSession bound to the active engine."""
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session


@pytest.fixture
async def client(db: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """FastAPI Test Client with overridden database session dependency."""
    async def override_get_session():
        yield db

    app.dependency_overrides[get_session] = override_get_session

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as c:
        yield c

    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Principals
# ---------------------------------------------------------------------------

@pytest.fixture
def admin_principal() -> KeycloakUserPrincipal:
    return KeycloakUserPrincipal(
        sub="admin-sub-1",
        email="admin@school.local",
        org_id=1,
        campus_id=1,
        realm_roles=["SUPER_ADMIN", "SCHOOL_ADMIN"],
        roles={"SUPER_ADMIN", "SCHOOL_ADMIN"},
        raw_claims={"lh_user_id": 1},
    )


@pytest.fixture
def teacher_principal() -> KeycloakUserPrincipal:
    return KeycloakUserPrincipal(
        sub="teacher-sub-2",
        email="teacher@school.local",
        org_id=1,
        campus_id=1,
        realm_roles=["TEACHER", "STAFF"],
        roles={"TEACHER", "STAFF"},
        raw_claims={"lh_user_id": 2},
    )


@pytest.fixture
def student_principal() -> KeycloakUserPrincipal:
    return KeycloakUserPrincipal(
        sub="student-sub-3",
        email="student@school.local",
        org_id=1,
        campus_id=1,
        realm_roles=["STUDENT"],
        roles={"STUDENT"},
        raw_claims={"lh_user_id": 3},
    )


@pytest.fixture
def parent_principal() -> KeycloakUserPrincipal:
    return KeycloakUserPrincipal(
        sub="parent-sub-4",
        email="parent@school.local",
        org_id=1,
        campus_id=1,
        realm_roles=["PARENT"],
        roles={"PARENT"},
        raw_claims={"lh_user_id": 4},
    )


# ---------------------------------------------------------------------------
# Base Academic Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
async def setup_org(db: AsyncSession) -> Organization:
    org = Organization(
        id=1,
        name="Apex International Academy",
        slug="apex-academy",
        email="info@apex.edu",
        org_uuid="org_apex_1",
        creation_date=str(datetime.now()),
        update_date=str(datetime.now()),
    )
    db.add(org)
    await db.commit()
    await db.refresh(org)
    return org


@pytest.fixture
async def setup_campus(db: AsyncSession, setup_org: Organization) -> Campus:
    campus = Campus(
        id=1,
        org_id=setup_org.id,
        name="Main Academic Campus",
        code="CAMPUS-MAIN",
        timezone="Asia/Karachi",
        is_active=True,
    )
    db.add(campus)
    await db.commit()
    await db.refresh(campus)
    return campus


@pytest.fixture
async def setup_academic_year(db: AsyncSession, setup_campus: Campus) -> AcademicYear:
    ay = AcademicYear(
        id=1,
        campus_id=setup_campus.id,
        name="2025-2026",
        start_date="2025-09-01",
        end_date="2026-06-30",
        is_active=True,
    )
    db.add(ay)
    await db.commit()
    await db.refresh(ay)
    return ay


@pytest.fixture
async def setup_academic_term(db: AsyncSession, setup_academic_year: AcademicYear) -> AcademicTerm:
    term = AcademicTerm(
        id=1,
        academic_year_id=setup_academic_year.id,
        name="Term 1 (Fall)",
        start_date="2025-09-01",
        end_date="2025-12-20",
        is_active=True,
    )
    db.add(term)
    await db.commit()
    await db.refresh(term)
    return term
