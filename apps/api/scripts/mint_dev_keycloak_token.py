#!/usr/bin/env python3
"""
Mint a dev-only Keycloak-shaped Bearer JWT for local SMS/RevOps testing.
==========================================================================

Why this exists: `src/routers/sms_*.py` now require a valid Keycloak OIDC
Bearer token (`src.core.keycloak_auth.get_current_user_principal`), but no
real Keycloak server has ever been deployed for this project (see the
`keycloak` service in `dokploy-compose.yml` / `docker-compose.prod.yml` --
defined, never started here). `keycloak_auth.decode_and_verify_token` already
falls back to verifying HS256 tokens against a shared secret
(`KEYCLOAK_SECRET_KEY` / `AUTH_JWT_SECRET_KEY`, defaulting to
`dev_jwt_secret_key_change_in_production`) when it isn't pointed at a real
JWKS server -- this script mints a token signed with that same secret.

This is the no-server-required alternative to `POST /api/v1/dev/mint_keycloak_token`
(see src/routers/dev.py) -- useful because that HTTP endpoint requires you to
already have a superadmin Learnhouse *session* (an unrelated, native auth
system), which is circular for a first-time local setup.

SAFETY: this refuses to run unless `is_hmac_dev_verification_active()`
(src/core/keycloak_auth.py) returns True -- i.e. unless KEYCLOAK_URL/
KEYCLOAK_SERVER_URL point at localhost and no real JWKS URL / public key is
configured. Pointed at a real Keycloak deployment, this script (and the
equivalent HTTP endpoint) are both inert. See
src/tests/security/test_dev_keycloak_token_minting.py for the tests proving
this.

USAGE (run from the `apps/api` directory so `.env` is picked up):

    uv run python scripts/mint_dev_keycloak_token.py --role TEACHER
    uv run python scripts/mint_dev_keycloak_token.py --role STUDENT --subject-id 7
    uv run python scripts/mint_dev_keycloak_token.py --role PARENT --children-ids 7,8

Then use the printed token as a Bearer token against the API, e.g.:

    curl http://localhost:1338/api/v1/sms/timetable/student/7?section_id=1 \\
      -H "Authorization: Bearer <token>"

FRONTEND: paste the printed token into the "Dev Session" panel the web app
shows when `NEXT_PUBLIC_ENABLE_DEV_AUTH=true` (see
apps/web/lib/api/dev-token.ts), or set it directly in the browser console:
    localStorage.setItem('csg_dev_keycloak_token', '<token>')
apps/web/lib/api/api-client.ts then attaches it as `Authorization: Bearer
<token>` on every SMS module request automatically.
"""

import argparse
import json
import os
import sys

# Run as `python scripts/mint_dev_keycloak_token.py` from apps/api, or
# `uv run python scripts/mint_dev_keycloak_token.py` -- either way, make sure
# apps/api itself (not just scripts/) is on sys.path so `import src...` and
# `import config...` resolve, matching scripts/migrate.py's convention.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.core.dev_tokens import mint_dev_keycloak_token  # noqa: E402
from src.services.dev.dev import isDevModeEnabled  # noqa: E402


def parse_int_list(raw: str):
    if not raw:
        return None
    return [int(x.strip()) for x in raw.split(",") if x.strip()]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--role", default="SCHOOL_ADMIN", help="SUPER_ADMIN, SCHOOL_ADMIN, TEACHER, STUDENT, PARENT, STAFF, or PSYCHOLOGIST")
    parser.add_argument("--sub", default="dev-user-1", help="Keycloak subject / user UUID")
    parser.add_argument("--email", default="dev@csg.edu.pk")
    parser.add_argument("--name", default="Dev Tester")
    parser.add_argument("--org-id", type=int, default=1)
    parser.add_argument("--campus-id", type=int, default=1)
    parser.add_argument("--subject-id", type=int, default=1, help="'My' student_id/staff_id/teacher_id -- see mint_dev_keycloak_token docstring")
    parser.add_argument("--section-id", type=int, default=1)
    parser.add_argument("--academic-term-id", type=int, default=1)
    parser.add_argument("--children-ids", type=str, default=None, help="Comma-separated student_ids, for --role PARENT")
    parser.add_argument("--expires-minutes", type=int, default=480)
    parser.add_argument("--json", action="store_true", help="Print the full JSON response instead of just the token")
    args = parser.parse_args()

    if not isDevModeEnabled():
        print(
            "ERROR: LEARNHOUSE_DEVELOPMENT_MODE is not enabled. This script is "
            "for local development only. Set LEARNHOUSE_DEVELOPMENT_MODE=true "
            "in apps/api/.env.",
            file=sys.stderr,
        )
        return 1

    try:
        minted = mint_dev_keycloak_token(
            role=args.role,
            sub=args.sub,
            email=args.email,
            name=args.name,
            org_id=args.org_id,
            campus_id=args.campus_id,
            subject_id=args.subject_id,
            section_id=args.section_id,
            academic_term_id=args.academic_term_id,
            children_ids=parse_int_list(args.children_ids),
            expires_in_minutes=args.expires_minutes,
        )
    except RuntimeError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1
    except ValueError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(minted, indent=2))
    else:
        print(minted["access_token"])
        print(f"\n# Claims: {json.dumps(minted['claims'])}", file=sys.stderr)
        print(f"# Expires in: {minted['expires_in']}s", file=sys.stderr)
        print("\n# Example usage:", file=sys.stderr)
        print(
            f'curl http://localhost:1338/api/v1/sms/campuses/ -H "Authorization: Bearer {minted["access_token"]}"',
            file=sys.stderr,
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
