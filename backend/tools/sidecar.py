"""Item 1 — bank/processor/contracts sidecar extraction.

Copies matcher columns off a raw upload frame BEFORE `normalizer.apply_plan`
drops them. Returns None for every file type the matcher does not consume, so
the golden path is untouched for P&L, payroll and supplier files.

Extracted from `ParserAgent._build_sidecar` — it never touched `self`, so it
is a pure function: `tools/` per CLAUDE.md is "stateless helpers, no DB, no
LLM", which this always was.
"""

from __future__ import annotations

import pandas as pd

from backend.domain.contracts import DiscoveryPlan
from backend.logger import get_logger
from backend.tools import normalizer

logger = get_logger(__name__)

# Item 1 — the company's single Undeposited Funds / merchant-clearing GL name.
# v1 simplification: the MVP boundary is locked to ONE clearing account, so this
# is a constant rather than config. If the product ever supports multiple
# clearing accounts this must become configurable (a company setting), which
# would need a migration — deliberately out of scope here.
_DEFAULT_UF_ACCOUNT_NAME = "Undeposited Funds"


def _normalize_header(col: object) -> str:
    return str(col).strip().lower().replace(" ", "_").replace("-", "_")


# Canonical sidecar column -> accepted raw headers, per C.5.1's frame table.
# First alias found wins, so canonical names always take precedence.
_SIDECAR_COLUMNS: dict[str, dict[str, tuple[str, ...]]] = {
    "processor_settlement": {
        "payout_id": ("payout_id", "batch_id", "payout", "batch", "reference"),
        "gross": ("gross", "gross_amount", "amount_collected"),
        "net": ("net", "net_amount"),
        "collected_date": ("collected_date", "collected", "date"),
    },
    "bank_statement": {
        "bank_ref": ("bank_ref", "reference", "payout_id", "ref"),
        "gross": ("gross", "gross_amount"),
        "fee": ("fee", "fees"),
        "net": ("net", "net_amount"),
        "amount": ("amount", "deposit", "credit"),
        "settlement_date": ("settlement_date", "settled", "posted_date", "date"),
    },
    # Item 4 — contracts / RMR roster. Preserves the count inputs before
    # apply_plan drops them. customer_name is deliberately NOT here: it is not
    # a count input and must not ride along.
    "contracts": {
        "customer_id": ("customer_id", "customer", "account_id", "site_id"),
        "status": ("status", "account_status", "contract_status"),
        "monthly_fee": ("monthly_fee", "monthly_amount", "rate", "mrr", "rmr"),
        "last_billed": ("last_billed", "last_billed_date", "last_invoice_date"),
    },
    "general_ledger": {
        "gl_ref": ("gl_ref", "memo", "reference", "check_no", "check_number"),
        "gl_account": ("gl_account", "account"),
        "amount": ("amount",),
        "gl_date": ("gl_date", "date"),
    },
}


def build_sidecar(
    df_raw: "pd.DataFrame",
    file_type: str | None,
    plan: DiscoveryPlan | None = None,
) -> "pd.DataFrame | None":
    """Copy matcher columns off the raw frame BEFORE apply_plan drops them.

    Returns None for every file type the matcher does not consume, so the
    golden path is untouched for P&L, payroll and supplier files.

    Header mapping note (v1): the spec says "Discovery maps onto these"
    canonical names but never specifies how. Rather than guess at a
    Discovery prompt change, this resolves headers deterministically
    against an explicit alias list — no LLM in the path, consistent with
    the matcher being pandas-only. Files with unrecognised headers simply
    produce no sidecar and fall back to today's behaviour.

    `df_raw` comes from `file_reader.read_file`, whose columns are integer
    positions — header promotion happens later, inside apply_plan. Matching
    aliases against those integers can never hit, so when Discovery's plan
    is available we promote headers here first. That still runs ahead of
    apply_plan's column drop, which is the constraint that matters.
    """
    if file_type not in _SIDECAR_COLUMNS:
        return None

    if plan is not None:
        df_raw = normalizer.promote_headers(df_raw, plan)

    lookup = {_normalize_header(c): c for c in df_raw.columns}
    out = {}
    for canonical, aliases in _SIDECAR_COLUMNS[file_type].items():
        for alias in aliases:
            if alias in lookup:
                out[canonical] = df_raw[lookup[alias]]
                break
    if not out:
        return None

    # reset_index: a promoted frame starts after the header row, so its
    # index no longer starts at 0. The masks below build fallback Series on
    # a fresh RangeIndex, and mismatched indexes make pandas reindex the
    # boolean key instead of aligning positionally.
    sidecar = pd.DataFrame(out).reset_index(drop=True)
    sidecar["_orig_row_index"] = range(len(sidecar))

    if file_type == "general_ledger":
        # C.5.1: sidecar only rows carrying a ref OR sitting on the UF
        # account. "Do not sidecar Rent."
        ref = (
            sidecar["gl_ref"]
            if "gl_ref" in sidecar
            else pd.Series([None] * len(sidecar))
        )
        account = (
            sidecar["gl_account"]
            if "gl_account" in sidecar
            else pd.Series([None] * len(sidecar))
        )
        keep = ref.notna() | (
            account.astype("string").str.strip() == _DEFAULT_UF_ACCOUNT_NAME
        )
        sidecar = sidecar[keep.fillna(False)]
        if sidecar.empty:
            return None

    logger.info(
        "sidecar_extracted",
        extra={
            "file_type": file_type,
            "columns": sorted(out.keys()),
            "rows": int(len(sidecar)),
        },
    )
    return sidecar
