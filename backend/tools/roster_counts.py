"""Item 4 — RMR account-count vs GL.

Pandas counts over a contracts/roster sidecar. No Claude, no DB, no I/O, no
classification, no fuzzy matching. Claude only ever copies these integers.

Spec: docs/sprint/kova2-implementation-plan.md, item 4, sections C.2 / C.3,
including resolutions R.1 (billed-in-period is defined over Active rows only),
R.2 (Active is an exact normalized match), R.3 (rows are accounts, not
customers; mid-period rate changes deferred) and R.8 (counts are point values,
never ratios).

**Never log a customer name, a customer id, or a fee.** A roster is the most
PII-adjacent file the product ingests; only aggregate integers may be logged.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import pandas as pd

from backend.logger import get_logger

logger = get_logger(__name__)

# R.2: the only status token that counts as billable this month. Everything
# else — cancelled, suspended, pending, on hold, inactive, terminated, and any
# value we have not anticipated — is NOT active. Stretching this would invent
# revenue. v1 deliberately has no richer breakdown (Open Question 1).
_ACTIVE_STATUS = "active"


@dataclass(frozen=True)
class RosterCounts:
    """Pandas-computed roster facts. Every field is copied, never derived."""

    n_active: int
    n_billed_in_period: int
    count_delta: int
    fee_sum_active: float | None
    fee_sum_billed: float | None
    # The dollar size of the gap, computed here so the narrative can state it
    # without subtracting. Claude was giving both sides ("$3,825.00 against
    # $3,540.00") and leaving the reader to do the arithmetic, because the
    # only golden-rule-safe alternative was saying nothing. None whenever the
    # fee sums are None — a gap with no fee column is not a zero gap.
    fee_gap: float | None


def _normalized_status(value: object) -> str:
    if value is None or (not isinstance(value, str) and pd.isna(value)):
        return ""
    return str(value).strip().casefold()


def compute(sidecar: pd.DataFrame | None, period: date) -> RosterCounts | None:
    """Return roster counts, or None when the file cannot support a count story.

    Returns None (and the caller falls back to today's dollar-only behaviour)
    when the sidecar is missing, empty, or has no status column. R.2 is
    explicit that a missing status column must NOT be read as "all active".
    """
    if sidecar is None or sidecar.empty:
        return None
    if "status" not in sidecar.columns:
        logger.info(
            "roster_counts_skipped",
            extra={"reason": "no status column", "rows_in_sidecar": int(len(sidecar))},
        )
        return None

    status = sidecar["status"].map(_normalized_status)
    is_active = status == _ACTIVE_STATUS

    # R.1: billed-in-period is counted over ACTIVE rows only, so count_delta
    # means exactly "active but not billed this month" and can never be
    # negative. Null / blank / unparseable last_billed is NOT billed — absence
    # of billing evidence is not evidence of billing.
    if "last_billed" in sidecar.columns:
        billed_at = pd.to_datetime(sidecar["last_billed"], errors="coerce")
        in_period = (billed_at.dt.year == period.year) & (
            billed_at.dt.month == period.month
        )
        in_period = in_period.fillna(False)
    else:
        in_period = pd.Series(False, index=sidecar.index)

    is_billed = is_active & in_period

    n_active = int(is_active.sum())
    n_billed = int(is_billed.sum())
    count_delta = n_active - n_billed

    if count_delta < 0:
        # Unreachable while is_billed is a subset of is_active. If a future
        # change breaks that invariant, emit nothing rather than a bad count.
        logger.warning(
            "roster_counts_negative_delta",
            extra={"n_active": n_active, "n_billed_in_period": n_billed},
        )
        return None

    fee_sum_active: float | None = None
    fee_sum_billed: float | None = None
    fee_gap: float | None = None
    if "monthly_fee" in sidecar.columns:
        fees = pd.to_numeric(sidecar["monthly_fee"], errors="coerce").fillna(0.0)
        fee_sum_active = round(float(fees[is_active].sum()), 2)
        fee_sum_billed = round(float(fees[is_billed].sum()), 2)
        # Rounded from the rounded sums, not from the raw floats, so the
        # narrated gap always equals the two narrated sides exactly. Deriving
        # it from unrounded sums could print a gap a cent off from the
        # subtraction a reader performs on the printed figures.
        fee_gap = round(fee_sum_active - fee_sum_billed, 2)

    # R.3: rows are ACCOUNTS, not customers. A rate increase represented as two
    # rows counts twice; that is deferred, not solved. Log the duplicate count
    # (never the ids themselves) so the limitation is observable.
    if "customer_id" in sidecar.columns:
        duplicates = int(sidecar["customer_id"].duplicated().sum())
        if duplicates:
            logger.warning(
                "roster_counts_duplicate_customer_ids",
                extra={
                    "duplicate_rows": duplicates,
                    "note": "counts are per account row; mid-period rate changes "
                    "may appear twice (R.3, deferred)",
                },
            )

    # Values only — never a name, an id, or an individual fee.
    logger.info(
        "roster_counts",
        extra={
            "n_active": n_active,
            "n_billed_in_period": n_billed,
            "count_delta": count_delta,
            "rows_in_sidecar": int(len(sidecar)),
        },
    )

    return RosterCounts(
        n_active=n_active,
        n_billed_in_period=n_billed,
        count_delta=count_delta,
        fee_sum_active=fee_sum_active,
        fee_sum_billed=fee_sum_billed,
        fee_gap=fee_gap,
    )
