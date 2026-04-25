from __future__ import annotations

import re
from datetime import date

import pandas as pd

from backend.domain.contracts import (
    DiscoveryPlan,
    DropReason,
    NormalizerDropReport,
)
from backend.logger import get_logger, get_trace_id
from backend.tools.pii_sanitizer import _scrub_value

_ACCOUNT_SNIPPET_MAX = 40

logger = get_logger(__name__)

# Strips a QBO/NetSuite-style account-code prefix: "5000 - Component Costs",
# "4100 — AgroScan A1", "123-Freight In". Keeps the trailing name.
_ACCOUNT_CODE_RE = re.compile(r"^\s*(\d{3,6})\s*[-–—]\s*(.+?)\s*$")

# Safety-net subtotal detector. Runs AFTER Discovery's skip_row_indices drop,
# catching any "Total Revenue" / "Gross Profit" / "Net Income" / "% Margin"
# row a flaky plan leaves behind. Conservative: start-of-string markers only
# so legitimate accounts like "Total Access LLC" would survive — but our
# Golden Schema has no such account today. If false-positive surfaces later,
# narrow the regex.
_SUBTOTAL_RE = re.compile(
    r"^\s*(total|gross|net)\b|.*%\s*$",
    re.IGNORECASE,
)

_GOLDEN_FIELDS = {
    "account",
    "account_code",
    "amount",
    "date",
    "parent_category",
    "department",
    "description",
}


def _build_snippet(raw_value) -> str:
    """PII-scrub a row's account cell, then truncate to 40 chars.

    ORDER IS LOAD-BEARING: scrub first, truncate second. Reversing would
    let a truncated prefix of a PII match (e.g. "alice@" with no TLD)
    escape the email regex. See test_scrub_before_truncate_invariant.
    """
    if raw_value is None or (isinstance(raw_value, float) and pd.isna(raw_value)):
        return ""
    return _scrub_value(str(raw_value))[:_ACCOUNT_SNIPPET_MAX]


def apply_plan(
    df_raw: pd.DataFrame,
    plan: DiscoveryPlan,
    period: date,
) -> tuple[pd.DataFrame, NormalizerDropReport]:
    """Deterministically transform a raw DataFrame into Golden Schema shape.

    Pure Python. No LLM calls. No network I/O. Given the same inputs,
    returns the same (DataFrame, NormalizerDropReport) pair every time.

    Sequence:
      1. Drop rows in plan.skip_row_indices.
      2. Promote plan.header_row_index as the column header.
      3. Rename columns per plan.column_mapping; drop None-mapped columns.
      4. Parse "NNNN - Name" prefix into account_code + account.
      5. Attach parent_category from plan.hierarchy_hints (hints win only if
         no explicit parent_category column was mapped).
      6. Inject date = period (uniform; matches monthly_entries.period).
      7. Ensure all optional Golden Schema columns exist as None.
      8. Coerce amount to float; drop rows where coercion fails → drop report.
      9. Safety-net: drop subtotal regex matches → drop report.

    The DropReport surfaces rows the Normalizer dropped (NOT rows that were
    already in plan.skip_row_indices — those are Discovery's intentional
    skips). Each entry carries the original file row_index and a PII-scrubbed
    40-char account_snippet so the frontend can show "what got dropped"
    without leaking cell values.
    """
    trace_id = get_trace_id()
    drop_entries: list[DropReason] = []

    # --- 1. Drop skip rows (metadata, banners, subtotals identified by Discovery)
    skip = set(plan.skip_row_indices)
    df = df_raw.copy()
    df["_orig_row_index"] = df.index
    df = df[~df["_orig_row_index"].isin(skip)].copy()

    # --- 2. Promote header row
    header_idx = plan.header_row_index
    if header_idx in df["_orig_row_index"].values:
        header_row = df.loc[df["_orig_row_index"] == header_idx].iloc[0]
        header_values = [
            str(v) if v is not None and not pd.isna(v) else f"col_{i}"
            for i, v in enumerate(header_row.drop("_orig_row_index").tolist())
        ]
        df = df[df["_orig_row_index"] > header_idx].copy()
        df.columns = header_values + ["_orig_row_index"]
    # If header row was itself in skip_row_indices or missing from df, we
    # assume Discovery already excluded it and df.columns are already correct.

    # --- 3. Rename columns per column_mapping; drop None-mapped columns
    rename_map: dict[str, str] = {}
    drop_cols: list[str] = []
    _claimed_targets: set[str] = set()
    for src, target in plan.column_mapping.items():
        if src not in df.columns:
            continue
        if target is None:
            drop_cols.append(src)
        elif target in _GOLDEN_FIELDS:
            if target in _claimed_targets:
                # Second column claiming the same Golden field — drop to avoid
                # duplicate column names that break pd.to_numeric / pandera.
                drop_cols.append(src)
            else:
                rename_map[src] = target
                _claimed_targets.add(target)
    if drop_cols:
        df = df.drop(columns=drop_cols)
    if rename_map:
        df = df.rename(columns=rename_map)

    # Discard any file columns Discovery didn't mention — keeps strict=True clean
    known = _GOLDEN_FIELDS | {"_orig_row_index"}
    extra = [c for c in df.columns if c not in known]
    if extra:
        df = df.drop(columns=extra)

    # --- 4. Parse account-code prefix
    if "account" in df.columns:
        parsed = df["account"].astype(str).str.extract(_ACCOUNT_CODE_RE)
        has_code = parsed[0].notna()
        if "account_code" not in df.columns:
            df["account_code"] = None
        df.loc[has_code, "account_code"] = parsed.loc[has_code, 0]
        df.loc[has_code, "account"] = parsed.loc[has_code, 1]

    # --- 5. Attach parent_category from hierarchy_hints
    if plan.hierarchy_hints:
        hint_map = {h.row_index: h.parent_category for h in plan.hierarchy_hints}
        if "parent_category" in df.columns:
            # Explicit column already mapped — hints only fill gaps
            explicit = df["parent_category"]
            filled = df["_orig_row_index"].map(hint_map)
            df["parent_category"] = explicit.where(explicit.notna(), filled)
        else:
            df["parent_category"] = df["_orig_row_index"].map(hint_map)

    # --- 6. Inject date uniformly, preserving original dates where present.
    # If Discovery mapped a source date column (e.g. "Invoice Date", "Payout Date")
    # to the canonical "date" field, keep those values — they may be future-dated
    # (e.g. April payout for a March transaction) which hint_computer needs to detect
    # crosses_period_boundary. Only fill missing/null dates with the period default.
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], errors="coerce").fillna(
            pd.to_datetime(period)
        )
    else:
        df["date"] = pd.to_datetime(period)

    # --- 7. Ensure all optional Golden Schema columns exist
    for optional in (
        "account_code",
        "parent_category",
        "department",
        "description",
    ):
        if optional not in df.columns:
            df[optional] = None

    # --- 8. Coerce amount to float; drop bad rows
    if "amount" not in df.columns:
        # Discovery contract requires this; _semantic_validate caught it, but
        # defence-in-depth: don't emit a malformed frame.
        raise ValueError("Normalizer: 'amount' column missing after mapping")

    coerced = pd.to_numeric(df["amount"], errors="coerce")
    bad = coerced.isna() & df["amount"].notna()
    if bad.any():
        bad_df = df.loc[bad]
        for _, row in bad_df.iterrows():
            drop_entries.append(
                DropReason(
                    row_index=int(row["_orig_row_index"]),
                    account_snippet=_build_snippet(row.get("account")),
                    reason="amount_coerce_failed",
                )
            )
        logger.info(
            "normalizer dropped uncoercible amount rows",
            extra={
                "event": "normalizer_amount_coerce_drop",
                "trace_id": trace_id,
                "row_indices": bad_df["_orig_row_index"].tolist(),
                "count": int(bad.sum()),
            },
        )
    df = df.loc[~bad].copy()
    df["amount"] = pd.to_numeric(df["amount"], errors="coerce")
    df = df.loc[df["amount"].notna()].copy()

    # --- 9. Safety-net subtotal filter
    subtotal_mask = df["account"].astype(str).str.match(_SUBTOTAL_RE)
    if subtotal_mask.any():
        caught_df = df.loc[subtotal_mask]
        for _, row in caught_df.iterrows():
            drop_entries.append(
                DropReason(
                    row_index=int(row["_orig_row_index"]),
                    account_snippet=_build_snippet(row.get("account")),
                    reason="subtotal_safety_net",
                )
            )
        logger.warning(
            "normalizer caught subtotal rows missed by Discovery",
            extra={
                "event": "normalizer_subtotal_safety_net",
                "trace_id": trace_id,
                "row_indices": caught_df["_orig_row_index"].tolist(),
                "count": int(subtotal_mask.sum()),
            },
        )
        df = df.loc[~subtotal_mask].copy()

    # Drop provenance helper, return canonical column order
    df = df.drop(columns=["_orig_row_index"])
    ordered = [
        "account",
        "account_code",
        "amount",
        "date",
        "parent_category",
        "department",
        "description",
    ]
    out_df = df[ordered].reset_index(drop=True)
    report = NormalizerDropReport(
        entries=drop_entries,
        total_dropped=len(drop_entries),
    )
    return out_df, report
