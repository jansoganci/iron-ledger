"""Prove same-item 12× annual-prepayment hints — pandas only, isolated fixture."""

from __future__ import annotations

from pathlib import Path

from backend.agents.interpreter import (
    _apply_reconciliation_classifications,
    _classify_from_hints,
)
from backend.tools.hint_computer import compute_hints
from tests.tools.annual_prepayment_fixture import (
    ANNUAL_GL,
    ANNUAL_MONTHLY,
    IMPLIED_MONTHLY,
    PERIOD,
    SENTINEL_DELTA,
    SENTINEL_GL,
    SENTINEL_PAYROLL_TAXES,
    SENTINEL_RENT,
    SENTINEL_SOURCE,
    annual_consolidated,
    annual_item,
    annual_raw_dfs,
    annual_source_is_lump_item,
    gl_only_software_item,
    sentinel_pnl_with_rent_and_payroll_taxes,
    sentinel_raw_dfs,
    sentinel_service_revenue_item,
)
from tests.tools.deposit_vs_fee_fixture import (
    deposit_consolidated,
    deposit_item,
    deposit_raw_dfs,
    fee_consolidated,
    fee_item,
    fee_raw_dfs,
)

PROMPT = Path("backend/prompts/narrative_prompt.txt").read_text()


def test_annual_fixture_is_exactly_12x() -> None:
    assert ANNUAL_GL / ANNUAL_MONTHLY == 12.0
    assert IMPLIED_MONTHLY == 1_100.0


def test_annual_prepayment_hint_fires_on_same_account() -> None:
    hints = compute_hints(
        annual_item(), annual_consolidated(), PERIOD, annual_raw_dfs()
    )
    assert hints.looks_like_annual_prepayment is True
    assert hints.delta_matches_known_vendor is True  # alias
    assert hints.implied_monthly == IMPLIED_MONTHLY
    assert hints.is_customer_deposit is False
    assert hints.is_processor_fee_gap is False
    assert hints.is_gl_only is False
    assert hints.is_source_only is False


def test_annual_hint_fires_when_source_holds_the_lump() -> None:
    item = annual_source_is_lump_item()
    hints = compute_hints(item, annual_consolidated(), PERIOD, annual_raw_dfs())
    assert hints.looks_like_annual_prepayment is True
    assert hints.implied_monthly == IMPLIED_MONTHLY


def test_sentinel_285_is_not_annual_prepayment() -> None:
    """Regression: Δ$285 × 12 must not match Rent / Payroll Taxes.

    Retired rule: 285 × 12 = 3420, vs Payroll Taxes 3675 (7.5%) and Rent 3200
    (6.4%), both inside ±10%. Same-item 12× is 3825/3540 ≈ 1.08, not 12.
    """
    assert abs(SENTINEL_DELTA) == 285.0
    old_annual = abs(SENTINEL_DELTA) * 12  # 3420 — must not be used
    assert abs(SENTINEL_PAYROLL_TAXES - old_annual) / old_annual <= 0.10
    assert abs(SENTINEL_RENT - old_annual) / old_annual <= 0.10
    assert not (10.8 <= SENTINEL_SOURCE / SENTINEL_GL <= 13.2)
    assert not (10.8 <= SENTINEL_GL / SENTINEL_SOURCE <= 13.2)

    hints = compute_hints(
        sentinel_service_revenue_item(),
        sentinel_pnl_with_rent_and_payroll_taxes(),
        PERIOD,
        sentinel_raw_dfs(),
    )
    assert hints.looks_like_annual_prepayment is False
    assert hints.delta_matches_known_vendor is False
    assert hints.implied_monthly is None
    assert hints.is_gl_only is False
    assert hints.is_source_only is False
    assert _classify_from_hints(hints.model_dump()) == "stale_reference"


def test_gl_only_software_is_not_annual_prepayment() -> None:
    item = gl_only_software_item()
    consol = annual_consolidated()
    raw = {"gl_export.xlsx": annual_raw_dfs()["gl_export.xlsx"]}
    hints = compute_hints(item, consol, PERIOD, raw)
    assert hints.is_gl_only is True
    assert hints.looks_like_annual_prepayment is False
    assert hints.implied_monthly is None


def test_deposit_is_not_annual_prepayment() -> None:
    hints = compute_hints(
        deposit_item(), deposit_consolidated(), PERIOD, deposit_raw_dfs()
    )
    assert hints.is_customer_deposit is True
    assert hints.looks_like_annual_prepayment is False
    assert hints.implied_monthly is None
    assert _classify_from_hints(hints.model_dump()) == "timing_cutoff"


def test_fee_is_not_annual_prepayment() -> None:
    hints = compute_hints(fee_item(), fee_consolidated(), PERIOD, fee_raw_dfs())
    assert hints.is_processor_fee_gap is True
    assert hints.looks_like_annual_prepayment is False
    assert _classify_from_hints(hints.model_dump()) == "structural_explained"


def test_annual_classifies_as_accrual_mismatch() -> None:
    hints = compute_hints(
        annual_item(), annual_consolidated(), PERIOD, annual_raw_dfs()
    )
    assert _classify_from_hints(hints.model_dump()) == "accrual_mismatch"


def test_merge_forces_accrual_when_claude_says_stale_reference() -> None:
    hints = compute_hints(
        annual_item(), annual_consolidated(), PERIOD, annual_raw_dfs()
    )
    items = [
        {
            "account": "Software Subscriptions",
            "card_kind": "exception",
            "hints": hints.model_dump(),
            "classification": None,
        }
    ]
    _apply_reconciliation_classifications(
        items, {"Software Subscriptions": "stale_reference"}
    )
    assert items[0]["classification"] == "accrual_mismatch"


def test_deposit_wins_if_both_hints_are_set() -> None:
    """Belt-and-suspenders: deposit speech act outranks prepaid-asset."""
    assert (
        _classify_from_hints(
            {
                "is_customer_deposit": True,
                "looks_like_annual_prepayment": True,
            }
        )
        == "timing_cutoff"
    )
    items = [
        {
            "account": "Installation Revenue",
            "card_kind": "exception",
            "hints": {
                "is_customer_deposit": True,
                "looks_like_annual_prepayment": True,
            },
            "classification": None,
        }
    ]
    _apply_reconciliation_classifications(
        items, {"Installation Revenue": "accrual_mismatch"}
    )
    assert items[0]["classification"] == "timing_cutoff"


def test_fee_wins_if_both_hints_are_set() -> None:
    assert (
        _classify_from_hints(
            {
                "is_processor_fee_gap": True,
                "looks_like_annual_prepayment": True,
            }
        )
        == "structural_explained"
    )


def test_prompt_uses_pandas_implied_monthly_not_division() -> None:
    assert "looks_like_annual_prepayment" in PROMPT
    assert "implied_monthly" in PROMPT
    assert "Never divide an amount by 12" in PROMPT
    accrual_block = PROMPT.split("5. accrual_mismatch")[1].split("6. structural")[0]
    assert "prepaid asset" in accrual_block
    assert "unearned revenue" in accrual_block
    assert "do not divide" in accrual_block.lower() or "Do not divide" in accrual_block
