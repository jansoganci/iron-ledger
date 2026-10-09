"""Book-only YTD amounts, with no LLM or external services."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from backend.domain.entities import MonthlyEntry
from backend.tools.ytd_summary import build_ytd_summary


def _entry(
    month: int,
    account: str,
    amount: str,
    *,
    source: str = "gl.xlsx",
    breakdown: list[dict] | None = None,
) -> MonthlyEntry:
    return MonthlyEntry(
        id=f"{month}-{account}-{source}",
        company_id="company-1",
        account_id=account,
        period=date(2026, month, 1),
        actual_amount=Decimal(amount),
        source_file=source,
        source_breakdown=breakdown,
    )


ACCOUNTS = {
    "rev": {"category": "REVENUE"},
    "other-income": {"category": "OTHER_INCOME"},
    "cogs": {"category": "COGS"},
    "opex": {"category": "OPEX"},
    "rnd": {"category": "R&D"},
    "ga": {"category": "G&A"},
    "other": {"category": "OTHER"},
}


def test_empty_year_and_source_only_year_have_no_book_months() -> None:
    assert build_ytd_summary([], ACCOUNTS, 2026)["totals"] is None
    result = build_ytd_summary(
        [_entry(3, "rev", "100.00", source="contracts.xlsx")],
        ACCOUNTS,
        2026,
        through_month=3,
    )
    assert result["last_loaded_month"] is None
    assert result["totals"] is None
    assert [month["values"] for month in result["months"]] == [None] * 3


def test_single_month_uses_book_amount_and_decimal_arithmetic() -> None:
    entries = [
        _entry(
            3,
            "rev",
            "100.10",
            source="vendor.xlsx",
            breakdown=[
                {"source_file": "gl.xlsx", "amount": 100.10},
                {"source_file": "vendor.xlsx", "amount": 150.00},
            ],
        ),
        _entry(3, "rev", "0.20"),
        _entry(3, "other-income", "4.00"),
        _entry(3, "cogs", "40.00"),
        _entry(3, "opex", "10.00"),
        _entry(3, "rnd", "2.00"),
        _entry(3, "ga", "5.00"),
        _entry(3, "other", "7.00"),
        _entry(3, "cogs", "80.00", source="vendor.xlsx"),
    ]
    result = build_ytd_summary(entries, ACCOUNTS, 2026)

    assert result["through_month"] == 3
    assert result["months"][0]["values"] is None
    assert result["months"][1]["values"] is None
    assert result["months"][2]["values"] == {
        "revenue": 104.30,
        "cogs": 40.0,
        "gross_profit": 64.30,
        "operating_expenses": 12.0,
        "general_administrative": 5.0,
        "net_profit": 47.30,
    }
    assert result["totals"] == result["months"][2]["values"]
    assert result["has_unclassified_accounts"] is True


def test_missing_month_is_blank_and_ytd_skips_it() -> None:
    entries = [
        _entry(1, "rev", "100.00"),
        _entry(3, "rev", "300.00"),
        _entry(3, "cogs", "90.00"),
    ]
    result = build_ytd_summary(entries, ACCOUNTS, 2026)

    assert result["months"][1] == {"month": 2, "values": None}
    assert result["months"][2]["values"]["revenue"] == 300.0
    assert result["totals"]["revenue"] == 400.0
    assert result["totals"]["net_profit"] == 310.0


def test_zero_book_month_is_zero_not_missing() -> None:
    result = build_ytd_summary([_entry(2, "rev", "0.00")], ACCOUNTS, 2026)
    assert result["months"][0]["values"] is None
    assert result["months"][1]["values"]["revenue"] == 0.0
    assert result["totals"]["net_profit"] == 0.0


def test_selected_month_limits_and_extends_past_last_upload() -> None:
    entries = [_entry(1, "rev", "100.00"), _entry(3, "rev", "300.00")]
    february = build_ytd_summary(entries, ACCOUNTS, 2026, through_month=2)
    april = build_ytd_summary(entries, ACCOUNTS, 2026, through_month=4)

    assert february["totals"]["revenue"] == 100.0
    assert february["last_loaded_month"] == 3
    assert april["months"][3]["values"] is None
    assert april["totals"]["revenue"] == 400.0


def test_full_year_has_twelve_months_and_twelve_month_total() -> None:
    result = build_ytd_summary(
        [_entry(month, "rev", "10.00") for month in range(1, 13)],
        ACCOUNTS,
        2026,
    )
    assert len(result["months"]) == 12
    revenues = [month["values"]["revenue"] for month in result["months"]]
    assert revenues == [10.0] * 12
    assert result["totals"]["revenue"] == 120.0
