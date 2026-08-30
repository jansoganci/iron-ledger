"""Unit tests for hint_computer.py.

Tests are pure pandas — no DB, no LLM. Each test targets one hint function
in isolation using hand-crafted DataFrames that mirror the Sentinel Secure
demo scenario.
"""

from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from backend.domain.contracts import ReconciliationItem, ReconciliationSource
from backend.tools.hint_computer import (
    _crosses_period_boundary,
    _is_gl_only,
    _is_round_fraction,
    _is_source_only,
    _period_end,
    _similar_amount_in_other_account,
    compute_hints,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

PERIOD = date(2026, 3, 1)
PERIOD_END = date(2026, 3, 31)


def _item(
    account: str = "Payroll",
    category: str = "OPEX",
    gl_amount: float | None = 43500.0,
    non_gl_total: float = 44200.0,
    delta: float = 700.0,
    sources: list[ReconciliationSource] | None = None,
) -> ReconciliationItem:
    if sources is None:
        sources = [
            ReconciliationSource(
                source_file="gl_export.xlsx", amount=gl_amount or 0, row_count=1
            ),
            ReconciliationSource(
                source_file="payroll_march.xlsx", amount=non_gl_total, row_count=8
            ),
        ]
    return ReconciliationItem(
        account=account,
        category=category,
        sources=sources,
        gl_amount=gl_amount,
        non_gl_total=non_gl_total,
        delta=delta,
        delta_pct=round(delta / gl_amount, 4) if gl_amount else None,
        severity="low",
    )


def _consolidated_df(*rows: tuple[str, str, float]) -> pd.DataFrame:
    """Build a minimal consolidated DataFrame from (account, category, amount) tuples."""
    return pd.DataFrame(
        [{"account": a, "category": c, "amount": amt} for a, c, amt in rows]
    )


# ---------------------------------------------------------------------------
# _period_end
# ---------------------------------------------------------------------------


def test_period_end_march() -> None:
    assert _period_end(date(2026, 3, 1)) == date(2026, 3, 31)


def test_period_end_february_leap_year() -> None:
    assert _period_end(date(2024, 2, 1)) == date(2024, 2, 29)


def test_period_end_february_non_leap() -> None:
    assert _period_end(date(2025, 2, 1)) == date(2025, 2, 28)


# ---------------------------------------------------------------------------
# _crosses_period_boundary
# ---------------------------------------------------------------------------


def test_crosses_period_boundary_true_when_future_date_present() -> None:
    """Installation payments file with April due dates → True."""
    df = pd.DataFrame(
        {
            "account": ["Installation Revenue"] * 3,
            "amount": [4000.0, 4000.0, 3000.0],
            "date": [date(2026, 3, 18), date(2026, 3, 6), date(2026, 3, 28)],
            "Balance Due Date": ["2026-04-15", None, "2026-04-28"],
        }
    )
    result = _crosses_period_boundary(
        {"installation_payments_mar_2026.xlsx"},
        {"installation_payments_mar_2026.xlsx": df},
        PERIOD_END,
    )
    assert result is True


def test_crosses_period_boundary_false_when_all_dates_in_period() -> None:
    df = pd.DataFrame(
        {
            "account": ["Payroll"],
            "amount": [44200.0],
            "date": [date(2026, 3, 31)],
        }
    )
    result = _crosses_period_boundary(
        {"payroll_march.xlsx"},
        {"payroll_march.xlsx": df},
        PERIOD_END,
    )
    assert result is False


def test_crosses_period_boundary_false_when_file_not_in_raw_dfs() -> None:
    """If the source file isn't in source_raw_dfs, hint is conservatively False."""
    result = _crosses_period_boundary(
        {"missing_file.xlsx"},
        {},
        PERIOD_END,
    )
    assert result is False


def test_last_billed_april_on_contracts_file_is_not_cutoff() -> None:
    """Sentinel roster: Last Billed 1 Apr must not steal stale_reference."""
    df = pd.DataFrame(
        {
            "Account": ["Service Revenue"] * 2,
            "Last Billed": [date(2026, 3, 1), date(2026, 4, 1)],
            "Start Date": [date(2024, 6, 1), date(2025, 1, 1)],
        }
    )
    result = _crosses_period_boundary(
        {"sentinel_contracts_mar_2026.xlsx"},
        {"sentinel_contracts_mar_2026.xlsx": df},
        PERIOD_END,
    )
    assert result is False


def test_last_billed_april_blocked_even_without_contracts_filename() -> None:
    df = pd.DataFrame({"Last Billed": [date(2026, 4, 1)]})
    result = _crosses_period_boundary(
        {"rmr_export.xlsx"},
        {"rmr_export.xlsx": df},
        PERIOD_END,
    )
    assert result is False


def test_feb_28_renewal_does_not_fire() -> None:
    df = pd.DataFrame({"Renewal Date": [date(2026, 2, 28)]})
    result = _crosses_period_boundary(
        {"customers.xlsx"},
        {"customers.xlsx": df},
        PERIOD_END,
    )
    assert result is False


def test_invoice_date_after_month_end_is_cutoff() -> None:
    df = pd.DataFrame({"Invoice Date": [date(2026, 3, 12), date(2026, 4, 3)]})
    result = _crosses_period_boundary(
        {"sentinel_supplier_invoices_mar_2026.xlsx"},
        {"sentinel_supplier_invoices_mar_2026.xlsx": df},
        PERIOD_END,
    )
    assert result is True


def test_payout_date_after_month_end_is_cutoff() -> None:
    df = pd.DataFrame({"Payout Date": [date(2026, 4, 2)]})
    result = _crosses_period_boundary(
        {"vandelay_shopify_payouts_mar_2026.xlsx"},
        {"vandelay_shopify_payouts_mar_2026.xlsx": df},
        PERIOD_END,
    )
    assert result is True


def test_payout_period_text_is_not_cutoff() -> None:
    """Harvest-style 'Mar 1-14' must not coerce into a future cutoff date."""
    df = pd.DataFrame({"Payout Period": ["Mar 1-14", "Mar 15-31"]})
    result = _crosses_period_boundary(
        {"harvest_delivery_settlements_mar_2026.xlsx"},
        {"harvest_delivery_settlements_mar_2026.xlsx": df},
        PERIOD_END,
    )
    assert result is False


def test_contracts_file_column_named_date_is_skipped() -> None:
    df = pd.DataFrame({"date": [date(2026, 4, 1)]})
    result = _crosses_period_boundary(
        {"customer_roster.xlsx"},
        {"customer_roster.xlsx": df},
        PERIOD_END,
    )
    assert result is False


# ---------------------------------------------------------------------------
# _is_round_fraction
# ---------------------------------------------------------------------------


def test_is_round_fraction_true_at_exactly_half() -> None:
    item = _item(gl_amount=8000.0, non_gl_total=4000.0, delta=-4000.0)
    assert _is_round_fraction(item) is True


def test_is_round_fraction_true_within_tolerance() -> None:
    # 4100 / 8000 = 0.5125, within ±5% of 0.5
    item = _item(gl_amount=8000.0, non_gl_total=4100.0, delta=-3900.0)
    assert _is_round_fraction(item) is True


def test_is_round_fraction_false_installation_demo() -> None:
    # 11000 / 15000 = 0.733 — NOT round fraction → relies on period boundary
    item = _item(
        account="Installation Revenue",
        gl_amount=15000.0,
        non_gl_total=11000.0,
        delta=-4000.0,
    )
    assert _is_round_fraction(item) is False


def test_is_round_fraction_false_when_no_gl_amount() -> None:
    item = _item(gl_amount=None, non_gl_total=1700.0, delta=1700.0)
    assert _is_round_fraction(item) is False


# ---------------------------------------------------------------------------
# _similar_amount_in_other_account
# ---------------------------------------------------------------------------


def test_similar_amount_matches_contractors_line() -> None:
    """$700 Payroll delta matches $700 Contractors line → categorical misclassification."""
    item = _item(account="Payroll", delta=700.0)
    df = _consolidated_df(
        ("Payroll", "OPEX", 43500.0),
        ("Contractors", "OPEX", 700.0),  # the miscoded bonus
        ("Service Revenue", "REVENUE", 3540.0),
    )
    assert _similar_amount_in_other_account(item, df) is True


def test_similar_amount_no_match_when_no_similar_account() -> None:
    item = _item(account="Payroll", delta=700.0)
    df = _consolidated_df(
        ("Payroll", "OPEX", 43500.0),
        ("Service Revenue", "REVENUE", 3540.0),
        ("Equipment COGS", "COGS", 36100.0),
    )
    assert _similar_amount_in_other_account(item, df) is False


def test_similar_amount_ignores_same_account() -> None:
    """The item's own account should not match itself."""
    item = _item(account="Payroll", delta=43500.0)
    df = _consolidated_df(
        ("Payroll", "OPEX", 43500.0),
    )
    assert _similar_amount_in_other_account(item, df) is False


def test_similar_amount_false_when_delta_trivial() -> None:
    item = _item(delta=0.0)
    df = _consolidated_df(("Payroll", "OPEX", 43500.0))
    assert _similar_amount_in_other_account(item, df) is False


# ---------------------------------------------------------------------------
# _is_source_only / _is_gl_only
# ---------------------------------------------------------------------------


def test_is_source_only_true_when_no_gl_source() -> None:
    """CableMax invoice in supplier file only, not in GL."""
    item = _item(
        account="Equipment COGS",
        sources=[
            ReconciliationSource(
                source_file="supplier_invoices.xlsx", amount=1700.0, row_count=1
            )
        ],
        gl_amount=None,
    )
    assert _is_source_only(item) is True
    assert _is_gl_only(item) is False


def test_is_gl_only_true_when_only_gl_contributes() -> None:
    """Contractors line appears only in GL, no dept file lists it."""
    item = _item(
        account="Contractors",
        sources=[
            ReconciliationSource(
                source_file="gl_export.xlsx", amount=700.0, row_count=1
            )
        ],
        gl_amount=700.0,
        non_gl_total=0.0,
        delta=-700.0,
    )
    assert _is_gl_only(item) is True
    assert _is_source_only(item) is False


def test_neither_source_only_nor_gl_only_when_both_present() -> None:
    item = _item()  # default has both gl_export + payroll sources
    assert _is_source_only(item) is False
    assert _is_gl_only(item) is False


# ---------------------------------------------------------------------------
# looks_like_annual_prepayment — other-account hunt is retired
# ---------------------------------------------------------------------------


def test_other_account_12x_is_not_annual_prepayment() -> None:
    """Retired rule: delta=$1100 × 12 matching a *different* HubSpot row.

    Same-item 12× is required. Payroll 43500 vs 44200 is not ~12×.
    """
    item = _item(
        account="SaaS Subscriptions",
        delta=1100.0,
        gl_amount=6700.0,
        non_gl_total=7800.0,
    )
    df = _consolidated_df(
        ("SaaS Subscriptions", "OPEX", 6700.0),
        ("HubSpot Annual Invoice", "OPEX", 13200.0),
    )
    raw = {
        "gl_export.xlsx": pd.DataFrame(
            {"account": ["SaaS Subscriptions"], "amount": [6700.0]}
        ),
        "payroll_march.xlsx": pd.DataFrame(
            {"account": ["SaaS Subscriptions"], "amount": [7800.0]}
        ),
    }
    hints = compute_hints(item, df, PERIOD, raw)
    assert hints.looks_like_annual_prepayment is False
    assert hints.implied_monthly is None


# ---------------------------------------------------------------------------
# compute_hints — integration (all hints for one item)
# ---------------------------------------------------------------------------


def test_compute_hints_payroll_misclassification() -> None:
    """Full hint set for Payroll $700 delta — should flag similar_amount_in_other_account."""
    item = _item(account="Payroll", delta=700.0)
    df = _consolidated_df(
        ("Payroll", "OPEX", 43500.0),
        ("Contractors", "OPEX", 700.0),
        ("Service Revenue", "REVENUE", 3540.0),
    )
    raw_dfs = {
        "gl_export.xlsx": pd.DataFrame(
            {"account": ["Payroll"], "amount": [43500.0], "date": [date(2026, 3, 31)]}
        ),
        "payroll_march.xlsx": pd.DataFrame(
            {"account": ["Payroll"], "amount": [44200.0], "date": [date(2026, 3, 28)]}
        ),
    }
    hints = compute_hints(item, df, PERIOD, raw_dfs)
    assert hints.similar_amount_in_other_account is True
    assert hints.crosses_period_boundary is False
    assert hints.is_round_fraction is False
    assert hints.is_gl_only is False
    assert hints.is_source_only is False


def test_compute_hints_installation_timing() -> None:
    """Full hint set for Installation Revenue $4,000 gap — should flag period boundary."""
    item = _item(
        account="Installation Revenue",
        category="REVENUE",
        gl_amount=15000.0,
        non_gl_total=11000.0,
        delta=-4000.0,
        sources=[
            ReconciliationSource(
                source_file="gl_export.xlsx", amount=15000.0, row_count=1
            ),
            ReconciliationSource(
                source_file="installation_payments_mar_2026.xlsx",
                amount=11000.0,
                row_count=3,
            ),
        ],
    )
    df = _consolidated_df(
        ("Installation Revenue", "REVENUE", 15000.0),
        ("Service Revenue", "REVENUE", 3540.0),
    )
    install_df = pd.DataFrame(
        {
            "account": ["Installation Revenue"] * 3,
            "amount": [4000.0, 4000.0, 3000.0],
            "date": [date(2026, 3, 18), date(2026, 3, 6), date(2026, 3, 28)],
            "Balance Due Date": ["2026-04-15", None, "2026-04-28"],
        }
    )
    raw_dfs = {
        "gl_export.xlsx": pd.DataFrame(
            {
                "account": ["Installation Revenue"],
                "amount": [15000.0],
                "date": [date(2026, 3, 1)],
            }
        ),
        "installation_payments_mar_2026.xlsx": install_df,
    }
    hints = compute_hints(item, df, PERIOD, raw_dfs)
    assert hints.crosses_period_boundary is True
    assert hints.is_round_fraction is False  # 11000/15000 = 0.73, not 0.5
    assert hints.is_customer_deposit is False
    assert hints.is_processor_fee_gap is False
    assert hints.similar_amount_in_other_account is False


def test_compute_hints_never_raises() -> None:
    """compute_hints must return a default ReconciliationHints on any error."""
    item = _item()
    # Pass a broken consolidated_df to trigger an exception internally
    bad_df = pd.DataFrame({"wrong_column": [1, 2, 3]})
    hints = compute_hints(item, bad_df, PERIOD, {})
    assert hints is not None  # returned default, did not raise
