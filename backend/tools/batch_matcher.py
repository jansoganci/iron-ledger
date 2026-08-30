"""Item 1 — bank/processor three-way matcher.

**PR-A ships this module INERT.** It contains identity construction and the
internal fee gate only. There is no matching logic, no call site, and nothing
in the running pipeline imports it. The three passes (ID → amount+date →
leftovers) and `_classify` land in PR-B.

Deterministic pandas only. No Claude, no DB, no I/O, no fuzzy matching.

Spec: docs/sprint/kova2-implementation-plan.md, item 1, sections C.5 / C.5.1,
including decisions E.1 (fee_pct is computed, never stored) and E.4 (match_id
construction).
"""

from __future__ import annotations

from datetime import date
from typing import Literal

MatchKind = Literal["id", "amount_date", "none"]
LeftoverSide = Literal["fsm", "bank"]


def norm(value: object | None) -> str | None:
    """Normalize a join id: ``None`` when null/blank, else stripped + casefolded.

    Per C.5.1: ``norm(id) := None if id is null/blank else
    str(id).strip().casefold()``. A blank ref is not an id — it must never
    match another blank ref on ID.
    """
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    return text.casefold()


def fee_pct(gross: float, fee: float) -> float | None:
    """Internal pandas gate for the 3-8% band (decision E.1).

    Never stored on ``BatchMatch``, never serialized, never a prompt
    placeholder. Returns None when gross is 0.
    """
    if gross == 0:
        return None
    return abs(fee) / abs(gross)


def build_match_id(
    match_kind: MatchKind,
    *,
    id_val: object | None = None,
    amount: float | None = None,
    day: date | None = None,
    side: LeftoverSide | None = None,
    ref: object | None = None,
    seq: int | None = None,
) -> str:
    """Construct the deterministic ``BatchMatch.match_id`` (decision E.4).

    Same input files must always produce the same id, because C.8 may key
    per-batch speech off it. Every component is derived from file content:
    the normalized id, the amount rounded to 2dp, the calendar date, and for
    null-ref leftovers a ``seq`` taken from ``_orig_row_index`` order.

    **Forbidden by spec** — do not "helpfully" substitute any of these:
    a UUID, a hash of object identity, a global insertion counter, or anything
    derived from dict/set iteration order. ``tests/tools/test_batch_match_id.py``
    is written to fail if one is introduced.

    Ambiguity is a document defect, not a coding decision: this function raises
    rather than inventing a fallback when a required component is missing.
    """
    if match_kind == "id":
        normalized = norm(id_val)
        if normalized is None:
            raise ValueError(
                "match_kind='id' requires a non-blank id_val; a blank ref "
                "never forms an ID match (C.5.1 join-key hierarchy)"
            )
        return normalized

    if match_kind == "amount_date":
        if amount is None or day is None:
            raise ValueError(
                "match_kind='amount_date' requires the group key (amount, day); "
                "it is taken from the group, never from a member row"
            )
        return f"ad:{amount:.2f}:{day.isoformat()}"

    if match_kind == "none":
        if side not in ("fsm", "bank"):
            raise ValueError("match_kind='none' requires side='fsm' or side='bank'")
        normalized_ref = norm(ref)
        if normalized_ref is not None:
            return f"none:{side}:{normalized_ref}"
        if amount is None or day is None or seq is None:
            raise ValueError(
                "a null-ref leftover requires amount, day and seq; seq is the "
                "0-based ordinal among same-side leftovers sharing that amount "
                "and date, in ascending _orig_row_index order"
            )
        return f"none:{side}:{amount:.2f}:{day.isoformat()}:{seq}"

    raise ValueError(f"unknown match_kind: {match_kind!r}")
