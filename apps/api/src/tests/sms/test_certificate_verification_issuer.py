"""A certificate with no template must not name an issuer it cannot prove.

`verify_certificate` is the PUBLIC endpoint -- the one an employer or a
university reads to decide whether a credential someone showed them is real.
It used to fall back to `issuer_name="Official Board"` and
`issuer_title="Authorized Issuer"` whenever the issuing template row was
missing, which asserts that a named authority stands behind a certificate the
system can no longer attribute to anyone.

Everything the system DOES know -- recipient, title, issue date, and whether it
has been revoked -- is still returned. Only the unprovable claim is withheld.
"""

import pytest

from src.services.sms.certificates import CertificateService


class TestPublicVerificationNeverInventsAnIssuer:
    @pytest.mark.asyncio
    async def test_missing_template_yields_no_issuer(self, monkeypatch):
        class _Cert:
            template_id = 4242
            recipient_name = "A Student"
            title = "Certificate of Completion"
            honors = None
            issue_date = "2026-09-15"
            is_revoked = False
            revocation_reason = None
            verification_hash = "abc123"

        class _Result:
            def first(self):
                return _Cert()

        class _DB:
            async def exec(self, *_a, **_k):
                return _Result()

            async def get(self, *_a, **_k):
                # The template row is gone -- the exact condition that used to
                # manufacture "Official Board".
                return None

        resp = await CertificateService.verify_certificate(_DB(), "abc123")

        assert resp.issuer_name is None, (
            "An unattributable certificate must not name an issuer. "
            f"Got {resp.issuer_name!r}."
        )
        assert resp.issuer_title is None

        # The facts the system genuinely holds are still reported.
        assert resp.recipient_name == "A Student"
        assert resp.title == "Certificate of Completion"
        assert resp.is_revoked is False
        assert resp.is_valid is True
