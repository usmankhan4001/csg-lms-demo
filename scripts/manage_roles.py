#!/usr/bin/env python3
"""
SMS Role Management CLI Utility for Learnhouse / CSG LMS.

Usage:
    python scripts/manage_roles.py list --org-id 1
    python scripts/manage_roles.py assign --email teacher@csg.edu --role TEACHER --org-id 1 [--campus-id 1]
    python scripts/manage_roles.py assign --user-id 42 --role STUDENT --org-id 1
    python scripts/manage_roles.py revoke --email user@csg.edu --role PARENT --org-id 1
    python scripts/manage_roles.py inspect --email student@csg.edu
    python scripts/manage_roles.py link-guardian --guardian-email parent@csg.edu --student-email student@csg.edu --relation Mother
"""

import argparse
import asyncio
import os
import sys
from typing import List, Optional

# Add apps/api to path so imports work
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "apps", "api"))

from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.core.keycloak_auth import (
    SUPER_ADMIN,
    SCHOOL_ADMIN,
    TEACHER,
    STUDENT,
    PARENT,
    STAFF,
    PSYCHOLOGIST,
)
from src.db.sms_identity import SchoolRole, SMSUserRole, StudentGuardian
from src.db.users import User


VALID_ROLES = [
    SUPER_ADMIN,
    SCHOOL_ADMIN,
    TEACHER,
    STUDENT,
    PARENT,
    STAFF,
    PSYCHOLOGIST,
]


def get_db_url() -> str:
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        postgres_user = os.environ.get("POSTGRES_USER", "postgres")
        postgres_pwd = os.environ.get("POSTGRES_PASSWORD", "postgres")
        postgres_host = os.environ.get("POSTGRES_HOST", "localhost")
        postgres_port = os.environ.get("POSTGRES_PORT", "5432")
        postgres_db = os.environ.get("POSTGRES_DB", "learnhouse")
        db_url = f"postgresql+asyncpg://{postgres_user}:{postgres_pwd}@{postgres_host}:{postgres_port}/{postgres_db}"
    elif db_url.startswith("postgresql://"):
        db_url = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return db_url


async def find_user_by_email_or_id(session: AsyncSession, email: Optional[str] = None, user_id: Optional[int] = None) -> Optional[User]:
    if user_id:
        return await session.get(User, user_id)
    if email:
        result = await session.exec(select(User).where(User.email == email.strip().lower()))
        return result.first()
    return None


async def list_roles(org_id: Optional[int] = None, role_filter: Optional[str] = None):
    engine = create_async_engine(get_db_url(), echo=False)
    async with AsyncSession(engine) as session:
        query = select(SMSUserRole)
        if org_id is not None:
            query = query.where(SMSUserRole.org_id == org_id)
        if role_filter:
            query = query.where(SMSUserRole.role == role_filter)

        results = (await session.exec(query)).all()
        print(f"\n=== SMS User Roles ({len(results)} assignments found) ===")
        print(f"{'ID':<6} {'User ID':<10} {'Email':<30} {'Role':<15} {'Org ID':<8} {'Campus ID':<10} {'Status':<8}")
        print("-" * 90)
        for r in results:
            u = await session.get(User, r.user_id)
            email = u.email if u else "UNKNOWN"
            status_str = "ACTIVE" if r.is_active else "INACTIVE"
            print(f"{r.id:<6} {r.user_id:<10} {email:<30} {r.role:<15} {r.org_id or '-':<8} {r.campus_id or '-':<10} {status_str:<8}")
    await engine.dispose()


async def assign_role(email: Optional[str], user_id: Optional[int], role: str, org_id: Optional[int], campus_id: Optional[int]):
    if role not in VALID_ROLES:
        print(f"Error: Invalid role '{role}'. Allowed: {', '.join(VALID_ROLES)}")
        sys.exit(1)

    engine = create_async_engine(get_db_url(), echo=False)
    async with AsyncSession(engine) as session:
        user = await find_user_by_email_or_id(session, email=email, user_id=user_id)
        if not user:
            print(f"Error: User not found for email='{email}' / user_id='{user_id}'")
            await engine.dispose()
            sys.exit(1)

        # Check existing
        query = select(SMSUserRole).where(
            SMSUserRole.user_id == user.id,
            SMSUserRole.role == role,
            SMSUserRole.org_id == org_id,
        )
        existing = (await session.exec(query)).first()
        if existing:
            existing.campus_id = campus_id
            existing.is_active = True
            await session.commit()
            print(f"Updated existing role: User '{user.email}' (ID: {user.id}) -> Role: {role} (Org: {org_id}, Campus: {campus_id})")
        else:
            new_role = SMSUserRole(
                user_id=user.id,
                org_id=org_id,
                campus_id=campus_id,
                role=role,
                is_active=True,
            )
            session.add(new_role)
            await session.commit()
            print(f"Successfully assigned: User '{user.email}' (ID: {user.id}) -> Role: {role} (Org: {org_id}, Campus: {campus_id})")

    await engine.dispose()


async def revoke_role(email: Optional[str], user_id: Optional[int], role: str, org_id: Optional[int]):
    engine = create_async_engine(get_db_url(), echo=False)
    async with AsyncSession(engine) as session:
        user = await find_user_by_email_or_id(session, email=email, user_id=user_id)
        if not user:
            print(f"Error: User not found for email='{email}' / user_id='{user_id}'")
            await engine.dispose()
            sys.exit(1)

        query = select(SMSUserRole).where(
            SMSUserRole.user_id == user.id,
            SMSUserRole.role == role,
        )
        if org_id is not None:
            query = query.where(SMSUserRole.org_id == org_id)

        existing = (await session.exec(query)).first()
        if not existing:
            print(f"Warning: No matching role '{role}' found for User '{user.email}'")
        else:
            await session.delete(existing)
            await session.commit()
            print(f"Successfully revoked: Role '{role}' from User '{user.email}' (ID: {user.id})")

    await engine.dispose()


async def inspect_user(email: Optional[str], user_id: Optional[int]):
    engine = create_async_engine(get_db_url(), echo=False)
    async with AsyncSession(engine) as session:
        user = await find_user_by_email_or_id(session, email=email, user_id=user_id)
        if not user:
            print(f"Error: User not found for email='{email}' / user_id='{user_id}'")
            await engine.dispose()
            sys.exit(1)

        print(f"\n=== User Identity Details ===")
        print(f"ID:         {user.id}")
        print(f"Email:      {user.email}")
        print(f"First Name: {user.first_name}")
        print(f"Last Name:  {user.last_name}")
        print(f"Created At: {user.created_at}")

        roles = (await session.exec(select(SMSUserRole).where(SMSUserRole.user_id == user.id))).all()
        print(f"\nAssigned SMS Roles ({len(roles)}):")
        for r in roles:
            print(f"  - Role: {r.role:<15} Org: {r.org_id or '-':<5} Campus: {r.campus_id or '-':<5} Active: {r.is_active}")

        guardianships = (await session.exec(select(StudentGuardian).where(StudentGuardian.guardian_user_id == user.id))).all()
        if guardianships:
            print(f"\nLinked Children (as Guardian):")
            for g in guardianships:
                student = await session.get(User, g.student_id)
                s_email = student.email if student else "UNKNOWN"
                print(f"  - Student ID: {g.student_id} ({s_email}) | Relation: {g.relation_type or 'Guardian'} | Primary: {g.is_primary}")

        wards = (await session.exec(select(StudentGuardian).where(StudentGuardian.student_id == user.id))).all()
        if wards:
            print(f"\nLinked Guardians (for Student):")
            for w in wards:
                guardian = await session.get(User, w.guardian_user_id)
                g_email = guardian.email if guardian else "UNKNOWN"
                print(f"  - Guardian ID: {w.guardian_user_id} ({g_email}) | Relation: {w.relation_type or 'Guardian'}")

    await engine.dispose()


async def link_guardian(guardian_email: str, student_email: str, relation: str, is_primary: bool = True):
    engine = create_async_engine(get_db_url(), echo=False)
    async with AsyncSession(engine) as session:
        guardian = await find_user_by_email_or_id(session, email=guardian_email)
        student = await find_user_by_email_or_id(session, email=student_email)
        if not guardian or not student:
            print(f"Error: Guardian ({guardian_email}) or Student ({student_email}) not found")
            await engine.dispose()
            sys.exit(1)

        link = StudentGuardian(
            guardian_user_id=guardian.id,
            student_id=student.id,
            relation_type=relation,
            is_primary=is_primary,
        )
        session.add(link)
        await session.commit()
        print(f"Linked Guardian '{guardian.email}' to Student '{student.email}' as {relation} (Primary: {is_primary})")

    await engine.dispose()


def main():
    parser = argparse.ArgumentParser(description="SMS Role Management CLI for CSG LMS / Learnhouse")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # list
    list_p = subparsers.add_parser("list", help="List assigned SMS roles")
    list_p.add_argument("--org-id", type=int, help="Filter by Organization ID")
    list_p.add_argument("--role", type=str, help="Filter by role name")

    # assign
    assign_p = subparsers.add_parser("assign", help="Assign a role to a user")
    assign_p.add_argument("--email", type=str, help="User email")
    assign_p.add_argument("--user-id", type=int, help="User ID")
    assign_p.add_argument("--role", type=str, required=True, choices=VALID_ROLES, help="Role name")
    assign_p.add_argument("--org-id", type=int, help="Organization ID")
    assign_p.add_argument("--campus-id", type=int, help="Campus ID")

    # revoke
    revoke_p = subparsers.add_parser("revoke", help="Revoke a role from a user")
    revoke_p.add_argument("--email", type=str, help="User email")
    revoke_p.add_argument("--user-id", type=int, help="User ID")
    revoke_p.add_argument("--role", type=str, required=True, choices=VALID_ROLES, help="Role name")
    revoke_p.add_argument("--org-id", type=int, help="Organization ID")

    # inspect
    inspect_p = subparsers.add_parser("inspect", help="Inspect a user's roles and guardian links")
    inspect_p.add_argument("--email", type=str, help="User email")
    inspect_p.add_argument("--user-id", type=int, help="User ID")

    # link-guardian
    link_p = subparsers.add_parser("link-guardian", help="Link a guardian to a student")
    link_p.add_argument("--guardian-email", type=str, required=True, help="Guardian email")
    link_p.add_argument("--student-email", type=str, required=True, help="Student email")
    link_p.add_argument("--relation", type=str, default="Guardian", help="Relation type (e.g. Father, Mother, Guardian)")
    link_p.add_argument("--secondary", action="store_true", help="Set as secondary guardian instead of primary")

    args = parser.parse_args()

    if args.command == "list":
        asyncio.run(list_roles(org_id=args.org_id, role_filter=args.role))
    elif args.command == "assign":
        if not args.email and not args.user_id:
            print("Error: Must specify either --email or --user-id")
            sys.exit(1)
        asyncio.run(assign_role(email=args.email, user_id=args.user_id, role=args.role, org_id=args.org_id, campus_id=args.campus_id))
    elif args.command == "revoke":
        if not args.email and not args.user_id:
            print("Error: Must specify either --email or --user-id")
            sys.exit(1)
        asyncio.run(revoke_role(email=args.email, user_id=args.user_id, role=args.role, org_id=args.org_id))
    elif args.command == "inspect":
        if not args.email and not args.user_id:
            print("Error: Must specify either --email or --user-id")
            sys.exit(1)
        asyncio.run(inspect_user(email=args.email, user_id=args.user_id))
    elif args.command == "link-guardian":
        asyncio.run(link_guardian(guardian_email=args.guardian_email, student_email=args.student_email, relation=args.relation, is_primary=not args.secondary))


if __name__ == "__main__":
    main()
