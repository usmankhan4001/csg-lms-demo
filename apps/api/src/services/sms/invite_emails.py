"""
The invite email itself.

Kept in its own module rather than added to `services/users/emails.py` for two
reasons: that file is Learnhouse's own lifecycle mail and is being edited
concurrently, and a school invite is a CSG-LMS concept rather than a platform
one. The shared layout, button and logo helpers are imported rather than
reimplemented, so this message looks like every other email the platform sends
and inherits white-labelling for free.

WHAT THIS EMAIL MUST NEVER CONTAIN: a password. Not a generated one, not a
temporary one, not "your password is currently X, please change it". The whole
point of the provisioning design is that no password exists for this account
until the person chooses one. The email carries a single-use link and nothing
else that could sign anyone in.
"""

from __future__ import annotations

import html
import logging
from typing import Optional
from urllib.parse import quote

from src.services.email.utils import send_email
from src.services.users.emails import (
    STYLES,
    _brand_logo_html,
    _button_style,
    _email_layout,
)

logger = logging.getLogger(__name__)


def build_invite_url(base_url: str, org_id: int, email: str, code: str) -> str:
    """The link the recipient clicks to choose a password.

    Every component is URL-encoded: an email local part may legally contain
    characters that would otherwise terminate or inject a query parameter.
    """
    # `/accept-invite`, NOT `/auth/accept-invite`. The web proxy rewrites a
    # short set of public auth paths (`/login`, `/reset`, `/forgot` ...) into
    # `/auth/*` after resolving the tenant; a link sent straight to the internal
    # path falls through to the tenant catch-all, gets rewritten again to
    # `/orgs/{slug}/auth/...` and 404s. That is documented in proxy.ts against
    # the magic-login link, which was emailed broken for exactly this reason.
    root = (base_url or "").rstrip("/")
    return (
        f"{root}/accept-invite"
        f"?org_id={int(org_id)}"
        f"&email={quote(str(email), safe='')}"
        f"&code={quote(str(code), safe='')}"
    )


def send_school_invite_email(
    *,
    email: str,
    first_name: str,
    org_name: str,
    role_label: str,
    invite_url: str,
    expires_in_days: int,
    lang: str = "en",
    sender_name: Optional[str] = None,
    logo_url: Optional[str] = None,
    brand_color: Optional[str] = None,
    powered_by: bool = True,
):
    """Send one invite. Returns whatever the mail layer returned, or raises.

    Deliberately NOT swallowing exceptions here. The caller classifies the
    outcome into an honest invite status via `invites.classify_dispatch`, and it
    can only do that if it sees what actually happened. A swallowed failure
    would be recorded as a successful send and the family would be chased by
    nobody.
    """
    safe_org = html.escape(org_name or "your school")
    safe_name = html.escape((first_name or "").strip() or "there")
    safe_role = html.escape(role_label or "member")

    heading = f"Your {safe_org} account is ready"

    body_content = f"""
        <h1 style="{STYLES['h1']}">{heading}</h1>
        <p style="{STYLES['p']}">
            Hello {safe_name}, an account has been created for you at
            <strong>{safe_org}</strong> as a {safe_role}.
        </p>
        <p style="{STYLES['p']}">
            Choose your password to finish setting it up. No password has been
            set for you, so this link is the only way in.
        </p>
        <a href="{invite_url}" style="{_button_style(brand_color)}">
            Choose your password
        </a>
        <p style="{STYLES['p']}" >
            This link can be used once, and expires in {int(expires_in_days)} days.
        </p>
        <p style="{STYLES['link_text']}">{html.escape(invite_url)}</p>
    """

    return send_email(
        to=email,
        subject=f"Your {org_name} account is ready",
        body=_email_layout(
            title=heading,
            body_content=body_content,
            footer_note=(
                "If you were not expecting this, you can ignore this email and "
                "no account will be activated."
            ),
            logo_html=_brand_logo_html(logo_url, org_name),
            powered_by=powered_by,
            lang=lang,
        ),
        sender_name=sender_name,
    )
