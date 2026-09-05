"""Item 4 — roster_counts.compute, the pandas counting module.

Covers R.1 (billed-in-period over Active rows only, null = not billed,
count_delta never negative) and R.2 (exact normalized "active"; no status
column emits nothing).
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from backend.tools.roster_counts import RosterCounts, compute

FIXTURE = Path(__file__).parent / "fixtures" / "kova_rmr_roster_mar_2026.csv"
PERIOD = date(2026, 3, 1)


def _roster() -> pd.DataFrame:
    df = pd.read_csv(FIXTURE, dtype={"status": "string"})
    df["_orig_row_index"] = range(len(df))
    return df


def _frame(rows: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame(rows)
    df["_orig_row_index"] = range(len(df))
    return df


# ---------------------------------------------------------------------------
# The Sentinel shape
# ---------------------------------------------------------------------------


def test_sentinel_shape_85_82_3() -> None:
    counts = compute(_roster(), PERIOD)
    assert counts == RosterCounts(
        n_active=85,
        n_billed_in_period=82,
        count_delta=3,
        fee_sum_active=3825.00,
        fee_sum_billed=3540.00,
        fee_gap=285.00,
    )


def test_fixture_has_shape_noise_that_is_not_counted() -> None:
    """Suspended / blank / cancelled rows exist and are excluded."""
    df = _roster()
    statuses = {str(s).strip().casefold() for s in df["status"].fillna("")}
    assert {"suspended", "cancelled", ""} <= statuses
    assert len(df) == 88  # 85 active + 3 noise rows
    assert compute(df, PERIOD).n_active == 85


# ---------------------------------------------------------------------------
# R.2 — what counts as Active
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("raw", ["Active", "active", "ACTIVE", "  Active  "])
def test_status_case_and_whitespace_insensitive(raw) -> None:
    counts = compute(
        _frame([{"status": raw, "monthly_fee": 10.0, "last_billed": "2026-03-05"}]),
        PERIOD,
    )
    assert counts.n_active == 1


@pytest.mark.parametrize(
    "raw",
    ["Suspended", "Pending", "On Hold", "Inactive", "Terminated", "Cancelled", ""],
)
def test_suspended_pending_onhold_are_not_active(raw) -> None:
    """Stretching "active" would invent revenue — only exact matches count."""
    counts = compute(
        _frame([{"status": raw, "monthly_fee": 10.0, "last_billed": "2026-03-05"}]),
        PERIOD,
    )
    assert counts.n_active == 0
    assert counts.count_delta == 0


def test_active_pending_cancel_undercounts_by_design() -> None:
    """Documented cost of R.2's exact match — pinned so it is a decision."""
    counts = compute(
        _frame(
            [
                {
                    "status": "Active - pending cancel",
                    "monthly_fee": 10.0,
                    "last_billed": "2026-03-05",
                }
            ]
        ),
        PERIOD,
    )
    assert counts.n_active == 0


def test_missing_status_column_emits_nothing() -> None:
    """R.2: never read a missing status column as "all active"."""
    assert (
        compute(_frame([{"monthly_fee": 10.0, "last_billed": "2026-03-05"}]), PERIOD)
        is None
    )


# ---------------------------------------------------------------------------
# R.1 — what counts as billed in period
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("raw", [None, "", "not a date", "n/a"])
def test_null_or_unparseable_last_billed_is_not_billed(raw) -> None:
    counts = compute(
        _frame([{"status": "Active", "monthly_fee": 10.0, "last_billed": raw}]),
        PERIOD,
    )
    assert counts.n_active == 1
    assert counts.n_billed_in_period == 0
    assert counts.count_delta == 1


@pytest.mark.parametrize(
    "billed,expected",
    [
        ("2026-03-01", 1),
        ("2026-03-31", 1),
        ("2026-02-28", 0),  # prior month
        ("2026-04-01", 0),  # next month
        ("2025-03-15", 0),  # right month, wrong year
    ],
)
def test_billed_in_period_is_year_month_equality(billed, expected) -> None:
    counts = compute(
        _frame([{"status": "Active", "monthly_fee": 10.0, "last_billed": billed}]),
        PERIOD,
    )
    assert counts.n_billed_in_period == expected


def test_billed_is_counted_over_active_rows_only() -> None:
    """A billed-but-cancelled row must not inflate the billed count."""
    counts = compute(
        _frame(
            [
                {"status": "Active", "monthly_fee": 10.0, "last_billed": "2026-03-05"},
                {
                    "status": "Cancelled",
                    "monthly_fee": 99.0,
                    "last_billed": "2026-03-05",
                },
            ]
        ),
        PERIOD,
    )
    assert (counts.n_active, counts.n_billed_in_period) == (1, 1)
    assert counts.fee_sum_active == 10.0  # cancelled fee excluded


def test_count_delta_never_negative() -> None:
    counts = compute(_roster(), PERIOD)
    assert counts.count_delta >= 0
    assert 0 <= counts.n_billed_in_period <= counts.n_active


# ---------------------------------------------------------------------------
# Fees and edges
# ---------------------------------------------------------------------------


def test_missing_fee_column_yields_none_not_zero() -> None:
    """A false 0.00 in a narrative is worse than no number at all."""
    counts = compute(
        _frame([{"status": "Active", "last_billed": "2026-03-05"}]), PERIOD
    )
    assert counts.n_active == 1
    assert counts.fee_sum_active is None
    assert counts.fee_sum_billed is None


def test_missing_last_billed_column_means_nothing_billed() -> None:
    counts = compute(_frame([{"status": "Active", "monthly_fee": 10.0}]), PERIOD)
    assert (counts.n_active, counts.n_billed_in_period, counts.count_delta) == (1, 0, 1)


def test_empty_sidecar_returns_none() -> None:
    assert compute(pd.DataFrame(), PERIOD) is None
    assert compute(None, PERIOD) is None


def test_duplicate_customer_ids_still_emit_counts(caplog) -> None:
    """R.3: rows are accounts; a multi-site customer legitimately has several."""
    counts = compute(
        _frame(
            [
                {
                    "customer_id": "C1",
                    "status": "Active",
                    "monthly_fee": 10.0,
                    "last_billed": "2026-03-05",
                },
                {
                    "customer_id": "C1",
                    "status": "Active",
                    "monthly_fee": 20.0,
                    "last_billed": "2026-03-05",
                },
            ]
        ),
        PERIOD,
    )
    assert counts.n_active == 2
    assert counts.fee_sum_active == 30.0


def test_counts_are_ints_not_floats() -> None:
    counts = compute(_roster(), PERIOD)
    for value in (counts.n_active, counts.n_billed_in_period, counts.count_delta):
        assert isinstance(value, int)
