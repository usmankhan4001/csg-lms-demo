"""
CLI Runner for CSG-EMS Comprehensive Demo Data Seeding
======================================================
Usage:
    python -m scripts.seed_sms_demo
    or
    apps/api/.venv/Scripts/python apps/api/scripts/seed_sms_demo.py
"""

import asyncio
import os
import sys

# Ensure root apps/api is in sys.path
api_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if api_root not in sys.path:
    sys.path.insert(0, api_root)

from sqlmodel import SQLModel
from src.core.events.database import engine, get_db_session, import_all_models
from src.services.demo.sms_demo_seeder import seed_sms_demo_data


async def main():
    print("Initializing Database metadata and tables...")
    import_all_models()
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)

    print("Executing CSG-EMS Comprehensive Demo Data Seeder...")
    async for db_session in get_db_session():
        result = await seed_sms_demo_data(db_session)
        print("Demo seeding completed successfully!")
        print(f"Result: {result}")
        break


if __name__ == "__main__":
    asyncio.run(main())
