"""
Dev-only Keycloak-shaped token minting
=======================================

CSG-LMS's SMS/RevOps routers (`src/routers/sms_*.py`) authenticate callers
via `src.core.keycloak_auth.get_current_user_principal`, which expects a
Keycloak OIDC Bearer JWT. No real Keycloak server has ever been deployed for
this project -- the `keycloak` service in `dokploy-compose.yml` /
`docker-compose.prod.yml` is defined but has never been started here, and the
frontend's actual login flow (`apps/web/app/auth/login`, `src/security/auth.py`)
is Learnhouse's own native session system, entirely unrelated to Keycloak.

`keycloak_auth.decode_and_verify_token` already supports an HS256
shared-secret fallback (`KEYCLOAK_SECRET_KEY` / `AUTH_JWT_SECRET_KEY`,
defaulting to `dev_jwt_secret_key_change_in_production`) for exactly this
situation. This module mints tokens signed with that same secret so a
developer can exercise the now-authenticated SMS/RevOps endpoints locally
without standing up Keycloak.

SAFETY: `mint_dev_keycloak_token()` refuses to run (raises `RuntimeError`)
unless `is_hmac_dev_verification_active()` (see `src.core.keycloak_auth`)
returns True -- i.e. unless this deployment is *not* pointed at a real
Keycloak JWKS/host. That check is independent of anything this module does,
so it stays correct even if this module is imported somewhere unexpected.

HOW TO GET A TOKEN:
  * CLI (no running server, no session needed):
      cd apps/api && uv run python scripts/mint_dev_keycloak_token.py --role TEACHER
  * HTTP (requires a superadmin Learnhouse session -- see src/routers/dev.py):
      POST /api/v1/dev/mint_keycloak_token

HOW THE FRONTEND USES IT: see `apps/web/lib/api/dev-token.ts` (stores the
token, e.g. in `localStorage['csg_dev_keycloak_token']`) and
`apps/web/lib/api/api-client.ts` (attaches it as `Authorization: Bearer
<token>` on every SMS module fetch).
"""

import datetime
from typing import Any, Dict, List, Optional

import jwt

from src.core.keycloak_auth import ALL_REALM_ROLES, is_hmac_dev_verification_active, settings

DEFAULT_EXPIRES_IN_MINUTES = 480  # 8 hours -- long enough for a dev session


def mint_dev_keycloak_token(
    *,
    role: str = "SCHOOL_ADMIN",
    sub: str = "dev-user-1",
    email: Optional[str] = "dev@csg.edu.pk",
    name: Optional[str] = "Dev Tester",
    org_id: Optional[int] = 1,
    campus_id: Optional[int] = 1,
    subject_id: Optional[int] = 1,
    section_id: Optional[int] = 1,
    academic_term_id: Optional[int] = 1,
    children_ids: Optional[List[int]] = None,
    expires_in_minutes: int = DEFAULT_EXPIRES_IN_MINUTES,
) -> Dict[str, Any]:
    """
    Mint an HS256 Keycloak-shaped JWT signed with `settings.shared_secret`.

    `subject_id` is a CSG-LMS-specific convenience claim, not part of the
    real Keycloak contract: none of the `sms_*` routers resolve "my own
    student_id / staff_id" from the JWT today (they all take an explicit
    numeric id path/query param), so there is currently no server-side way to
    ask "who am I in the SMS domain". This claim lets the frontend dev harness
    decode its own minted token (see apps/web/lib/api/dev-token.ts) and use
    that id consistently as student_id / staff_id / teacher_id depending on
    role, so the 5 rebuilt dashboard pages can show "my" data end-to-end
    against the real endpoints without needing a new backend identity-lookup
    endpoint (out of scope here -- see AGENT scope boundary on sms_*.py).

    Returns a dict with `access_token`, `token_type`, `expires_in`, and the
    decoded `claims` (for display/debugging), mirroring a normal OAuth token
    response shape.

    Raises:
        RuntimeError: if this deployment is not configured for HMAC/dev
            Keycloak verification (see `is_hmac_dev_verification_active`).
        ValueError: if `role` is not a known realm role.
    """
    if not is_hmac_dev_verification_active():
        raise RuntimeError(
            "Refusing to mint a dev Keycloak token: this deployment looks like "
            "it is configured for a real Keycloak server (a JWKS URL, a pinned "
            "public key, or a non-localhost Keycloak host is set). This utility "
            "only works against HMAC/shared-secret dev verification."
        )

    normalized_role = role.upper()
    if normalized_role not in ALL_REALM_ROLES:
        raise ValueError(f"Unknown role '{role}'. Must be one of {sorted(ALL_REALM_ROLES)}")

    now = datetime.datetime.now(datetime.timezone.utc)
    exp = now + datetime.timedelta(minutes=expires_in_minutes)

    claims: Dict[str, Any] = {
        "sub": sub,
        "email": email,
        "preferred_username": email,
        "name": name,
        "org_id": org_id,
        "campus_id": campus_id,
        "realm_access": {"roles": [normalized_role]},
        # CSG-LMS dev convenience claims (see docstring above) -- not part of
        # KeycloakUserPrincipal's typed fields, but preserved in
        # principal.raw_claims and readable by the frontend from the token
        # payload directly.
        "subject_id": subject_id,
        "section_id": section_id,
        "academic_term_id": academic_term_id,
        "children_ids": children_ids if children_ids is not None else ([subject_id] if subject_id is not None else []),
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp()),
    }
    if settings.issuer:
        claims["iss"] = settings.issuer

    token = jwt.encode(claims, settings.shared_secret, algorithm="HS256")

    return {
        "access_token": token,
        "token_type": "Bearer",
        "expires_in": expires_in_minutes * 60,
        "claims": claims,
    }
