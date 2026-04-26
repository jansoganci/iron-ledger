"""Unit tests for SupabaseAnomaliesRepo.list_account_flag_counts_before.

Uses a hand-crafted mock of the supabase-py builder chain so no live DB is
needed.  Each test controls the rows returned by the mock and asserts on the
resulting {account_id: count} dict.
"""

from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock

from backend.adapters.supabase_repos import SupabaseAnomaliesRepo, _months_before


# ---------------------------------------------------------------------------
# _months_before helper
# ---------------------------------------------------------------------------


def test_months_before_crosses_year_boundary() -> None:
    assert _months_before(date(2026, 3, 1), 6) == date(2025, 9, 1)


def test_months_before_same_year() -> None:
    assert _months_before(date(2026, 8, 1), 3) == date(2026, 5, 1)


def test_months_before_january() -> None:
    assert _months_before(date(2026, 1, 1), 1) == date(2025, 12, 1)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_repo(rows: list[dict]) -> SupabaseAnomaliesRepo:
    """Return a repo whose Supabase client returns *rows* for any SELECT."""
    mock_resp = MagicMock()
    mock_resp.data = rows

    # Build a fluent mock: every chained call (select, eq, gte, lt, neq)
    # returns the same builder object; .execute() returns mock_resp.
    builder = MagicMock()
    builder.select.return_value = builder
    builder.eq.return_value = builder
    builder.gte.return_value = builder
    builder.lt.return_value = builder
    builder.neq.return_value = builder
    builder.execute.return_value = mock_resp

    client = MagicMock()
    client.table.return_value = builder

    return SupabaseAnomaliesRepo(client)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

BEFORE = date(2026, 3, 1)
ACCT_A = "acct-aaa"
ACCT_B = "acct-bbb"


def test_no_prior_flags_returns_empty_dict() -> None:
    repo = _make_repo([])
    result = repo.list_account_flag_counts_before("co-1", BEFORE)
    assert result == {}


def test_account_with_two_distinct_periods_returns_count_2() -> None:
    rows = [
        {"account_id": ACCT_A, "period": "2026-01-01"},
        {"account_id": ACCT_A, "period": "2026-02-01"},
    ]
    repo = _make_repo(rows)
    result = repo.list_account_flag_counts_before("co-1", BEFORE)
    assert result[ACCT_A] == 2


def test_duplicate_period_rows_counted_once() -> None:
    # Two rows for the same (account, period) — should count as 1 distinct period.
    rows = [
        {"account_id": ACCT_A, "period": "2026-01-01"},
        {"account_id": ACCT_A, "period": "2026-01-01"},
    ]
    repo = _make_repo(rows)
    result = repo.list_account_flag_counts_before("co-1", BEFORE)
    assert result[ACCT_A] == 1


def test_low_severity_rows_are_excluded_by_query_filter() -> None:
    # The .neq("severity", "low") filter is applied at the DB layer; the repo
    # implementation trusts the DB to exclude them.  We verify the builder
    # receives the correct .neq call so we know the filter was issued.
    rows: list[dict] = []
    mock_resp = MagicMock()
    mock_resp.data = rows

    builder = MagicMock()
    builder.select.return_value = builder
    builder.eq.return_value = builder
    builder.gte.return_value = builder
    builder.lt.return_value = builder
    builder.neq.return_value = builder
    builder.execute.return_value = mock_resp

    client = MagicMock()
    client.table.return_value = builder

    repo = SupabaseAnomaliesRepo(client)
    repo.list_account_flag_counts_before("co-1", BEFORE)

    builder.neq.assert_called_once_with("severity", "low")


def test_boundary_flag_exactly_at_cutoff_is_included() -> None:
    # cutoff for BEFORE=2026-03-01 with 6 months = 2025-09-01
    # A flag on 2025-09-01 must be included (period >= cutoff).
    cutoff = date(2025, 9, 1)
    rows = [
        {"account_id": ACCT_A, "period": str(cutoff)},
    ]
    repo = _make_repo(rows)
    result = repo.list_account_flag_counts_before("co-1", BEFORE)
    assert result[ACCT_A] == 1


def test_multiple_accounts_counted_independently() -> None:
    rows = [
        {"account_id": ACCT_A, "period": "2026-01-01"},
        {"account_id": ACCT_A, "period": "2026-02-01"},
        {"account_id": ACCT_B, "period": "2026-02-01"},
    ]
    repo = _make_repo(rows)
    result = repo.list_account_flag_counts_before("co-1", BEFORE)
    assert result[ACCT_A] == 2
    assert result[ACCT_B] == 1
