"""
Integration tests for CSG-EMS SMS Demo API Router
==================================================
Tests /api/v1/sms/demo/seed and /api/v1/sms/demo/clean-and-reseed
"""

from unittest.mock import patch, AsyncMock, MagicMock
import pytest
from httpx import AsyncClient, ASGITransport
from sqlmodel.ext.asyncio.session import AsyncSession

from app import app
from src.core.events.database import get_db_session
from src.routers.sms_demo import seed_demo_endpoint, clean_and_reseed_demo_endpoint, SeedDemoRequest, CleanAndReseedDemoRequest


MOCK_SEED_RESULT = {
    "status": "success",
    "organization": "CSG Academy Global",
    "org_id": 1,
    "org_slug": "csg-academy",
    "campus": "Main Campus",
    "users_seeded": 13,
    "users_created": 13,
    "students": 4,
    "teachers": 4,
    "staff": 2,
    "sections": 4,
    "courses": 4,
    "chapters": 12,
    "activities": 24,
    "submissions": 12,
    "attendance_records": 120,
    "gradebook_entries": 16,
    "cbt_exams": 2,
    "crm_leads": 10,
    "journal_entries": 5,
    "payslips": 8,
    "cognia_evidence_items": 10,
    "ami_index": 3.88,
}


@pytest.mark.asyncio
async def test_seed_sms_demo_endpoint_direct():
    mock_db = MagicMock(spec=AsyncSession)
    with patch("src.routers.sms_demo.seed_sms_demo_data", new_callable=AsyncMock, return_value=MOCK_SEED_RESULT):
        req = SeedDemoRequest(org_slug="csg-academy", clear_previous=False)
        res = await seed_demo_endpoint(payload=req, db_session=mock_db)
        assert res["status"] == "success"
        assert res["sections"] == 4
        assert res["courses"] == 4
        assert res["ami_index"] == 3.88


@pytest.mark.asyncio
async def test_clean_and_reseed_sms_demo_endpoint_direct():
    mock_db = MagicMock(spec=AsyncSession)
    with patch("src.routers.sms_demo.seed_sms_demo_data", new_callable=AsyncMock, return_value=MOCK_SEED_RESULT):
        req = CleanAndReseedDemoRequest(org_slug="csg-academy")
        res = await clean_and_reseed_demo_endpoint(payload=req, db_session=mock_db)
        assert res["status"] == "success"
        assert res["sections"] == 4
        assert res["courses"] == 4
        assert res["ami_index"] == 3.88


@pytest.mark.asyncio
async def test_sms_demo_api_http_client():
    mock_db = MagicMock(spec=AsyncSession)
    app.dependency_overrides[get_db_session] = lambda: mock_db

    with patch("src.routers.sms_demo.seed_sms_demo_data", new_callable=AsyncMock, return_value=MOCK_SEED_RESULT):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Seed
            seed_resp = await client.post("/api/v1/sms/demo/seed", json={"org_slug": "csg-academy", "clear_previous": False})
            assert seed_resp.status_code == 200
            data = seed_resp.json()
            assert data["status"] == "success"
            assert data["sections"] == 4
            assert data["courses"] == 4

            # Clean and Reseed
            reseed_resp = await client.post("/api/v1/sms/demo/clean-and-reseed", json={"org_slug": "csg-academy"})
            assert reseed_resp.status_code == 200
            data2 = reseed_resp.json()
            assert data2["status"] == "success"
            assert data2["sections"] == 4
            assert data2["courses"] == 4

    app.dependency_overrides.clear()
