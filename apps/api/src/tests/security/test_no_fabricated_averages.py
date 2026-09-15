"""An average over nothing is not zero, and not any other number.

This repository has removed nine separate fabrication defects. The sharpest
were all the same shape: a MEASUREMENT computed over a possibly-empty set,
with a plausible-looking numeric literal supplied when the set turned out to
be empty.

  * A gradebook endpoint returned ``unweighted_gpa: 4.0``, ``academic_standing:
    "Good Standing"`` and ``honor_roll: True`` for a student with zero grade
    entries -- live in a router for weeks.
  * The Student 360 mastery radar scored every unassessed concept 0.0, so a
    newly enrolled child averaged 0% and was labelled "Novice" in every
    subject: a verdict on a child manufactured out of no evidence.
  * An admissions board rendered "0% Enrolled Conversion Rate" to a school
    that had not yet entered a single enquiry.

The correct answer in every one of these cases is "no value" -- ``None``,
omitted, or an explicit not-recorded state. A reader can act on "not measured".
A reader acts *wrongly* on a number that was invented.

WHAT THIS GUARDS, AND WHY IT IS DRAWN THIS NARROWLY
---------------------------------------------------
Exactly one expression shape is flagged: ``sum(...) / len(...)`` -- an
arithmetic mean over a collection -- given a numeric literal when the
collection is empty.

That shape is flagged because it is the only one where the AST alone proves
fabrication. An empty collection was not measured, so its mean is not a
number; the honest result is ``None``.

A first draft of this guard also flagged percentages (``a / b * 100``). It
was withdrawn, because it could not tell these apart:

  * ``(occupied / capacity * 100) if capacity > 0 else 0.0`` -- capacity is a
    configured total. Zero means "no rooms set up", and reporting 0% is
    genuinely misleading...
  * ``(completed / total * 100) if total > 0 else 0`` -- ...but here zero means
    an empty course, where "0% complete" is defensible.

Both are the same syntax and different facts. A guard that flagged ten
borderline cases to catch three real ones would be deleted by the first
person it obstructed, and would then protect nothing. Those cases are listed
in this module's companion report rather than enforced here.

A COUNT or a QUANTITY defaulting to zero is also NOT flagged: zero unread
messages really is zero, and four deliberate ``or 0`` defaults elsewhere in
this tree (in ``features_utils/resolve.py``, ``courses/activities/pdf.py``,
``setup/setup.py`` and ``sms/revops_acknowledge.py``) are quantities that a
previous audit examined and correctly left alone.

KNOWN LIMITATION: this walks expressions (``IfExp``, ``BoolOp``), so the same
fabrication written as an ``if``/``else`` *statement* is not caught. That is a
deliberate trade -- statement form forces the author to write the empty case
on its own line, where a reviewer can see it and a comment can justify it.

The check is AST-based, so prose that merely *describes* the pattern -- this
docstring included -- is not a match.
"""

import ast
from pathlib import Path
from typing import Dict, Iterator, List, Tuple

SRC = Path(__file__).resolve().parents[2]

SCANNED = ("routers", "services")

# Files with a real, currently-present offence owned by another workstream.
# An entry is a debt tracked in the open, NOT an exemption on merit: the
# companion test below fails if an entry outlives the defect it names, so the
# allowlist can never quietly become a hiding place. Empty, and should stay so.
KNOWN_UNFIXED: Dict[str, str] = {}


def _python_files() -> Iterator[Path]:
    for area in SCANNED:
        for path in (SRC / area).rglob("*.py"):
            if "__pycache__" in path.parts:
                continue
            yield path


def _rel(path: Path) -> str:
    return path.relative_to(SRC).as_posix()


def _is_numeric_literal(node: ast.AST) -> bool:
    """A bare number. ``None`` is the CORRECT empty answer and is not one."""
    if isinstance(node, ast.Constant):
        return isinstance(node.value, (int, float)) and not isinstance(
            node.value, bool
        )
    # round(0.0, 2) and float(0) are literals wearing a hat.
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
        if node.func.id in {"round", "float", "int"} and node.args:
            return _is_numeric_literal(node.args[0])
    # Unary minus on a literal.
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        return _is_numeric_literal(node.operand)
    return False


def _unwrap(node: ast.AST) -> ast.AST:
    """Peel ``round(...)``/``float(...)`` off an expression."""
    while isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
        if node.func.id in {"round", "float"} and node.args:
            node = node.args[0]
        else:
            break
    return node


def _calls(node: ast.AST, name: str) -> bool:
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == name
    )


def _is_measurement(node: ast.AST) -> bool:
    """True only for an arithmetic mean: ``sum(...) / len(...)``.

    Both halves are required. ``sum(x) / total_credits`` is a weighted mean
    over a real denominator that the caller has already established is
    non-zero, and is not this defect.
    """
    for sub in ast.walk(node):
        if isinstance(sub, ast.BinOp) and isinstance(sub.op, ast.Div):
            if _calls(_unwrap(sub.left), "sum") and _calls(_unwrap(sub.right), "len"):
                return True
    return False


def _offences_in(tree: ast.AST) -> List[Tuple[int, str]]:
    """Every measurement given a literal fallback, as (lineno, description)."""
    found: List[Tuple[int, str]] = []

    for node in ast.walk(tree):
        # `mean if xs else 0.0`
        if isinstance(node, ast.IfExp):
            if _is_measurement(node.body) and _is_numeric_literal(node.orelse):
                found.append(
                    (node.lineno, "measurement with a literal fallback (`... if ... else <number>`)")
                )
            # The inverted spelling: `0.0 if not xs else mean`
            elif _is_measurement(node.orelse) and _is_numeric_literal(node.body):
                found.append(
                    (node.lineno, "measurement with a literal fallback (inverted ternary)")
                )

        # `mean or 0.0`
        if isinstance(node, ast.BoolOp) and isinstance(node.op, ast.Or):
            values = node.values
            for earlier, later in zip(values, values[1:]):
                if _is_measurement(earlier) and _is_numeric_literal(later):
                    found.append(
                        (node.lineno, "measurement with a literal fallback (`... or <number>`)")
                    )

    return found


def test_no_measurement_falls_back_to_a_literal() -> None:
    """A mean over an empty collection must never resolve to a number."""
    offences: List[str] = []

    for path in _python_files():
        rel = _rel(path)
        if rel in KNOWN_UNFIXED:
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:  # pragma: no cover - a broken file is another test's problem
            continue
        for lineno, why in _offences_in(tree):
            offences.append(f"{rel}:{lineno} -- {why}")

    assert offences == [], (
        "An average over an empty set has no numeric answer. "
        "Return None (or omit the field) and let the caller render 'not "
        "recorded'; a plausible number here is indistinguishable from a real "
        "measurement and will be acted on as one.\n  "
        + "\n  ".join(offences)
    )


def test_known_unfixed_entries_still_exist_and_still_offend() -> None:
    """The debt list must not outlive the debt.

    If a file here has been fixed (or deleted), its entry has to go, or the
    allowlist quietly becomes a place where new defects can hide.
    """
    stale: List[str] = []

    for rel, reason in KNOWN_UNFIXED.items():
        path = SRC / rel
        if not path.exists():
            stale.append(f"{rel} no longer exists")
            continue
        if not _offences_in(ast.parse(path.read_text(encoding="utf-8"))):
            stale.append(f"{rel} no longer offends -- delete its entry")
        assert reason.strip(), f"{rel} needs a reason, not a bare exemption"

    assert stale == [], (
        "KNOWN_UNFIXED is out of date. Remove these entries:\n  "
        + "\n  ".join(stale)
    )


# ---------------------------------------------------------------------------
# Self-tests: what the guard must catch, and what it must leave alone.
#
# A guard that false-positives gets deleted by the first person it obstructs,
# and then protects nothing -- so the "must not flag" half below matters at
# least as much as the "must flag" half.
# ---------------------------------------------------------------------------

MUST_FLAG = [
    # The real defects, in the spellings they actually appeared in.
    "x = round(sum(scores) / len(scores), 2) if scores else 0.0",
    "x = sum(s.pct for s in rows) / len(rows) if rows else 0.0",
    "x = round(sum(v) / len(v), 4) if v else 1.0",
    "x = sum(total_scores) / len(total_scores) if total_scores else 0.0",
    # Disguises.
    "x = 0.0 if not rows else sum(rows) / len(rows)",
    "x = (sum(xs) / len(xs)) or 0.0",
    "x = round(sum(xs) / len(xs), 2) if xs else round(0.0, 2)",
    "x = sum(xs) / len(xs) if xs else -1",
    "x = float(sum(xs)) / len(xs) if xs else 0",
]

MUST_NOT_FLAG = [
    # The correct spelling.
    "x = round(sum(scores) / len(scores), 2) if scores else None",
    "x = sum(xs) / len(xs) if xs else None",
    # Quantities and counts -- zero is a real answer.
    "x = len(rows) or 0",
    "x = total_unread if total_unread else 0",
    "x = extra_limit or 0",
    "x = (plan_limit + extra) if plan_limit else 0",
    # A mean with no fallback at all.
    "x = sum(xs) / len(xs)",
    # A weighted mean over an already-validated denominator: the caller has
    # established total_credits > 0, and this is not the empty-set case.
    "x = sum(s.pts * s.credits for s in g) / total_credits if g else None",
    # Percentages over a CONFIGURED total. Deliberately out of scope -- see the
    # module docstring. Zero capacity is a misconfiguration, not an absence of
    # measurement, and the two are indistinguishable at the syntax level.
    "x = (occupied / capacity * 100.0) if capacity > 0 else 0.0",
    "x = round(completed / total * 100, 1) if total > 0 else 0",
    "x = (raw_score / max_score * 100.0) if max_score > 0 else 0.0",
    # A plain ratio that is not a mean.
    "x = (total / page_size) if page_size else 0",
]


def test_guard_catches_every_known_disguise() -> None:
    missed = [src for src in MUST_FLAG if not _offences_in(ast.parse(src))]
    assert missed == [], "The guard failed to flag:\n  " + "\n  ".join(missed)


def test_guard_leaves_legitimate_shapes_alone() -> None:
    wrong = [src for src in MUST_NOT_FLAG if _offences_in(ast.parse(src))]
    assert wrong == [], (
        "The guard false-positived on legitimate code. A guard that cries wolf "
        "gets deleted, and then guards nothing:\n  " + "\n  ".join(wrong)
    )
