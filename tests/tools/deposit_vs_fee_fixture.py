"""Isolated recon items for deposit vs processor-fee hints.

Not Sentinel/Vandelay xlsx: those files do not fire either scenario at the
account-total grain the consolidator emits (Sentinel install ratio is 1.10;
Bank Charges $95 is under the AND-gate and GL-only). Hand-crafted items keep
parser/Haiku out of the loop and pin the exact ratios pandas needs.
"""

from __future__ import annotations

from datetime import date

import pandas as pd

from backend.domain.contracts import ReconciliationItem, ReconciliationSource

PERIOD = date(2026, 3, 1)

# Customer 50% peşinat: GL recognized the full job; source has the deposit.
# 4000 / 8000 = 0.50 → is_round_fraction and is_customer_deposit.
DEPOSIT_GL = 8_000.0
DEPOSIT_SOURCE = 4_000.0
DEPOSIT_DELTA = DEPOSIT_SOURCE - DEPOSIT_GL  # -4000
DEPOSIT_PCT = DEPOSIT_DELTA / DEPOSIT_GL  # -0.50

# Processor gross vs net. |Δ| $3,500 clears the $500 AND-gate.
# |delta_pct| = 3500/61000 ≈ 5.74% sits in the 3–8% fee band.
FEE_GL = 61_000.0
FEE_NET = 57_500.0
FEE_DELTA = FEE_NET - FEE_GL  # -3500
FEE_PCT = FEE_DELTA / FEE_GL  # ≈ -0.0574

# Negative controls
BANK_CHARGES_GL = 95.0  # Sentinel-shaped: under $100, GL-only
VANDELAY_TIMING_PCT = 4_200.0 / 184_500.0  # ≈ 2.28%, below the 3% fee floor


def deposit_item() -> ReconciliationItem:
    return ReconciliationItem(
        account="Installation Revenue",
        category="REVENUE",
        sources=[
            ReconciliationSource(
                source_file="gl_export.xlsx", amount=DEPOSIT_GL, row_count=1
            ),
            ReconciliationSource(
                source_file="installation_payments.xlsx",
                amount=DEPOSIT_SOURCE,
                row_count=1,
            ),
        ],
        gl_amount=DEPOSIT_GL,
        non_gl_total=DEPOSIT_SOURCE,
        delta=DEPOSIT_DELTA,
        delta_pct=round(DEPOSIT_PCT, 4),
        severity="high",
    )


def deposit_raw_dfs() -> dict[str, pd.DataFrame]:
    return {
        "gl_export.xlsx": pd.DataFrame(
            {
                "account": ["Installation Revenue"],
                "amount": [DEPOSIT_GL],
                "date": [date(2026, 3, 1)],
            }
        ),
        "installation_payments.xlsx": pd.DataFrame(
            {
                "account": ["Installation Revenue"],
                "amount": [DEPOSIT_SOURCE],
                "Payment Type": ["50% Deposit"],
                "Balance Remaining": [4_000.0],
                "date": [date(2026, 3, 18)],
            }
        ),
    }


def deposit_consolidated() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "account": "Installation Revenue",
                "category": "REVENUE",
                "amount": DEPOSIT_GL + DEPOSIT_SOURCE,
            }
        ]
    )


def fee_item() -> ReconciliationItem:
    return ReconciliationItem(
        account="Product Sales",
        category="REVENUE",
        sources=[
            ReconciliationSource(
                source_file="gl_export.xlsx", amount=FEE_GL, row_count=1
            ),
            ReconciliationSource(
                source_file="payout_march.xlsx", amount=FEE_NET, row_count=1
            ),
        ],
        gl_amount=FEE_GL,
        non_gl_total=FEE_NET,
        delta=FEE_DELTA,
        delta_pct=round(FEE_PCT, 4),
        severity="medium",
    )


def fee_raw_dfs() -> dict[str, pd.DataFrame]:
    return {
        "gl_export.xlsx": pd.DataFrame(
            {
                "account": ["Product Sales"],
                "amount": [FEE_GL],
                "date": [date(2026, 3, 1)],
            }
        ),
        "payout_march.xlsx": pd.DataFrame(
            {
                "account": ["Product Sales"],
                "amount": [FEE_NET],
                "date": [date(2026, 3, 31)],
            }
        ),
    }


def fee_consolidated() -> pd.DataFrame:
    return pd.DataFrame(
        [{"account": "Product Sales", "category": "REVENUE", "amount": FEE_GL + FEE_NET}]
    )


def bank_charges_gl_only_item() -> ReconciliationItem:
    return ReconciliationItem(
        account="Bank Charges",
        category="G&A",
        sources=[
            ReconciliationSource(
                source_file="gl_export.xlsx", amount=BANK_CHARGES_GL, row_count=1
            )
        ],
        gl_amount=BANK_CHARGES_GL,
        non_gl_total=0.0,
        delta=-BANK_CHARGES_GL,
        delta_pct=-1.0,
        severity="low",
    )
