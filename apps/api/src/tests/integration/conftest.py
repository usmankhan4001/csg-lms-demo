"""
Integration Test Harness Configuration.
=========================================
Provides an in-memory SQLite database (with JSONB-to-JSON conversion), HTTP
client, AsyncSession, principals, and academic environment fixtures.

The database is deliberately *not* configurable: this harness used to resolve a
URL from TEST_DATABASE_URL / POSTGRES_TEST_URL / DATABASE_URL and, because
`from app import app` runs load_dotenv(), it would happily connect to whatever
PostgreSQL a developer had configured and then call
SQLModel.metadata.drop_all() on it at session end. Every test now gets a fresh
in-memory SQLite database instead, matching the rest of the suite.
"""

import os
import sys
from datetime import datetime
from typing import AsyncGenerator
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import JSON
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
from src.core.events.database import get_db_session


TEST_DB_URL = "sqlite+aiosqlite://"


def _assert_safe_test_database(url: str) -> None:
    """Refuse to run against anything but a throwaway in-memory SQLite database.

    Guards against a regression reintroducing an environment-derived URL: a
    real (possibly shared) database must never be reached, let alone dropped.
    """
    if not url.startswith("sqlite+aiosqlite://"):
        raise RuntimeError(
            "Integration tests may only run against in-memory SQLite, got "
            f"{url!r}. Refusing to touch a real database."
        )
    # Everything after the scheme must be empty (memory) or ':memory:'. A file
    # path would persist state across runs and survive a crash.
    path = url[len("sqlite+aiosqlite://"):].split("?", 1)[0]
    if path not in ("", ":memory:"):
        raise RuntimeError(
            "Integration tests may only run against in-memory SQLite, got a "
            f"file-backed database {url!r}. Refusing to touch it."
        )


@pytest.fixture
async def engine():
    """Per-test in-memory async SQLite engine with JSONB-to-JSON remapping.

    Function-scoped on purpose: each test gets a brand new database, so tests
    in this directory cannot leak rows into one another and stay order-
    independent. Teardown only disposes the engine -- there is no drop_all,
    because the schema lives and dies with the in-memory connection.
    """
    _assert_safe_test_database(TEST_DB_URL)

    for table in SQLModel.metadata.tables.values():
        for col in table.columns:
            if isinstance(col.type, JSONB):
                col.type = JSON()

    eng = create_async_engine(
        TEST_DB_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        echo=False,
    )
    async with eng.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
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

    app.dependency_overrides[get_db_session] = override_get_session

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
