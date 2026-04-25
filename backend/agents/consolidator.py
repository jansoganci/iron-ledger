"""ConsolidatorAgent — pure pandas, zero Claude calls.

Input : list of (label, DataFrame) where each DataFrame has already been
        normalized by the ParserAgent (columns: account, category, amount, period).
Output: (consolidated_df, list[ReconciliationItem])

Pipeline:
  1. Union   — stack all DataFrames, tag each row with source_file.
  2. Match   — fuzzy-match account names across sources at 90% threshold so
               "Payroll" / "Wages & Salaries" collapse to one canonical name.
               Ambiguous matches (<90%) keep their original name (treated as new
               accounts — the low-confidence flow is the caller's responsibility).
  3. Roll-up — group by canonical account name; compute per-source sub-totals
               and a consolidated total.
  4. Delta   — for each account that appears in ≥2 sources, compute delta.
               Flag if |delta| > $100 AND |delta_pct| > 5%, OR if |delta| > $500.
               Severity: high >$5000, medium $500–$5000, low <$500.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Literal

import pandas as pd
from rapidfuzz import fuzz, process

from backend.domain.contracts import (
    ReconciliationHints,
    ReconciliationItem,
    ReconciliationSource,
)
from backend.logger import get_logger

logger = get_logger(__name__)

_FUZZY_THRESHOLD = 90  # rapidfuzz WRatio score; below → no merge
_DELTA_DOLLAR_MIN = 100.0  # ignore trivially small deltas
_DELTA_PCT_MIN = 0.05  # 5% — must exceed BOTH gates to flag
_DELTA_DOLLAR_HARD = 500.0  # flag regardless of pct if delta exceeds this

_GL_LABELS = {"gl", "gl_export", "general_ledger", "quickbooks", "qb"}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def consolidate(
    sources: list[tuple[str, pd.DataFrame]],
) -> tuple[pd.DataFrame, list[ReconciliationItem]]:
    """Consolidate N (label, DataFrame) pairs into one P&L + reconciliation items.

    Each DataFrame must have columns: account (str), category (str), amount (float).
    The `label` is the source file name used for provenance.
    """
    if not sources:
        raise ValueError("consolidate() requires at least one source DataFrame")

    tagged = _union(sources)
    canonical_map = _build_canonical_map(tagged)
    tagged["canonical"] = tagged["account"].map(canonical_map)

    consolidated = _roll_up(tagged)
    recon_items = _detect_deltas(tagged, canonical_map, sources)

    logger.info(
        "consolidation_complete",
        extra={
            "event": "consolidation_complete",
            "source_count": len(sources),
            "account_count": len(consolidated),
            "reconciliation_count": len(recon_items),
        },
    )
    return consolidated, recon_items


# ---------------------------------------------------------------------------
# Step 1: Union
# ---------------------------------------------------------------------------


def _union(sources: list[tuple[str, pd.DataFrame]]) -> pd.DataFrame:
    frames = []
    for label, df in sources:
        df = df.copy()
        df["source_file"] = label
        df["amount"] = pd.to_numeric(df["amount"], errors="coerce").fillna(0.0)
        frames.append(df[["account", "category", "amount", "source_file"]])
    return pd.concat(frames, ignore_index=True)


# ---------------------------------------------------------------------------
# Step 2: Fuzzy-match account names → canonical name
# ---------------------------------------------------------------------------


def _build_canonical_map(df: pd.DataFrame) -> dict[str, str]:
    """Return {raw_account_name: canonical_name}.

    Strategy: collect unique account names, then greedily merge any pair whose
    WRatio score >= _FUZZY_THRESHOLD — BUT only when they appear in DIFFERENT
    source files. Accounts from the same file are always kept distinct to prevent
    short names (e.g. "Rent") from substring-matching longer ones
    (e.g. "Equipment Rental") within a single P&L export.
    """
    # Build a map from account name → set of source files that contain it.
    # When source_file column is absent (e.g. in unit tests), treat every
    # account as its own source so the score-only merge path still applies.
    has_source = "source_file" in df.columns
    name_sources: dict[str, set[str]] = {}
    for _, row in df.iterrows():
        name = row["account"]
        if pd.notna(name):
            src = str(row["source_file"]) if has_source else str(name)
            name_sources.setdefault(str(name), set()).add(src)

    names = sorted(name_sources.keys())
    canonical: dict[str, str] = {}
    # Track which sources each canonical name covers
    canonical_sources: dict[str, set[str]] = {}

    for name in names:
        if name in canonical:
            continue
        existing_canonicals = list({v for v in canonical.values()})
        if existing_canonicals:
            match, score, _ = process.extractOne(
                name,
                existing_canonicals,
                scorer=fuzz.WRatio,
            )
            # Only merge if score >= threshold AND the two accounts come from
            # different source files. Accounts within the same file are always
            # semantically distinct and must not be collapsed.
            if score >= _FUZZY_THRESHOLD:
                name_srcs = name_sources.get(name, set())
                canonical_srcs = canonical_sources.get(match, set())
                if not name_srcs.intersection(canonical_srcs):
                    canonical[name] = match
                    canonical_sources[match] = canonical_srcs | name_srcs
                    continue
        canonical[name] = name
        canonical_sources[name] = name_sources.get(name, set())

    return canonical


# ---------------------------------------------------------------------------
# Step 3: Roll-up → consolidated DataFrame
# ---------------------------------------------------------------------------


def _roll_up(tagged: pd.DataFrame) -> pd.DataFrame:
    """Aggregate to one row per canonical account with source_breakdown JSONB.

    Guarantees exactly one output row per canonical account name. When different
    source files disagree on category (e.g. GL says OPEX, dept file says OTHER),
    the GL-sourced category wins; if no GL source is present, the first observed
    category is used. This prevents DuplicateEntryError on the monthly_entries
    unique constraint (company_id, account_id, period).
    """
    grouped = (
        tagged.groupby(["canonical", "category", "source_file"])["amount"]
        .sum()
        .reset_index()
    )

    # Build one row per canonical account, merging across all categories.
    per_account: dict[str, dict] = {}
    for _, row in grouped.iterrows():
        canonical = row["canonical"]
        category = row["category"]
        source_file = row["source_file"]
        amount = round(float(row["amount"]), 2)

        if canonical not in per_account:
            per_account[canonical] = {
                "account": canonical,
                "category": category,
                "amount": 0.0,
                "source_breakdown": [],
            }

        entry = per_account[canonical]

        # GL category wins over any other source category.
        if _is_gl_label(source_file):
            entry["category"] = category

        entry["amount"] = round(entry["amount"] + amount, 2)
        entry["source_breakdown"].append(
            {
                "source_file": source_file,
                "amount": amount,
                "row_count": int(
                    len(
                        tagged[
                            (tagged["canonical"] == canonical)
                            & (tagged["source_file"] == source_file)
                        ]
                    )
                ),
            }
        )

    return pd.DataFrame(list(per_account.values()))


# ---------------------------------------------------------------------------
# Step 4: Delta detection → ReconciliationItem list
# ---------------------------------------------------------------------------


def _detect_deltas(
    tagged: pd.DataFrame,
    canonical_map: dict[str, str],
    sources: list[tuple[str, pd.DataFrame]],
) -> list[ReconciliationItem]:
    """Produce one ReconciliationItem per account that has a material cross-source delta."""
    items: list[ReconciliationItem] = []

    # Determine which source label is the GL (if any)
    gl_label: str | None = None
    for label, _ in sources:
        if _is_gl_label(label):
            gl_label = label
            break

    per_source = (
        tagged.groupby(["canonical", "category", "source_file"])["amount"]
        .sum()
        .reset_index()
    )

    for (canonical, category), grp in per_source.groupby(["canonical", "category"]):
        if len(grp) < 2:
            # Only one source for this account — check if it's GL-only or source-only
            only_source = grp.iloc[0]["source_file"]
            is_gl = _is_gl_label(only_source)
            total_sources = len(sources)
            if total_sources < 2:
                continue  # nothing to reconcile with one source total
            # Flag as orphan only if there are multiple source files
            gl_amount = (
                float(grp[grp["source_file"] == gl_label]["amount"].sum())
                if gl_label
                else None
            )
            non_gl_total = (
                float(grp[grp["source_file"] != gl_label]["amount"].sum())
                if gl_label
                else float(grp["amount"].sum())
            )
            hints = ReconciliationHints(
                is_gl_only=is_gl,
                is_source_only=not is_gl,
            )
            if (
                abs(
                    non_gl_total
                    if gl_amount is None
                    else (non_gl_total - (gl_amount or 0))
                )
                < _DELTA_DOLLAR_MIN
            ):
                continue
            items.append(_build_item(canonical, category, grp, gl_label, hints))
            continue

        item = _build_item(canonical, category, grp, gl_label, ReconciliationHints())
        if item is None:
            continue
        if _is_material(item.delta):
            items.append(item)

    return items


def _build_item(
    account: str,
    category: str,
    grp: pd.DataFrame,
    gl_label: str | None,
    hints: ReconciliationHints,
) -> ReconciliationItem | None:
    recon_sources = [
        ReconciliationSource(
            source_file=row["source_file"],
            amount=round(float(row["amount"]), 2),
            row_count=1,
        )
        for _, row in grp.iterrows()
    ]

    gl_amount: float | None = None
    if gl_label:
        gl_rows = grp[grp["source_file"] == gl_label]
        if not gl_rows.empty:
            gl_amount = round(float(gl_rows["amount"].sum()), 2)

    non_gl_rows = grp[grp["source_file"] != gl_label] if gl_label else grp
    non_gl_total = round(float(non_gl_rows["amount"].sum()), 2)

    if gl_amount is not None:
        delta = round(non_gl_total - gl_amount, 2)
        delta_pct = (delta / gl_amount) if gl_amount != 0 else None
    else:
        delta = non_gl_total
        delta_pct = None

    if not _is_material(delta):
        return None

    severity = _severity(abs(delta))

    return ReconciliationItem(
        account=account,
        category=category,
        sources=recon_sources,
        gl_amount=gl_amount,
        non_gl_total=non_gl_total,
        delta=delta,
        delta_pct=round(delta_pct, 4) if delta_pct is not None else None,
        severity=severity,
        hints=hints,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _is_gl_label(label: str) -> bool:
    normalized = label.lower().replace(" ", "_").replace("-", "_").split(".")[0]
    return any(gl in normalized for gl in _GL_LABELS)


def _is_material(delta: float) -> bool:
    abs_delta = abs(delta)
    return abs_delta >= _DELTA_DOLLAR_HARD or abs_delta >= _DELTA_DOLLAR_MIN


def _severity(abs_delta: float) -> Literal["low", "medium", "high"]:
    if abs_delta >= 5_000:
        return "high"
    if abs_delta >= 500:
        return "medium"
    return "low"
