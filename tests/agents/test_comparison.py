"""Unit tests for comparison.py — scaled flux gates, payroll tag, recurrence."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock

from backend.agents.comparison import (
    ComparisonAgent,
    _TIER1_DOLLAR,
    _TIER2_DOLLAR,
    _gates_from_band,
    calculate_variance,
)
from backend.domain.entities import MonthlyEntry


# ---------------------------------------------------------------------------
# Fail-safe: omitted gates = today's $50k / $10k
# ---------------------------------------------------------------------------


def test_no_category_defaults_to_tier1_thresholds() -> None:
    # $60K delta, 20% — fail-safe / omitted gates = $50k Tier 1
    result = calculate_variance(
        current=360_000.0, historical_avg=300_000.0, history_count=3
    )
    assert result["flag"] is True


def test_no_category_below_tier1_dollar_gate_not_flagged() -> None:
    # $40K delta, 40% — clears pct gate but NOT fail-safe dollar gate ($50K)
    result = calculate_variance(
        current=140_000.0, historical_avg=100_000.0, history_count=3
    )
    assert result["flag"] is False


# ---------------------------------------------------------------------------
# Fail-safe Tier 1 (non-REVENUE, non-payroll name): $50K AND 10%
# ---------------------------------------------------------------------------


def test_tier1_both_gates_must_clear() -> None:
    result = calculate_variance(
        current=360_000.0, historical_avg=300_000.0, history_count=3, category="OPEX"
    )
    assert result["flag"] is True


def test_tier1_only_dollar_gate_not_flagged() -> None:
    result = calculate_variance(
        current=3_060_000.0,
        historical_avg=3_000_000.0,
        history_count=3,
        category="OPEX",
    )
    assert result["flag"] is False


def test_tier1_only_pct_gate_not_flagged() -> None:
    result = calculate_variance(
        current=100_000.0, historical_avg=80_000.0, history_count=3, category="G&A"
    )
    assert result["flag"] is False


# ---------------------------------------------------------------------------
# Fail-safe Tier 2: REVENUE or payroll name, omitted gates = $10k AND 3%
# ---------------------------------------------------------------------------


def test_tier2_revenue_fires_at_lower_gates() -> None:
    result = calculate_variance(
        current=315_000.0, historical_avg=300_000.0, history_count=3, category="REVENUE"
    )
    assert result["flag"] is True


def test_tier2_payroll_fires_at_lower_gates() -> None:
    # Category PAYROLL is not a live gate — name tag is.
    result = calculate_variance(
        current=312_000.0,
        historical_avg=300_000.0,
        history_count=3,
        category="G&A",
        account_name="Salaries & Wages",
    )
    assert result["flag"] is True


def test_deferred_revenue_category_is_not_tier2() -> None:
    # $11k / 3.5% — would have been Tier 2; category string is not seeded.
    result = calculate_variance(
        current=325_000.0,
        historical_avg=314_000.0,
        history_count=3,
        category="DEFERRED_REVENUE",
    )
    assert result["flag"] is False


def test_tier2_below_dollar_gate_not_flagged() -> None:
    result = calculate_variance(
        current=88_000.0, historical_avg=80_000.0, history_count=3, category="REVENUE"
    )
    assert result["flag"] is False


def test_tier2_below_pct_gate_not_flagged() -> None:
    result = calculate_variance(
        current=1_212_000.0,
        historical_avg=1_200_000.0,
        history_count=3,
        category="G&A",
        account_name="Payroll",
    )
    assert result["flag"] is False


# ---------------------------------------------------------------------------
# Severity and variance_pct fields are unaffected by tiering
# ---------------------------------------------------------------------------


def test_severity_high_above_30_pct() -> None:
    result = calculate_variance(
        current=200_000.0, historical_avg=100_000.0, history_count=3, category="OPEX"
    )
    assert result["severity"] == "high"
    assert result["variance_pct"] == 100.0


def test_severity_medium_between_15_and_30_pct() -> None:
    result = calculate_variance(
        current=120_000.0, historical_avg=100_000.0, history_count=3
    )
    assert result["severity"] == "medium"


def test_severity_low_under_15_pct() -> None:
    result = calculate_variance(
        current=110_000.0, historical_avg=100_000.0, history_count=3
    )
    assert result["severity"] == "low"


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


def test_no_history_returns_no_history_sentinel() -> None:
    result = calculate_variance(current=100_000.0, historical_avg=0.0, history_count=0)
    assert result["flag"] is False
    assert result["severity"] == "no_history"
    assert result["variance_pct"] is None


def test_unknown_category_treated_as_tier1() -> None:
    result = calculate_variance(
        current=120_000.0, historical_avg=100_000.0, history_count=3, category="MYSTERY"
    )
    assert result["flag"] is False


# ---------------------------------------------------------------------------
# _gates_from_band
# ---------------------------------------------------------------------------


def test_gates_from_band_null_equals_legacy_constants() -> None:
    assert _gates_from_band(None) == (_TIER1_DOLLAR, _TIER2_DOLLAR)


def test_gates_from_band_500k_plus_equals_legacy_constants() -> None:
    assert _gates_from_band("500k_plus") == (_TIER1_DOLLAR, _TIER2_DOLLAR)


def test_gates_from_band_under_100k() -> None:
    assert _gates_from_band("under_100k") == (1_250.0, 250.0)


def test_gates_from_band_100k_250k() -> None:
    assert _gates_from_band("100k_250k") == (4_375.0, 875.0)


def test_gates_from_band_250k_500k() -> None:
    assert _gates_from_band("250k_500k") == (9_375.0, 1_875.0)


def test_unknown_band_string_fail_safe() -> None:
    for junk in ("annual", "", "not_a_band"):
        assert _gates_from_band(junk) == (_TIER1_DOLLAR, _TIER2_DOLLAR)


def test_null_band_never_zero_floors() -> None:
    assert _gates_from_band(None) != (0.0, 0.0)
    assert _gates_from_band(None)[0] > 0
    assert _gates_from_band(None)[1] > 0


# ---------------------------------------------------------------------------
# ICP-scale cases (band 100k_250k → t1=$4,375 t2=$875)
# ---------------------------------------------------------------------------


_ICP_T1, _ICP_T2 = _gates_from_band("100k_250k")


def test_icp_100k_250k_salaries_flags() -> None:
    result = calculate_variance(
        current=43_500.0,
        historical_avg=38_000.0,
        history_count=3,
        category="G&A",
        account_name="Salaries & Wages",
        dollar_t1=_ICP_T1,
        dollar_t2=_ICP_T2,
    )
    assert result["flag"] is True


def test_icp_installation_revenue_flags() -> None:
    result = calculate_variance(
        current=15_000.0,
        historical_avg=10_000.0,
        history_count=3,
        category="REVENUE",
        account_name="Installation Revenue",
        dollar_t1=_ICP_T1,
        dollar_t2=_ICP_T2,
    )
    assert result["flag"] is True


def test_icp_rent_noise_not_flagged() -> None:
    result = calculate_variance(
        current=3_200.0,
        historical_avg=3_000.0,
        history_count=3,
        category="OPEX",
        account_name="Rent",
        dollar_t1=_ICP_T1,
        dollar_t2=_ICP_T2,
    )
    assert result["flag"] is False


def test_payroll_name_uses_tier2_of_band() -> None:
    t1, t2 = _gates_from_band("under_100k")
    result = calculate_variance(
        current=43_500.0,
        historical_avg=38_000.0,
        history_count=3,
        category="G&A",
        account_name="Salaries & Wages",
        dollar_t1=t1,
        dollar_t2=t2,
    )
    assert result["flag"] is True


def test_payroll_name_without_scale_still_misses_icp_noise() -> None:
    # Same $5.5k / 14.5% at leftover $10k t2 — PR #5 alone is not enough.
    result = calculate_variance(
        current=43_500.0,
        historical_avg=38_000.0,
        history_count=3,
        category="G&A",
        account_name="Salaries & Wages",
    )
    assert result["flag"] is False


def test_revenue_without_payroll_name_is_tier2() -> None:
    result = calculate_variance(
        current=15_000.0,
        historical_avg=10_000.0,
        history_count=3,
        category="REVENUE",
        account_name="Installation Revenue",
        dollar_t1=_ICP_T1,
        dollar_t2=_ICP_T2,
    )
    assert result["flag"] is True


def test_opex_non_payroll_uses_tier1_of_band() -> None:
    result_flag = calculate_variance(
        current=43_500.0,
        historical_avg=38_000.0,
        history_count=3,
        category="OPEX",
        account_name="Rent",
        dollar_t1=_ICP_T1,
        dollar_t2=_ICP_T2,
    )
    assert result_flag["flag"] is True  # $5,500 > $4,375 and 14.5% > 10%

    result_pct = calculate_variance(
        current=40_500.0,
        historical_avg=37_500.0,
        history_count=3,
        category="OPEX",
        account_name="Rent",
        dollar_t1=_ICP_T1,
        dollar_t2=_ICP_T2,
    )
    # $3,000 / 8% — dollar may clear scaled t1; pct 8% does not clear 10%
    assert result_pct["flag"] is False


# ---------------------------------------------------------------------------
# ComparisonAgent — recurring anomaly detection (not a Recurrence agent)
# ---------------------------------------------------------------------------

COMPANY_ID = "00000000-0000-0000-0000-000000000001"
ACCT_ID = "00000000-0000-0000-0000-000000000002"
PERIOD = date(2026, 3, 1)


def _make_entry(account_id: str, amount: float) -> MonthlyEntry:
    return MonthlyEntry(
        id="entry-1",
        company_id=COMPANY_ID,
        account_id=account_id,
        period=PERIOD,
        actual_amount=Decimal(str(amount)),
    )


def _make_history_entry(account_id: str, amount: float, period: date) -> MonthlyEntry:
    return MonthlyEntry(
        id="hist-1",
        company_id=COMPANY_ID,
        account_id=account_id,
        period=period,
        actual_amount=Decimal(str(amount)),
    )


def _make_agent(prior_flag_counts: dict[str, int]) -> ComparisonAgent:
    """Build a ComparisonAgent with all repo dependencies mocked."""
    entries_repo = MagicMock()
    anomalies_repo = MagicMock()
    runs_repo = MagicMock()
    accounts_repo = MagicMock()
    companies_repo = MagicMock()

    entries_repo.list_for_period.return_value = [_make_entry(ACCT_ID, 360_000.0)]
    entries_repo.list_history.return_value = [
        _make_history_entry(ACCT_ID, 300_000.0, date(2026, 1, 1)),
        _make_history_entry(ACCT_ID, 300_000.0, date(2026, 2, 1)),
    ]
    accounts_repo.get_accounts_by_id.return_value = {
        ACCT_ID: {"name": "Engineering Salaries", "category": "G&A"}
    }
    companies_repo.get_by_id.return_value = {"monthly_revenue_band": None}

    anomalies_repo.list_account_flag_counts_before.return_value = prior_flag_counts
    anomalies_repo.write_many.return_value = None
    runs_repo.get_by_id.return_value = {"status": "comparing"}
    runs_repo.update_status.return_value = None
    runs_repo.set_pandas_summary.return_value = None

    return ComparisonAgent(
        entries_repo,
        anomalies_repo,
        runs_repo,
        accounts_repo,
        companies_repo,
    )


def test_recurrence_suffix_appended_when_prior_count_is_2() -> None:
    agent = _make_agent({ACCT_ID: 2})
    agent.run("run-1", COMPANY_ID, PERIOD)

    written: list = agent._anomalies.write_many.call_args[0][0]
    assert len(written) == 1
    assert (
        "Flagged in 2 of the past 6 months — recurring pattern."
        in written[0].description
    )


def test_recurrence_suffix_appended_when_prior_count_exceeds_2() -> None:
    agent = _make_agent({ACCT_ID: 4})
    agent.run("run-1", COMPANY_ID, PERIOD)

    written: list = agent._anomalies.write_many.call_args[0][0]
    assert (
        "Flagged in 4 of the past 6 months — recurring pattern."
        in written[0].description
    )


def test_recurrence_suffix_not_appended_when_prior_count_is_1() -> None:
    agent = _make_agent({ACCT_ID: 1})
    agent.run("run-1", COMPANY_ID, PERIOD)

    written: list = agent._anomalies.write_many.call_args[0][0]
    assert "recurring pattern" not in written[0].description


def test_recurrence_suffix_not_appended_when_no_prior_flags() -> None:
    agent = _make_agent({})
    agent.run("run-1", COMPANY_ID, PERIOD)

    written: list = agent._anomalies.write_many.call_args[0][0]
    assert "recurring pattern" not in written[0].description


def test_list_account_flag_counts_called_once_not_per_entry() -> None:
    agent = _make_agent({})
    agent.run("run-1", COMPANY_ID, PERIOD)

    agent._anomalies.list_account_flag_counts_before.assert_called_once_with(
        COMPANY_ID, PERIOD, lookback_months=6
    )
    agent._companies.get_by_id.assert_called_once_with(COMPANY_ID)
