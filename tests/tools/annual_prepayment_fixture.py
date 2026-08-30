"""Isolated recon items for same-item annual-prepayment (12×) hints.

Not Sentinel/Vandelay/DRONE xlsx: none of those files has a clean same-account
GL-vs-source 12× pair. Sentinel Service Revenue Δ$285 is the *negative*
control — the retired other-account rule matched Rent / Payroll Taxes.
"""

from __future__ import annotations

from datetime import date

import pandas as pd

from backend.domain.contracts import ReconciliationItem, ReconciliationSource

PERIOD = date(2026, 3, 1)

# Same-account annual lump: GL booked the year, vendor file is one month.
ANNUAL_GL = 13_200.0
ANNUAL_MONTHLY = 1_100.0
ANNUAL_DELTA = ANNUAL_MONTHLY - ANNUAL_GL  # -12100
ANNUAL_PCT = ANNUAL_DELTA / ANNUAL_GL  # ≈ -0.9167
IMPLIED_MONTHLY = ANNUAL_GL / 12.0  # 1100.0 — pandas, not Claude

# Sentinel Service Revenue: cancelled contracts still on the roster.
# Old formula: |285| × 12 = 3420 ≈ Payroll Taxes 3675 (7.5%) and Rent 3200 (6.4%).
SENTINEL_GL = 3_540.0
SENTINEL_SOURCE = 3_825.0
SENTINEL_DELTA = SENTINEL_SOURCE - SENTINEL_GL  # 285
SENTINEL_PAYROLL_TAXES = 3_675.0
SENTINEL_RENT = 3_200.0


def annual_item() -> ReconciliationItem:
    return ReconciliationItem(
        account="Software Subscriptions",
        category="OPEX",
        sources=[
            ReconciliationSource(
                source_file="gl_export.xlsx", amount=ANNUAL_GL, row_count=1
            ),
            ReconciliationSource(
                source_file="vendor_invoices.xlsx",
                amount=ANNUAL_MONTHLY,
                row_count=1,
            ),
        ],
        gl_amount=ANNUAL_GL,
        non_gl_total=ANNUAL_MONTHLY,
        delta=ANNUAL_DELTA,
        delta_pct=round(ANNUAL_PCT, 4),
        severity="high",
    )


def annual_raw_dfs() -> dict[str, pd.DataFrame]:
    return {
        "gl_export.xlsx": pd.DataFrame(
            {
                "account": ["Software Subscriptions"],
                "amount": [ANNUAL_GL],
                "date": [date(2026, 3, 1)],
            }
        ),
        "vendor_invoices.xlsx": pd.DataFrame(
            {
                "account": ["Software Subscriptions"],
                "amount": [ANNUAL_MONTHLY],
                "date": [date(2026, 3, 15)],
            }
        ),
    }


def annual_consolidated() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "account": "Software Subscriptions",
                "category": "OPEX",
                "amount": ANNUAL_GL,
            }
        ]
    )


def annual_source_is_lump_item() -> ReconciliationItem:
    """Inverse: source holds the year, GL shows one month."""
    delta = ANNUAL_GL - ANNUAL_MONTHLY
    return ReconciliationItem(
        account="Software Subscriptions",
        category="OPEX",
        sources=[
            ReconciliationSource(
                source_file="gl_export.xlsx", amount=ANNUAL_MONTHLY, row_count=1
            ),
            ReconciliationSource(
                source_file="vendor_invoices.xlsx", amount=ANNUAL_GL, row_count=1
            ),
        ],
        gl_amount=ANNUAL_MONTHLY,
        non_gl_total=ANNUAL_GL,
        delta=delta,
        delta_pct=round(delta / ANNUAL_MONTHLY, 4),
        severity="high",
    )


def sentinel_service_revenue_item() -> ReconciliationItem:
    return ReconciliationItem(
        account="Service Revenue",
        category="REVENUE",
        sources=[
            ReconciliationSource(
                source_file="gl_export.xlsx", amount=SENTINEL_GL, row_count=1
            ),
            ReconciliationSource(
                source_file="contracts_roster.xlsx",
                amount=SENTINEL_SOURCE,
                row_count=85,
            ),
        ],
        gl_amount=SENTINEL_GL,
        non_gl_total=SENTINEL_SOURCE,
        delta=SENTINEL_DELTA,
        delta_pct=round(SENTINEL_DELTA / SENTINEL_GL, 4),
        severity="medium",
    )


def sentinel_pnl_with_rent_and_payroll_taxes() -> pd.DataFrame:
    """P&L that would have false-fired the retired other-account ×12 rule."""
    return pd.DataFrame(
        [
            {
                "account": "Service Revenue",
                "category": "REVENUE",
                "amount": SENTINEL_GL,
            },
            {
                "account": "Payroll Taxes",
                "category": "OPEX",
                "amount": SENTINEL_PAYROLL_TAXES,
            },
            {
                "account": "Rent",
                "category": "G&A",
                "amount": SENTINEL_RENT,
            },
        ]
    )


def sentinel_raw_dfs() -> dict[str, pd.DataFrame]:
    return {
        "gl_export.xlsx": pd.DataFrame(
            {
                "account": ["Service Revenue"],
                "amount": [SENTINEL_GL],
                "date": [date(2026, 3, 1)],
            }
        ),
        "contracts_roster.xlsx": pd.DataFrame(
            {
                "account": ["Service Revenue"],
                "amount": [SENTINEL_SOURCE],
                "Last Billed": [date(2026, 4, 1)],
            }
        ),
    }


def gl_only_software_item() -> ReconciliationItem:
    """Sentinel Software Subscriptions $615 — coverage, not a prepaid."""
    return ReconciliationItem(
        account="Software Subscriptions",
        category="OPEX",
        sources=[
            ReconciliationSource(
                source_file="gl_export.xlsx", amount=615.0, row_count=1
            )
        ],
        gl_amount=615.0,
        non_gl_total=0.0,
        delta=-615.0,
        delta_pct=-1.0,
        severity="low",
    )
