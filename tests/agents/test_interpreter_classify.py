"""Unit tests for interpreter classification merge — no LLM."""

from __future__ import annotations

from backend.agents.interpreter import (
    _apply_reconciliation_classifications,
    _classify_from_hints,
    _is_coverage_item,
)


def test_classify_gl_only_is_not_missing_je() -> None:
    assert _classify_from_hints({"is_gl_only": True}) is None


def test_classify_source_only_is_missing_je() -> None:
    assert _classify_from_hints({"is_source_only": True}) == "missing_je"


def test_is_coverage_from_card_kind() -> None:
    assert _is_coverage_item({"card_kind": "coverage", "hints": {}}) is True


def test_is_coverage_from_gl_only_hint() -> None:
    assert _is_coverage_item({"hints": {"is_gl_only": True}}) is True


def test_apply_classifications_ignores_claude_on_coverage() -> None:
    items = [
        {
            "account": "Rent",
            "card_kind": "coverage",
            "hints": {"is_gl_only": True},
            "classification": None,
        },
        {
            "account": "Bonus",
            "card_kind": "exception",
            "hints": {"is_source_only": True},
            "classification": None,
        },
    ]
    _apply_reconciliation_classifications(
        items, {"Rent": "missing_je", "Bonus": "missing_je"}
    )
    assert items[0]["classification"] is None
    assert items[0]["card_kind"] == "coverage"
    assert items[1]["classification"] == "missing_je"


def test_round_fraction_is_timing_cutoff_not_accrual() -> None:
    assert (
        _classify_from_hints({"is_round_fraction": True, "is_customer_deposit": True})
        == "timing_cutoff"
    )


def test_fee_hint_beats_period_boundary() -> None:
    assert (
        _classify_from_hints(
            {
                "is_processor_fee_gap": True,
                "crosses_period_boundary": True,
            }
        )
        == "structural_explained"
    )


def test_vendor_annual_hint_is_accrual() -> None:
    assert (
        _classify_from_hints({"looks_like_annual_prepayment": True})
        == "accrual_mismatch"
    )


def test_vendor_annual_alias_still_classifies() -> None:
    assert (
        _classify_from_hints({"delta_matches_known_vendor": True}) == "accrual_mismatch"
    )


def test_annual_outranks_cutoff_in_fallback() -> None:
    assert (
        _classify_from_hints(
            {
                "looks_like_annual_prepayment": True,
                "crosses_period_boundary": True,
            }
        )
        == "accrual_mismatch"
    )
