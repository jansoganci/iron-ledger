"""Unit tests for comparison.py — Track 4 tiered materiality thresholds."""

from __future__ import annotations

import pytest

from backend.agents.comparison import calculate_variance


# ---------------------------------------------------------------------------
# Backward-compat: no category param defaults to Tier 1 behaviour
# ---------------------------------------------------------------------------


def test_no_category_defaults_to_tier1_thresholds() -> None:
    # $60K delta, 20% — clears both Tier 1 gates ($50K and 10%)
    result = calculate_variance(
        current=360_000.0, historical_avg=300_000.0, history_count=3
    )
    assert result["flag"] is True


def test_no_category_below_tier1_dollar_gate_not_flagged() -> None:
    # $40K delta, 40% — clears pct gate but NOT dollar gate ($50K)
    result = calculate_variance(
        current=140_000.0, historical_avg=100_000.0, history_count=3
    )
    assert result["flag"] is False


# ---------------------------------------------------------------------------
# Tier 1 (non-sensitive categories): $50K AND 10% gates
# ---------------------------------------------------------------------------


def test_tier1_both_gates_must_clear() -> None:
    # $60K delta, 20% — both gates met
    result = calculate_variance(
        current=360_000.0, historical_avg=300_000.0, history_count=3, category="OPEX"
    )
    assert result["flag"] is True


def test_tier1_only_dollar_gate_not_flagged() -> None:
    # $60K delta, 2% — dollar gate met but pct gate (10%) NOT met
    result = calculate_variance(
        current=3_060_000.0,
        historical_avg=3_000_000.0,
        history_count=3,
        category="OPEX",
    )
    assert result["flag"] is False


def test_tier1_only_pct_gate_not_flagged() -> None:
    # $20K delta, 25% — pct gate met but dollar gate ($50K) NOT met
    result = calculate_variance(
        current=100_000.0, historical_avg=80_000.0, history_count=3, category="G&A"
    )
    assert result["flag"] is False


# ---------------------------------------------------------------------------
# Tier 2 (REVENUE / PAYROLL / DEFERRED_REVENUE): $10K AND 3% gates
# ---------------------------------------------------------------------------


def test_tier2_revenue_fires_at_lower_gates() -> None:
    # $15K delta, 5% — clears Tier 2 gates but NOT Tier 1 ($50K)
    result = calculate_variance(
        current=315_000.0, historical_avg=300_000.0, history_count=3, category="REVENUE"
    )
    assert result["flag"] is True


def test_tier2_payroll_fires_at_lower_gates() -> None:
    # $12K delta, 4% — clears Tier 2 gates
    result = calculate_variance(
        current=312_000.0, historical_avg=300_000.0, history_count=3, category="PAYROLL"
    )
    assert result["flag"] is True


def test_tier2_deferred_revenue_fires_at_lower_gates() -> None:
    # $11K delta, 3.5%
    result = calculate_variance(
        current=325_000.0,
        historical_avg=314_000.0,
        history_count=3,
        category="DEFERRED_REVENUE",
    )
    assert result["flag"] is True


def test_tier2_below_dollar_gate_not_flagged() -> None:
    # $8K delta, 10% — pct gate met but dollar gate ($10K) NOT met
    result = calculate_variance(
        current=88_000.0, historical_avg=80_000.0, history_count=3, category="REVENUE"
    )
    assert result["flag"] is False


def test_tier2_below_pct_gate_not_flagged() -> None:
    # $12K delta, 1% — dollar gate met but pct gate (3%) NOT met
    result = calculate_variance(
        current=1_212_000.0,
        historical_avg=1_200_000.0,
        history_count=3,
        category="PAYROLL",
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
    # An unknown category string should fall through to Tier 1 gates
    result = calculate_variance(
        current=120_000.0, historical_avg=100_000.0, history_count=3, category="MYSTERY"
    )
    # $20K delta, 20% — clears Tier 1 pct (10%) but NOT dollar ($50K) → no flag
    assert result["flag"] is False
