"""Deterministic book-only monthly and year-to-date P&L summary."""

from __future__ import annotations

from collections import defaultdict
from decimal import Decimal
from pathlib import Path

from backend.domain.entities import MonthlyEntry
from backend.tools.file_type import match_file_type

ZERO = Decimal("0.00")
REVENUE_CATEGORIES = frozenset({"REVENUE", "OTHER_INCOME"})
OPERATING_CATEGORIES = frozenset({"OPEX", "R&D"})


def _is_book_entry(entry: MonthlyEntry) -> bool:
    """Prefer persisted source evidence; fall back to old source_file."""
    breakdown = entry.source_breakdown
    if breakdown:
        return any(
            isinstance(source, dict)
            and match_file_type(str(source.get("source_file") or ""))
            == "general_ledger"
            for source in breakdown
        )
    source_name = Path(entry.source_file or "").name
    return match_file_type(source_name) == "general_ledger"


def _line_values(amounts: dict[str, Decimal]) -> dict[str, float]:
    revenue = sum((amounts.get(cat, ZERO) for cat in REVENUE_CATEGORIES), ZERO)
    cogs = amounts.get("COGS", ZERO)
    operating_parts = (amounts.get(cat, ZERO) for cat in OPERATING_CATEGORIES)
    operating = sum(operating_parts, ZERO)
    general = amounts.get("G&A", ZERO)
    gross_profit = revenue - cogs
    return {
        "revenue": float(revenue),
        "cogs": float(cogs),
        "gross_profit": float(gross_profit),
        "operating_expenses": float(operating),
        "general_administrative": float(general),
        "net_profit": float(gross_profit - operating - general),
    }


def build_ytd_summary(
    entries: list[MonthlyEntry],
    accounts_by_id: dict[str, dict],
    year: int,
    through_month: int | None = None,
) -> dict:
    """Return monthly values and YTD totals; absent GL months remain null.

    The period's consolidated entry already uses the GL amount when both a GL
    and supporting file name the same account. Source-only entries are excluded
    when building this book summary, even if they appear in the Data detail.
    """
    by_month: dict[int, dict[str, Decimal]] = defaultdict(
        lambda: defaultdict(lambda: ZERO)
    )
    for entry in entries:
        if entry.period.year != year or not _is_book_entry(entry):
            continue
        account = accounts_by_id.get(entry.account_id, {})
        category = account.get("category") or "OTHER"
        by_month[entry.period.month][category] += entry.actual_amount

    last_loaded_month = max(by_month, default=None)
    end_month = through_month
    if end_month is None:
        end_month = last_loaded_month
    if end_month is None:
        return {
            "through_month": None,
            "last_loaded_month": None,
            "months": [],
            "totals": None,
            "has_unclassified_accounts": False,
        }

    months = []
    totals: dict[str, Decimal] = defaultdict(lambda: ZERO)
    has_unclassified = False
    has_loaded_month = False
    for month in range(1, end_month + 1):
        amounts = by_month.get(month)
        if amounts is None:
            months.append({"month": month, "values": None})
            continue
        has_loaded_month = True
        has_unclassified |= amounts.get("OTHER", ZERO) != ZERO
        for category, amount in amounts.items():
            totals[category] += amount
        months.append({"month": month, "values": _line_values(amounts)})

    return {
        "through_month": end_month,
        "last_loaded_month": last_loaded_month,
        "months": months,
        "totals": _line_values(totals) if has_loaded_month else None,
        "has_unclassified_accounts": has_unclassified,
    }
