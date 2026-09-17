"""
CLI Runner for CSG-EMS Comprehensive Demo Data Seeding
======================================================
Usage:
    python -m scripts.seed_sms_demo [--clean] [--org-slug CSG-ACADEMY]
    or
    apps/api/.venv/Scripts/python apps/api/scripts/seed_sms_demo.py --clean
"""

import argparse
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
    parser = argparse.ArgumentParser(description="CSG-EMS Comprehensive Demo Data Seeder CLI")
    parser.add_argument(
        "--clean",
        "--clear",
        action="store_true",
        dest="clean",
        help="Cleanly wipe previous demo records before seeding",
    )
    parser.add_argument(
        "--org-slug",
        type=str,
        default=None,
        help="Target organization slug (defaults to 'csg-academy')",
    )
    args = parser.parse_args()

    print("Initializing Database metadata and tables...")
    import_all_models()
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)

    print(f"Executing CSG-EMS Comprehensive Demo Data Seeder (clean_previous={args.clean}, org_slug={args.org_slug})...")
    async for db_session in get_db_session():
        result = await seed_sms_demo_data(
            db_session=db_session,
            org_slug=args.org_slug,
            clear_previous=args.clean,
        )
        print("Demo seeding completed successfully!")
        print(f"Result: {result}")
        break


if __name__ == "__main__":
    asyncio.run(main())
