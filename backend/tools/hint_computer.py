"""Deterministic hint computation for reconciliation classification.

All functions are pure pandas — no Claude, no DB, no I/O.
Hints feed into the Claude prompt so the LLM can classify with data-backed
signals rather than guessing from dollar amounts alone.

Hint definitions (match ReconciliationHints in domain/contracts.py):

  crosses_period_boundary   — any transaction date in the involved source file(s)
                              falls after period_end. Strong timing_cutoff signal.

  is_round_fraction         — non_gl_total / gl_amount ≈ 0.5 (±5%).
                              Suggests a 50% deposit or advance — timing signal.

  similar_amount_in_other_account
                            — the item's delta appears as the total of a different
                              account in the consolidated DataFrame. Strong
                              categorical_misclassification signal: the missing
                              $700 from Payroll is sitting as $700 in Contractors.

  is_source_only            — account present in at least one dept file but
                              absent from the GL source entirely.

  is_gl_only                — account present only in the GL source, with no
                              matching entry from any dept file.

  delta_matches_known_vendor
                            — delta × 12 ≈ an amount found in another account's
                              GL total (suggests an annual invoice expensed in
                              full rather than amortized monthly).
"""

from __future__ import annotations

from datetime import date

import pandas as pd

from backend.domain.contracts import ReconciliationHints, ReconciliationItem
from backend.logger import get_logger

logger = get_logger(__name__)

_ROUND_FRACTION_TOLERANCE = 0.05  # ±5% around 0.50
_AMOUNT_MATCH_TOLERANCE = 0.10  # ±10% for cross-account dollar match
_ANNUAL_MATCH_TOLERANCE = 0.10  # ±10% for delta × 12 ≈ another account


def compute_hints(
    item: ReconciliationItem,
    consolidated_df: pd.DataFrame,
    period: date,
    source_raw_dfs: dict[str, pd.DataFrame],
) -> ReconciliationHints:
    """Return a fully populated ReconciliationHints for one reconciliation item.

    Args:
        item: The ReconciliationItem to annotate (gl_amount, non_gl_total, delta,
              sources list with source_file names).
        consolidated_df: Full consolidated DataFrame — columns [account, category,
                         amount, source_breakdown]. One row per canonical account.
        period: The reporting period end (last day of the month).
        source_raw_dfs: {filename: validated DataFrame with [account, amount, date, ...]}
                         produced by ParserAgent.parse_file_silently().
    """
    try:
        period_end = _period_end(period)
        involved_files = {s.source_file for s in item.sources}
        is_source_only = _is_source_only(item)
        is_gl_only = _is_gl_only(item)

        return ReconciliationHints(
            crosses_period_boundary=_crosses_period_boundary(
                involved_files, source_raw_dfs, period_end
            ),
            is_round_fraction=_is_round_fraction(item),
            similar_amount_in_other_account=_similar_amount_in_other_account(
                item, consolidated_df
            ),
            is_source_only=is_source_only,
            is_gl_only=is_gl_only,
            delta_matches_known_vendor=_delta_matches_known_vendor(
                item, consolidated_df
            ),
        )
    except Exception as exc:
        logger.warning(
            "hint_computer_error",
            extra={
                "event": "hint_computer_error",
                "account": item.account,
                "error": str(exc),
            },
        )
        return ReconciliationHints()


# ---------------------------------------------------------------------------
# Individual hint functions
# ---------------------------------------------------------------------------


def _crosses_period_boundary(
    involved_files: set[str],
    source_raw_dfs: dict[str, pd.DataFrame],
    period_end: date,
) -> bool:
    """True if any row in an involved source file has date > period_end.

    Checks all date-like columns (not just the canonical 'date' column) so
    that files with "Balance Due Date", "Due Date", "Payment Date" etc. are
    also caught. Uses pandas coercion to tolerate mixed-type columns.
    """
    for filename in involved_files:
        df = source_raw_dfs.get(filename)
        if df is None or df.empty:
            continue
        for col in df.select_dtypes(
            include=["object", "datetime64[ns]", "datetime64[ns, UTC]"]
        ).columns:
            try:
                parsed = pd.to_datetime(
                    df[col], errors="coerce", dayfirst=False, format="mixed"
                )
                if parsed.dropna().empty:
                    continue
                future_dates = parsed.dropna().dt.date
                if any(d > period_end for d in future_dates):
                    return True
            except Exception:
                continue
    return False


def _is_round_fraction(item: ReconciliationItem) -> bool:
    """True when non_gl_total / gl_amount is within ±5% of 0.50.

    Signals a 50% deposit or advance payment pattern — strong timing indicator.
    """
    if item.gl_amount is None or item.gl_amount == 0:
        return False
    ratio = item.non_gl_total / item.gl_amount
    return abs(ratio - 0.5) <= _ROUND_FRACTION_TOLERANCE


def _similar_amount_in_other_account(
    item: ReconciliationItem,
    consolidated_df: pd.DataFrame,
) -> bool:
    """True when abs(delta) appears as another account's consolidated total ±10%.

    This is the categorical misclassification fingerprint:
    $700 missing from Payroll → $700 shows up as Contractors line in the GL.
    Only fires when the matching account is NOT the same account as item.account.
    """
    abs_delta = abs(item.delta)
    if abs_delta < 1.0:
        return False
    for _, row in consolidated_df.iterrows():
        if row["account"] == item.account:
            continue
        other_amt = abs(float(row["amount"]))
        if other_amt < 1.0:
            continue
        if abs(other_amt - abs_delta) / abs_delta <= _AMOUNT_MATCH_TOLERANCE:
            return True
    return False


def _is_source_only(item: ReconciliationItem) -> bool:
    """True when NO GL source contributed to this account.

    Used for accounts that appear in a dept file but have no GL entry.
    """
    from backend.agents.consolidator import _is_gl_label

    gl_sources = [s for s in item.sources if _is_gl_label(s.source_file)]
    return len(gl_sources) == 0 and len(item.sources) > 0


def _is_gl_only(item: ReconciliationItem) -> bool:
    """True when ONLY a GL source contributed to this account.

    Used for accounts present in the GL but absent from all dept files.
    """
    from backend.agents.consolidator import _is_gl_label

    gl_sources = [s for s in item.sources if _is_gl_label(s.source_file)]
    non_gl_sources = [s for s in item.sources if not _is_gl_label(s.source_file)]
    return len(gl_sources) > 0 and len(non_gl_sources) == 0


def _delta_matches_known_vendor(
    item: ReconciliationItem,
    consolidated_df: pd.DataFrame,
) -> bool:
    """True when delta × 12 ≈ another account's GL total ±10%.

    Signals an annual-subscription / annual-invoice pattern: the full invoice
    was expensed in one month instead of being amortized monthly. For example,
    a $13,200 HubSpot invoice should be $1,100/month; if the GL shows $13,200
    for March, the delta vs. expected ($12,100) × 12 ≈ $13,200 full-year cost.
    """
    abs_delta = abs(item.delta)
    if abs_delta < 1.0:
        return False
    annual_equivalent = abs_delta * 12
    for _, row in consolidated_df.iterrows():
        if row["account"] == item.account:
            continue
        other_amt = abs(float(row["amount"]))
        if other_amt < 1.0:
            continue
        if (
            abs(other_amt - annual_equivalent) / annual_equivalent
            <= _ANNUAL_MATCH_TOLERANCE
        ):
            return True
    return False


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _period_end(period: date) -> date:
    """Return last day of the given period's month."""
    import calendar

    last_day = calendar.monthrange(period.year, period.month)[1]
    return date(period.year, period.month, last_day)
