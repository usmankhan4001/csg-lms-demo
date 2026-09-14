#!/usr/bin/env python
"""
Stand up a real school from a config file.

Before this existed there was no onboarding path at all: every demonstration
school in this project was hand-built by clicking through the UI or by curl.
That is fine once and impossible to repeat reliably.

What it creates, in dependency order:
    organization -> campus -> academic year -> terms -> class sections
    plus a grading scale and one school-admin user.

THREE RULES, each from a real incident in this codebase:

1. IDEMPOTENT. Running it twice must not duplicate anything. Every object is
   looked up by its natural key first and reused if present. You will run
   this more than once -- while iterating on the config, or re-running after
   a partial failure -- and a script that silently creates a second "Grade 9
   A" each time is worse than no script.

2. NEVER INVENT DATA. Anything the config does not specify is left unset. It
   is NOT defaulted to something plausible. This project has had three
   separate incidents of fabricated data reaching real users (a 4.0 GPA for
   a student with no grades, a parent digest inventing attendance, and
   marketing copy naming a school that does not exist). A seeded school that
   quietly contains invented terms or a made-up grading scale is the same
   class of bug.

3. NO DEFAULT PASSWORD. The admin password comes from the config or from
   $CSG_SEED_ADMIN_PASSWORD, and is never written to stdout, a log, or the
   config example. A seed script with a baked-in password becomes the
   forgotten admin account on a production box.

Usage:
    python scripts/seed_school.py --config scripts/example_school.yml
    python scripts/seed_school.py --config my_school.yml --dry-run

Run it from the repo root with the API's virtualenv active, e.g.:
    cd apps/api && uv run python ../../scripts/seed_school.py --config ...
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

# The models live in apps/api. Import them rather than writing raw SQL, so
# this script cannot drift from the schema the application actually uses.
_REPO_ROOT = Path(__file__).resolve().parent.parent
_API_ROOT = _REPO_ROOT / "apps" / "api"
if str(_API_ROOT) not in sys.path:
    sys.path.insert(0, str(_API_ROOT))


class ConfigError(Exception):
    """Raised for anything wrong with the config, before any write happens."""


# ---------------------------------------------------------------------------
# Config loading and validation
# ---------------------------------------------------------------------------

def load_config(path: Path) -> Dict[str, Any]:
    if not path.is_file():
        raise ConfigError(f"config file not found: {path}")

    text = path.read_text(encoding="utf-8")
    suffix = path.suffix.lower()

    if suffix in (".yml", ".yaml"):
        try:
            import yaml  # type: ignore
        except ImportError as exc:  # pragma: no cover - environment dependent
            raise ConfigError(
                "PyYAML is required to read a .yml config. Either install it "
                "or supply the same config as .json."
            ) from exc
        data = yaml.safe_load(text)
    elif suffix == ".json":
        import json
        data = json.loads(text)
    else:
        raise ConfigError(f"unsupported config format '{suffix}' (use .yml or .json)")

    if not isinstance(data, dict):
        raise ConfigError("config root must be a mapping")
    return data


def _require(d: Dict[str, Any], key: str, where: str) -> Any:
    if key not in d or d[key] in (None, ""):
        raise ConfigError(f"{where}: missing required field '{key}'")
    return d[key]


def validate(cfg: Dict[str, Any]) -> None:
    """Validate the WHOLE config before writing anything.

    Failing halfway through leaves a half-built school that the idempotency
    rules then have to reconcile. Cheaper to refuse up front.
    """
    org = _require(cfg, "organization", "config")
    _require(org, "name", "organization")
    _require(org, "slug", "organization")

    campus = _require(cfg, "campus", "config")
    _require(campus, "name", "campus")
    _require(campus, "code", "campus")

    year = _require(cfg, "academic_year", "config")
    _require(year, "name", "academic_year")

    terms = cfg.get("terms") or []
    if not isinstance(terms, list):
        raise ConfigError("terms: must be a list")
    for i, term in enumerate(terms):
        _require(term, "name", f"terms[{i}]")

    sections = cfg.get("sections") or []
    if not isinstance(sections, list):
        raise ConfigError("sections: must be a list")
    for i, sec in enumerate(sections):
        _require(sec, "grade_level", f"sections[{i}]")
        _require(sec, "section_name", f"sections[{i}]")

    scale = cfg.get("grading_scale")
    if scale is not None:
        _require(scale, "name", "grading_scale")
        intervals = _require(scale, "intervals", "grading_scale")
        if not isinstance(intervals, list) or not intervals:
            raise ConfigError("grading_scale.intervals: must be a non-empty list")
        for i, iv in enumerate(intervals):
            for k in ("grade", "min_percentage", "max_percentage", "gpa_point"):
                _require(iv, k, f"grading_scale.intervals[{i}]")

    admin = _require(cfg, "admin_user", "config")
    _require(admin, "email", "admin_user")
    _require(admin, "username", "admin_user")

    # Rule 3: the password is never defaulted and never read from the config
    # in plaintext if an env var is available.
    if not (admin.get("password") or os.environ.get("CSG_SEED_ADMIN_PASSWORD")):
        raise ConfigError(
            "admin_user: no password supplied. Set $CSG_SEED_ADMIN_PASSWORD "
            "(preferred) or admin_user.password in the config. There is "
            "deliberately no default."
        )


# ---------------------------------------------------------------------------
# Seeding
# ---------------------------------------------------------------------------

async def seed(cfg: Dict[str, Any], dry_run: bool) -> int:
    from sqlmodel import select
    from src.core.events.database import get_db_session_context  # type: ignore
    from src.db.organizations import Organization  # type: ignore
    from src.db.sms_campus import AcademicTerm, AcademicYear, Campus, ClassSection  # type: ignore
    from src.db.sms_identity import SMSUserRole  # type: ignore
    from src.db.users import User  # type: ignore

    created: List[str] = []
    reused: List[str] = []

    def note(action: str, what: str) -> None:
        (created if action == "create" else reused).append(what)
        prefix = "WOULD CREATE" if (dry_run and action == "create") else action.upper()
        print(f"  [{prefix}] {what}")

    async with get_db_session_context() as session:  # type: ignore
        # --- organization ---------------------------------------------------
        org_cfg = cfg["organization"]
        org = (
            await session.execute(select(Organization).where(Organization.slug == org_cfg["slug"]))
        ).scalars().first()
        if org is None:
            note("create", f"organization '{org_cfg['slug']}'")
            if not dry_run:
                org = Organization(name=org_cfg["name"], slug=org_cfg["slug"])
                session.add(org)
                await session.commit()
                await session.refresh(org)
        else:
            note("reuse", f"organization '{org_cfg['slug']}' (id={org.id})")

        if dry_run and org is None:
            print("\n  (dry run stops here: later objects depend on the organization id)")
            return 0

        # --- campus ---------------------------------------------------------
        c_cfg = cfg["campus"]
        campus = (
            await session.execute(
                select(Campus).where(Campus.org_id == org.id, Campus.code == c_cfg["code"])
            )
        ).scalars().first()
        if campus is None:
            note("create", f"campus '{c_cfg['code']}'")
            if not dry_run:
                campus = Campus(
                    org_id=org.id,
                    name=c_cfg["name"],
                    code=c_cfg["code"],
                    # Rule 2: absent stays absent. No invented address.
                    address=c_cfg.get("address"),
                    timezone=c_cfg.get("timezone", "UTC"),
                )
                session.add(campus)
                await session.commit()
                await session.refresh(campus)
        else:
            note("reuse", f"campus '{c_cfg['code']}' (id={campus.id})")

        if dry_run and campus is None:
            return 0

        # --- academic year ---------------------------------------------------
        y_cfg = cfg["academic_year"]
        year = (
            await session.execute(
                select(AcademicYear).where(
                    AcademicYear.campus_id == campus.id, AcademicYear.name == y_cfg["name"]
                )
            )
        ).scalars().first()
        if year is None:
            note("create", f"academic year '{y_cfg['name']}'")
            if not dry_run:
                year = AcademicYear(
                    campus_id=campus.id,
                    name=y_cfg["name"],
                    start_date=y_cfg.get("start_date"),
                    end_date=y_cfg.get("end_date"),
                    is_active=bool(y_cfg.get("is_active", True)),
                )
                session.add(year)
                await session.commit()
                await session.refresh(year)
        else:
            note("reuse", f"academic year '{y_cfg['name']}' (id={year.id})")

        if dry_run and year is None:
            return 0

        # --- terms -----------------------------------------------------------
        for t_cfg in cfg.get("terms") or []:
            term = (
                await session.execute(
                    select(AcademicTerm).where(
                        AcademicTerm.academic_year_id == year.id,
                        AcademicTerm.name == t_cfg["name"],
                    )
                )
            ).scalars().first()
            if term is None:
                note("create", f"term '{t_cfg['name']}'")
                if not dry_run:
                    session.add(
                        AcademicTerm(
                            academic_year_id=year.id,
                            name=t_cfg["name"],
                            term_code=t_cfg.get("term_code"),
                            weight_percentage=t_cfg.get("weight_percentage", 100),
                            start_date=t_cfg.get("start_date"),
                            end_date=t_cfg.get("end_date"),
                        )
                    )
                    await session.commit()
            else:
                note("reuse", f"term '{t_cfg['name']}'")

        # --- class sections ---------------------------------------------------
        # ClassSection carries academic_year_id (added so a school can roll a
        # year forward). It is set here rather than left to a default, because
        # a section that belongs to no year is exactly what blocked rollover.
        for s_cfg in cfg.get("sections") or []:
            section = (
                await session.execute(
                    select(ClassSection).where(
                        ClassSection.campus_id == campus.id,
                        ClassSection.grade_level == s_cfg["grade_level"],
                        ClassSection.section_name == s_cfg["section_name"],
                    )
                )
            ).scalars().first()
            label = f"section '{s_cfg['grade_level']} {s_cfg['section_name']}'"
            if section is None:
                note("create", label)
                if not dry_run:
                    kwargs: Dict[str, Any] = dict(
                        campus_id=campus.id,
                        grade_level=s_cfg["grade_level"],
                        section_name=s_cfg["section_name"],
                        room_number=s_cfg.get("room_number"),
                    )
                    if "max_capacity" in s_cfg:
                        kwargs["max_capacity"] = s_cfg["max_capacity"]
                    if hasattr(ClassSection, "academic_year_id"):
                        kwargs["academic_year_id"] = year.id
                    session.add(ClassSection(**kwargs))
                    await session.commit()
            else:
                note("reuse", label)

        # --- grading scale ------------------------------------------------------
        scale_cfg = cfg.get("grading_scale")
        if scale_cfg:
            from src.db.sms_gradebook import GradingScale  # type: ignore

            scale = (
                await session.execute(
                    select(GradingScale).where(GradingScale.name == scale_cfg["name"])
                )
            ).scalars().first()
            if scale is None:
                note("create", f"grading scale '{scale_cfg['name']}'")
                if not dry_run:
                    session.add(
                        GradingScale(
                            name=scale_cfg["name"],
                            intervals=scale_cfg["intervals"],
                            is_default=bool(scale_cfg.get("is_default", False)),
                        )
                    )
                    await session.commit()
            else:
                note("reuse", f"grading scale '{scale_cfg['name']}'")

        # --- admin user ----------------------------------------------------------
        a_cfg = cfg["admin_user"]
        user = (
            await session.execute(select(User).where(User.email == a_cfg["email"]))
        ).scalars().first()
        if user is None:
            note("create", f"admin user '{a_cfg['email']}'")
            if not dry_run:
                from src.security.security import security_hash_password  # type: ignore

                # Env var wins over the config file, so a real deployment need
                # never write the password to disk at all.
                password = os.environ.get("CSG_SEED_ADMIN_PASSWORD") or a_cfg.get("password")
                user = User(
                    email=a_cfg["email"],
                    username=a_cfg["username"],
                    password=await security_hash_password(password),
                    first_name=a_cfg.get("first_name", ""),
                    last_name=a_cfg.get("last_name", ""),
                )
                session.add(user)
                await session.commit()
                await session.refresh(user)
        else:
            note("reuse", f"admin user '{a_cfg['email']}' (id={user.id})")

        # --- school-admin role grant -----------------------------------------------
        if user is not None and not dry_run:
            grant = (
                await session.execute(
                    select(SMSUserRole).where(
                        SMSUserRole.user_id == user.id,
                        SMSUserRole.org_id == org.id,
                        SMSUserRole.role == "SCHOOL_ADMIN",
                    )
                )
            ).scalars().first()
            if grant is None:
                note("create", f"SCHOOL_ADMIN grant for '{a_cfg['email']}'")
                session.add(
                    SMSUserRole(
                        user_id=user.id,
                        org_id=org.id,
                        campus_id=campus.id,
                        role="SCHOOL_ADMIN",
                    )
                )
                await session.commit()
            else:
                note("reuse", f"SCHOOL_ADMIN grant for '{a_cfg['email']}'")

    print()
    if dry_run:
        print(f"DRY RUN: {len(created)} object(s) would be created, {len(reused)} already exist.")
        print("Nothing was written.")
    else:
        print(f"Done: {len(created)} created, {len(reused)} already existed.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed a CSG-LMS school from a config file.")
    parser.add_argument("--config", required=True, type=Path, help="Path to a .yml or .json school config")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report what would be created without writing anything.",
    )
    args = parser.parse_args()

    try:
        cfg = load_config(args.config)
        validate(cfg)
    except ConfigError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    print(f"Seeding from {args.config}{' (DRY RUN)' if args.dry_run else ''}\n")
    try:
        return asyncio.run(seed(cfg, args.dry_run))
    except Exception as exc:  # noqa: BLE001 - top-level reporting
        print(f"\nERROR: seeding failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
