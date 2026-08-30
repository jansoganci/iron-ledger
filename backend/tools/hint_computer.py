"""Deterministic hint computation for reconciliation classification.

All functions are pure pandas — no Claude, no DB, no I/O.
Hints feed into the Claude prompt so the LLM can classify with data-backed
signals rather than guessing from dollar amounts alone.

Hint definitions (match ReconciliationHints in domain/contracts.py):

  crosses_period_boundary   — a *transaction-like* date in an involved source
                              file falls after period_end (invoice / payout /
                              payment / deposit / balance-due / canonical date).
                              Roster cycle dates (last billed, renewal, start,
                              end, next bill) are ignored. Strong timing_cutoff
                              signal.

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

  looks_like_annual_prepayment
                            — two-sided, same item: |GL| / |source| (or the
                              inverse) ≈ 12 ±10%. Annual cash booked in one
                              month instead of amortized. Never scans other
                              P&L accounts. implied_monthly = max(|GL|,
                              |source|) / 12 (pandas). Alias:
                              delta_matches_known_vendor.

  is_customer_deposit       — two-sided 50% peşinat / unearned revenue. True when
                              the account-total ratio is ~0.50 or an involved
                              source file has deposit / balance-remaining columns.
                              Not a vendor prepaid.

  is_processor_fee_gap      — two-sided gross-vs-net gap whose |delta_pct| sits
                              in a pandas fee band. Never set on GL-only /
                              source-only / customer-deposit items.
"""

from __future__ import annotations

from datetime import date

import pandas as pd

from backend.domain.contracts import ReconciliationHints, ReconciliationItem
from backend.logger import get_logger

logger = get_logger(__name__)

_ROUND_FRACTION_TOLERANCE = 0.05  # ±5% around 0.50
_AMOUNT_MATCH_TOLERANCE = 0.10  # ±10% for cross-account dollar match
_ANNUAL_RATIO = 12.0  # annual lump vs monthly run-rate; ×4 quarterly is out of slice
_ANNUAL_MATCH_TOLERANCE = 0.10  # ±10% around 12×
_ANNUAL_SIDE_FLOOR = 100.0  # both sides must clear this; skips noise / coverage crumbs
# Processor/platform netting as a share of the GL side. Floor is above the
# ~2.3% Vandelay late-payout shape; ceiling is below a 50% deposit ratio.
_FEE_BAND_MIN = 0.03
_FEE_BAND_MAX = 0.08

_DEPOSIT_HEADER_NEEDLES = (
    "deposit",
    "balance remaining",
    "balance_remaining",
    "payment type",
    "payment_type",
)
_DEPOSIT_VALUE_TOKENS = ("deposit", "50%")

# Cutoff hint: txn-like headers only. "date" matches Start Date, so blocklist
# must run after. Do not blanket-drop every "due" — Balance Due Date stays.
_CUTOFF_DATE_ALLOW = (
    "date",
    "txn date",
    "transaction date",
    "invoice date",
    "payment date",
    "payout date",
    "settlement date",
    "deposit date",
    "balance due",
    "due date",
)
_CUTOFF_DATE_BLOCK = (
    "last billed",
    "start date",
    "end date",
    "renewal",
    "next bill",
    "next_bill",
    "contract end",
    "payout period",
)
_CONTRACTS_FILE_NEEDLES = ("contract", "roster", "subscription", "recurring")


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
        is_customer_deposit = _is_customer_deposit(
            item, is_gl_only, is_source_only, involved_files, source_raw_dfs
        )
        is_processor_fee_gap = _is_processor_fee_gap(
            item, is_gl_only, is_source_only, is_customer_deposit
        )
        looks_like_annual, implied_monthly = _looks_like_annual_prepayment(
            item,
            is_gl_only=is_gl_only,
            is_source_only=is_source_only,
            is_customer_deposit=is_customer_deposit,
            is_processor_fee_gap=is_processor_fee_gap,
        )

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
            looks_like_annual_prepayment=looks_like_annual,
            implied_monthly=implied_monthly,
            delta_matches_known_vendor=looks_like_annual,
            is_customer_deposit=is_customer_deposit,
            is_processor_fee_gap=is_processor_fee_gap,
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
    """True if a transaction-like date in an involved file is after period_end.

    Roster/renewal/last-billed/start/end columns are ignored. Contracts-shaped
    filenames are skipped entirely so a roster column named ``date`` cannot
    steal timing_cutoff. Invoice due / balance due / payout dates still count.
    Never logs cell values.
    """
    for filename in involved_files:
        if _is_contracts_roster_file(filename):
            continue
        df = source_raw_dfs.get(filename)
        if df is None or df.empty:
            continue
        for col in df.columns:
            if not _is_cutoff_date_column(col):
                continue
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


def _normalize_header(col: object) -> str:
    return str(col).lower().replace("_", " ")


def _is_contracts_roster_file(filename: str) -> bool:
    stem = filename.lower().replace("-", "_").replace(" ", "_").split("/")[-1]
    return any(n in stem for n in _CONTRACTS_FILE_NEEDLES)


def _is_cutoff_date_column(col: object) -> bool:
    header = _normalize_header(col)
    if any(n in header for n in _CUTOFF_DATE_BLOCK):
        return False
    return any(n in header for n in _CUTOFF_DATE_ALLOW)


def _is_round_fraction(item: ReconciliationItem) -> bool:
    """True when non_gl_total / gl_amount is within ±5% of 0.50.

    Signals a 50% deposit or advance payment pattern — strong timing indicator.
    """
    if item.gl_amount is None or item.gl_amount == 0:
        return False
    ratio = item.non_gl_total / item.gl_amount
    return abs(ratio - 0.5) <= _ROUND_FRACTION_TOLERANCE


def _is_customer_deposit(
    item: ReconciliationItem,
    is_gl_only: bool,
    is_source_only: bool,
    involved_files: set[str],
    source_raw_dfs: dict[str, pd.DataFrame],
) -> bool:
    """Two-sided customer peşinat — ratio ~50% or deposit columns in a source file."""
    if is_gl_only or is_source_only:
        return False
    if _is_round_fraction(item):
        return True
    return _deposit_column_signal(involved_files, source_raw_dfs)


def _deposit_column_signal(
    involved_files: set[str],
    source_raw_dfs: dict[str, pd.DataFrame],
) -> bool:
    """True when an involved file has a deposit/balance-remaining header.

    Matches column names (and a closed token list on payment-type columns).
    Never logs cell values.
    """
    for filename in involved_files:
        df = source_raw_dfs.get(filename)
        if df is None or df.empty:
            continue
        for col in df.columns:
            col_l = str(col).lower()
            if not any(needle in col_l for needle in _DEPOSIT_HEADER_NEEDLES):
                continue
            if "payment type" in col_l or "payment_type" in col_l:
                tokens = df[col].dropna().astype(str).str.lower()
                if tokens.apply(lambda v: any(t in v for t in _DEPOSIT_VALUE_TOKENS)).any():
                    return True
                continue
            if "balance remaining" in col_l or "balance_remaining" in col_l:
                remaining = pd.to_numeric(df[col], errors="coerce").fillna(0.0)
                if (remaining > 0).any():
                    return True
                continue
            if "deposit" in col_l:
                return True
    return False


def _is_processor_fee_gap(
    item: ReconciliationItem,
    is_gl_only: bool,
    is_source_only: bool,
    is_customer_deposit: bool,
) -> bool:
    """Two-sided gross-vs-net whose |delta_pct| sits in the pandas fee band."""
    if is_gl_only or is_source_only or is_customer_deposit:
        return False
    if item.delta_pct is None:
        return False
    abs_pct = abs(item.delta_pct)
    return _FEE_BAND_MIN <= abs_pct <= _FEE_BAND_MAX


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


def _looks_like_annual_prepayment(
    item: ReconciliationItem,
    *,
    is_gl_only: bool,
    is_source_only: bool,
    is_customer_deposit: bool,
    is_processor_fee_gap: bool,
) -> tuple[bool, float | None]:
    """Same-item |GL| vs |source| ≈ 12× ±10%. Returns (hint, implied_monthly).

    Does not scan other P&L accounts. Deposit and fee hints win: a 50%
    peşinat or a 3–8% processor gap is never an annual prepaid. One-sided
    coverage is not a prepaid. Quarterly ×4 is out of this slice.
    """
    if is_gl_only or is_source_only or is_customer_deposit or is_processor_fee_gap:
        return False, None
    if item.gl_amount is None:
        return False, None
    gl_abs = abs(float(item.gl_amount))
    source_abs = abs(float(item.non_gl_total))
    if gl_abs < _ANNUAL_SIDE_FLOOR or source_abs < _ANNUAL_SIDE_FLOOR:
        return False, None
    smaller = min(gl_abs, source_abs)
    if smaller == 0:
        return False, None
    ratio = max(gl_abs, source_abs) / smaller
    lo = _ANNUAL_RATIO * (1.0 - _ANNUAL_MATCH_TOLERANCE)
    hi = _ANNUAL_RATIO * (1.0 + _ANNUAL_MATCH_TOLERANCE)
    if lo <= ratio <= hi:
        return True, max(gl_abs, source_abs) / _ANNUAL_RATIO
    return False, None


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _period_end(period: date) -> date:
    """Return last day of the given period's month."""
    import calendar

    last_day = calendar.monthrange(period.year, period.month)[1]
    return date(period.year, period.month, last_day)
