"""Item 1 PR-B — interpreter force-class and guardrail wiring for `matches`.

Two things under test:

1. When an item carries three-way `matches`, the account-level class is the
   pandas residue and Claude cannot override it — including over the Kova 1
   account-total fee hint (C.7: no double speech on one card).
2. Every pandas number Claude is allowed to copy from a nested match reaches
   the guardrail's reference pool, and `fee_pct` does not.
"""

from __future__ import annotations

from datetime import date

import pytest

from backend.agents.interpreter import (
    _apply_reconciliation_classifications,
    _residue_from_matches,
)
from backend.domain.contracts import BatchMatch
from backend.tools.guardrail import verify_guardrail


def _match(classification: str | None = None, **overrides) -> dict:
    payload = {
        "match_id": "pz-100",
        "processor_ref": "PZ-100",
        "bank_ref": "PZ-100",
        "gl_ref": "PZ-100",
        "gl_account": "Undeposited Funds",
        "gl_amount": 1000.0,
        "gross": 1000.0,
        "fee": 45.0,
        "net": 955.0,
        "settlement_date": date(2026, 3, 15),
        "match_kind": "id",
        "ambiguous": False,
        "candidate_count": 1,
        "unmatched": False,
        "classification": classification,
    }
    payload.update(overrides)
    return payload


def _item(**overrides) -> dict:
    payload = {
        "account": "Undeposited Funds",
        "category": "REVENUE",
        "sources": [],
        "gl_amount": 1000.0,
        "non_gl_total": 1000.0,
        "delta": 0.0,
        "hints": {},
    }
    payload.update(overrides)
    return payload


# ---------------------------------------------------------------------------
# Force-class
# ---------------------------------------------------------------------------


def test_matches_force_the_account_class_over_claude() -> None:
    items = [_item(matches=[_match("missing_je")])]
    _apply_reconciliation_classifications(items, {"Undeposited Funds": "timing_cutoff"})
    assert items[0]["classification"] == "missing_je"


def test_matches_outrank_the_account_total_fee_hint() -> None:
    """C.7: three-way result wins over is_processor_fee_gap — no double speech."""
    items = [
        _item(
            hints={"is_processor_fee_gap": True},
            matches=[_match("missing_je")],
        )
    ]
    _apply_reconciliation_classifications(items, {})
    assert items[0]["classification"] == "missing_je"


def test_matches_outrank_deposit_and_annual_hints() -> None:
    for hint in ("is_customer_deposit", "looks_like_annual_prepayment"):
        items = [
            _item(hints={hint: True}, matches=[_match("categorical_misclassification")])
        ]
        _apply_reconciliation_classifications(items, {})
        assert items[0]["classification"] == "categorical_misclassification", hint


def test_residue_is_most_action_requiring_not_first_or_last() -> None:
    items = [
        _item(
            matches=[
                _match("structural_explained"),
                _match("missing_je"),
                _match("timing_cutoff"),
            ]
        )
    ]
    _apply_reconciliation_classifications(items, {})
    # A card must never say "no action required" over a batch needing a JE.
    assert items[0]["classification"] == "missing_je"


def test_item_without_matches_keeps_todays_behaviour() -> None:
    """PR-B must not disturb any existing card."""
    items = [_item(hints={"is_processor_fee_gap": True})]
    _apply_reconciliation_classifications(items, {})
    assert items[0]["classification"] == "structural_explained"

    items = [_item(matches=None, hints={"is_customer_deposit": True})]
    _apply_reconciliation_classifications(items, {})
    assert items[0]["classification"] == "timing_cutoff"


def test_coverage_still_wins_over_matches() -> None:
    """A coverage card has no supporting file, so it cannot have real matches."""
    items = [_item(card_kind="coverage", matches=[_match("missing_je")])]
    _apply_reconciliation_classifications(items, {})
    assert items[0]["classification"] is None
    assert items[0]["card_kind"] == "coverage"


def test_residue_helper_ignores_unclassified_matches() -> None:
    assert _residue_from_matches([_match(None)]) is None
    assert _residue_from_matches(None) is None
    assert _residue_from_matches([]) is None


def test_residue_accepts_model_objects_not_only_dicts() -> None:
    model = BatchMatch(**_match("stale_reference"))
    assert _residue_from_matches([model]) == "stale_reference"


# ---------------------------------------------------------------------------
# Guardrail wiring — golden rule end to end
# ---------------------------------------------------------------------------


def _recon_values_for(items: list[dict]) -> list[float]:
    """Mirror of the interpreter's reference-building loop, for assertion."""
    values: list[float] = []
    for item in items:
        for field in ("gl_amount", "non_gl_total", "delta"):
            v = item.get(field)
            if v is not None:
                values.extend([float(v), float(abs(v))])
        hints = item.get("hints") or {}
        if isinstance(hints, dict) and hints.get("implied_monthly") is not None:
            values.extend(
                [float(hints["implied_monthly"]), float(abs(hints["implied_monthly"]))]
            )
        for match in item.get("matches") or []:
            for money_field in ("gross", "fee", "net", "gl_amount"):
                v = match.get(money_field)
                if v is not None:
                    values.extend([float(v), float(abs(v))])
            if match.get("candidate_count") is not None:
                values.append(float(match["candidate_count"]))
        for count_field in (
            "unmatched_count",
            "unmatched_processor_count",
            "unmatched_bank_count",
        ):
            v = item.get(count_field)
            if v is not None:
                values.append(float(v))
        for src in item.get("sources", []):
            values.append(float(src.get("amount", 0)))
    return values


@pytest.mark.parametrize("number", [1000.0, 45.0, 955.0])
def test_matcher_numbers_pass_the_guardrail(number) -> None:
    """Golden rule: Claude may copy gross/fee/net only because pandas put them
    in the verified reference pool first."""
    items = [_item(matches=[_match("structural_explained")], unmatched_bank_count=1)]
    passed, msg = verify_guardrail(
        {"numbers_used": [number], "narrative": f"Amount {number:,.2f} observed."},
        {"accounts": {"Undeposited Funds": {"current": 1000.0}}},
        reconciliation_values=_recon_values_for(items),
        strict=True,
    )
    assert passed is True, msg


def test_candidate_count_and_unmatched_count_are_verified() -> None:
    items = [
        _item(
            matches=[_match("stale_reference", candidate_count=2)],
            unmatched_bank_count=1,
        )
    ]
    values = _recon_values_for(items)
    assert 2.0 in values
    assert 1.0 in values


def test_fee_pct_is_never_a_reference_value() -> None:
    """E.1: a percentage must not enter the money pool — that was the bug the
    guardrail fix removed."""
    items = [_item(matches=[_match("structural_explained")])]
    values = _recon_values_for(items)
    assert 0.045 not in values  # fee 45 / gross 1000
    assert 4.5 not in values


def test_invented_matcher_number_still_fails_the_guardrail() -> None:
    items = [_item(matches=[_match("structural_explained")])]
    passed, msg = verify_guardrail(
        {"numbers_used": [1234.56], "narrative": "Amount 1,234.56 observed."},
        {"accounts": {"Undeposited Funds": {"current": 1000.0}}},
        reconciliation_values=_recon_values_for(items),
        strict=True,
    )
    assert passed is False
    assert "Mismatch" in msg
