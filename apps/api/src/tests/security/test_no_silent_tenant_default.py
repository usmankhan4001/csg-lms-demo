"""A tenant that cannot be established is missing -- never organisation 1.

Eighteen call sites across `sms_cognia`, `sms_gradebook`, `sms_revops_config`
and `sms_settings` resolved their tenant as `principal.org_id or 1`. When a
principal carried no organisation, every one silently read AND WROTE the data
of organisation 1 -- whichever school holds the lowest id. Concretely:
`update_settings_group` wrote another school's settings, `delete_knowledge_
entry` deleted its knowledge base rows, `submit_cognia_evidence` filed evidence
into its accreditation binder, and `generate_official_transcript` stamped its
name onto a document headed "OFFICIAL".

Four of those sites were reachable by any authenticated user, because every
`sms_cognia` endpoint gates on a bare `get_current_user_principal` with no role
requirement -- and `resolve_school_principal` leaves `org_id` None for a user
holding zero `SMSUserRole` grants. The other fourteen sit behind `require_roles`
and were defensive rather than live, but `require_roles` short-circuits for a
SUPER_ADMIN *before* checking anything, and a SUPER_ADMIN on an instance where
`_get_default_org_id` finds no organisation also arrives with `org_id` None.

This test guards the SHAPE rather than the string, so the defect cannot return
wearing different syntax. It parses the AST, so prose in a comment or docstring
that merely *describes* the pattern (this file included) is not a match.
"""

import ast
from pathlib import Path
from typing import Iterator, List, Tuple

import pytest

# Directories where a tenant identifier is resolved for a real request.
SCANNED = ("routers", "services", "security", "core")

SRC = Path(__file__).resolve().parents[2]

TENANT_FIELDS = {"org_id", "organization_id"}


def _python_files() -> Iterator[Path]:
    for area in SCANNED:
        root = SRC / area
        if not root.is_dir():
            continue
        for path in root.rglob("*.py"):
            if "__pycache__" in path.parts:
                continue
            yield path


def _is_tenant_ref(node: ast.AST) -> bool:
    """`x.org_id`, or a bare `org_id` name."""
    if isinstance(node, ast.Attribute) and node.attr in TENANT_FIELDS:
        return True
    if isinstance(node, ast.Name) and node.id in TENANT_FIELDS:
        return True
    return False


def _is_plausible_org_id(node: ast.AST) -> bool:
    """A literal int that could name a REAL organisation, so >= 1.

    The distinction matters and is not pedantry. Organisation ids start at 1,
    so `or 1` resolves to whichever school holds the lowest id -- a live tenant
    whose records are then read and written. `or 0` names no organisation at
    all: a SELECT returns nothing and an INSERT trips the foreign key. Sloppy,
    but not a cross-tenant leak, and not what this guard is for.

    Four `or 0` defaults exist today in features_utils/resolve.py,
    courses/activities/pdf.py, setup/setup.py and sms/revops_acknowledge.py.
    They are reported as a separate, lesser finding rather than swept in here,
    because widening this guard to catch them would change four files that
    close no leak and belong to other owners.
    """
    return (
        isinstance(node, ast.Constant)
        and isinstance(node.value, int)
        and not isinstance(node.value, bool)
        and node.value >= 1
    )


def _offences_in(tree: ast.AST) -> List[Tuple[int, str]]:
    found: List[Tuple[int, str]] = []

    for node in ast.walk(tree):
        # org_id or 1
        if isinstance(node, ast.BoolOp) and isinstance(node.op, ast.Or):
            values = node.values
            for left, right in zip(values, values[1:]):
                if _is_tenant_ref(left) and _is_plausible_org_id(right):
                    found.append((node.lineno, "`<tenant> or <int>`"))

        # org_id if org_id else 1   /   1 if org_id is None else org_id
        #
        # The precise shape is one branch resolving to the tenant and the other
        # to a literal id. Merely *testing* a tenant while returning a number
        # is something else entirely -- `_get_purchased_extra(...) if org_id
        # else 0` returns a purchased quantity, not an organisation -- so the
        # branches are inspected, not just the condition.
        if isinstance(node, ast.IfExp):
            branches = (node.body, node.orelse)
            tenant_branch = any(_is_tenant_ref(b) for b in branches)
            literal_branch = any(_is_plausible_org_id(b) for b in branches)
            if tenant_branch and literal_branch:
                found.append((node.lineno, "`<tenant> if ... else <int>`"))

        if isinstance(node, ast.Call):
            # getattr(principal, "org_id", 1)
            if isinstance(node.func, ast.Name) and node.func.id == "getattr" and len(node.args) == 3:
                key, default = node.args[1], node.args[2]
                if (
                    isinstance(key, ast.Constant)
                    and key.value in TENANT_FIELDS
                    and _is_plausible_org_id(default)
                ):
                    found.append((node.lineno, "`getattr(..., '<tenant>', <int>)`"))

            # claims.get("org_id", 1)
            if (
                isinstance(node.func, ast.Attribute)
                and node.func.attr == "get"
                and len(node.args) == 2
            ):
                key, default = node.args
                if (
                    isinstance(key, ast.Constant)
                    and key.value in TENANT_FIELDS
                    and _is_plausible_org_id(default)
                ):
                    found.append((node.lineno, "`.get('<tenant>', <int>)`"))

    return found


class TestNoSilentTenantDefault:
    def test_no_module_defaults_a_missing_tenant_to_a_literal_org(self):
        offences: List[str] = []

        for path in _python_files():
            try:
                tree = ast.parse(path.read_text(encoding="utf-8"))
            except SyntaxError:  # pragma: no cover - a broken file fails elsewhere
                continue
            for lineno, shape in _offences_in(tree):
                offences.append(f"{path.relative_to(SRC)}:{lineno} -- {shape}")

        assert not offences, (
            "A request whose tenant cannot be established must be refused, never "
            "silently attributed to a literal organisation id. Use "
            "`require_org_id(principal)` from src/security/school_ownership.py.\n"
            "Found:\n  " + "\n  ".join(sorted(offences))
        )


class TestGuardActuallyDetects:
    """The guard above is worthless if it cannot see the defect it removed.

    Each case is the real code that was in the tree, so a future refactor of
    the detector is checked against what actually shipped.
    """

    @pytest.mark.parametrize(
        "source",
        [
            'org_id = principal.org_id or 1',
            'x = f"org_{principal.org_id or 1}"',
            'resolved = resolve_all_groups(session, principal.org_id or 1, campus)',
            'org_id = principal.org_id if principal.org_id else 1',
            'org_id = 1 if principal.org_id is None else principal.org_id',
            'org_id = getattr(principal, "org_id", 1)',
            'org_id = claims.get("org_id", 1)',
            'org_id = organization_id or 1',
        ],
    )
    def test_detects_each_disguise(self, source):
        assert _offences_in(ast.parse(source)), f"guard missed: {source}"

    @pytest.mark.parametrize(
        "source",
        [
            # The fix itself.
            'org_id = require_org_id(principal)',
            # Defaulting to None is honest -- it stays None and is checked.
            'org_id = principal.org_id or None',
            # Unrelated `or 1`: version and attempt numbers legitimately do this.
            'activity.current_version = (activity.current_version or 1) + 1',
            'attempt = int(getattr(sub, "attempt_number", 1) or 1)',
            # A campus default is a different concern with its own helpers.
            'campus_id = principal.campus_id or 1',
            # Defaulting to 0 names no organisation: a SELECT finds nothing and
            # an INSERT trips the foreign key, so it cannot expose another
            # school. These four exist in the tree today and are a separate,
            # lesser finding -- see _is_plausible_org_id.
            'org_id = org_id or 0',
            'org_id = org_id if org_id else 0',
            'return int(campus.org_id) if campus and campus.org_id else 0',
            'purchased = _get_purchased_extra(org_id, feature, x) if org_id else 0',
        ],
    )
    def test_does_not_fire_on_legitimate_code(self, source):
        assert not _offences_in(ast.parse(source)), f"false positive: {source}"
