"""Python-only tie-out summary used by the close-checklist page."""

from __future__ import annotations

from backend.tools.file_type import detect_file_type, match_file_type
from backend.tools.tie_out_summary import build_tie_out_summary, group_for_item


def test_detect_file_type_fallback_unchanged() -> None:
    assert detect_file_type("mystery_file.xlsx") == "supplier_invoices"
    assert match_file_type("mystery_file.xlsx") is None


def test_redhawk_shaped_summary_payroll_clean_vendor_gap() -> None:
    files = [
        "redhawk_gl_mar_2026.xlsx",
        "redhawk_payroll_mar_2026.xlsx",
        "redhawk_vendor_invoices_mar_2026.xlsx",
        "redhawk_contracts_mar_2026.xlsx",
    ]
    items = [
        {
            "account": "Equipment COGS",
            "card_kind": "exception",
            "hints": {},
            "sources": [
                {"source_file": "redhawk_gl_mar_2026.xlsx", "amount": 1000.0},
                {
                    "source_file": "redhawk_vendor_invoices_mar_2026.xlsx",
                    "amount": 1700.0,
                },
            ],
        },
        {
            "account": "Rent",
            "card_kind": "coverage",
            "hints": {"is_gl_only": True},
            "sources": [{"source_file": "redhawk_gl_mar_2026.xlsx", "amount": 3200.0}],
        },
    ]
    summary = build_tie_out_summary(files, items)
    by_key = {g["key"]: g for g in summary["groups"]}
    assert by_key["payroll"]["status"] == "clean"
    assert by_key["supplier_invoices"]["status"] == "gap"
    assert by_key["contracts"]["status"] == "clean"
    assert "other" not in by_key
    assert summary["compared"] == 3
    assert summary["with_gap"] == 1
    assert summary["not_compared"] == 1


def test_coverage_is_not_a_gap_group() -> None:
    item = {
        "account": "Rent",
        "card_kind": "coverage",
        "hints": {"is_gl_only": True},
        "sources": [{"source_file": "redhawk_gl_mar_2026.xlsx", "amount": 3200.0}],
    }
    assert group_for_item(item) is None
    summary = build_tie_out_summary(["redhawk_gl_mar_2026.xlsx"], [item])
    assert summary["groups"] == []
    assert summary["not_compared"] == 1
    assert summary["compared"] == 0


def test_unknown_and_cash_files_land_in_other() -> None:
    files = ["mystery_pack.xlsx", "stripe_payouts_mar.csv"]
    items = [
        {
            "account": "Undeposited Funds",
            "card_kind": "exception",
            "hints": {},
            "sources": [
                {"source_file": "stripe_payouts_mar.csv", "amount": 100.0},
            ],
        }
    ]
    summary = build_tie_out_summary(files, items)
    assert [g["key"] for g in summary["groups"]] == ["other"]
    assert summary["groups"][0]["status"] == "gap"


def test_vendor_gap_still_appears_under_vendors() -> None:
    item = {
        "account": "Equipment COGS",
        "card_kind": "exception",
        "hints": {},
        "sources": [
            {"source_file": "redhawk_vendor_invoices_mar_2026.xlsx", "amount": 1.0},
        ],
    }
    assert group_for_item(item) == "supplier_invoices"


def test_payroll_and_vendor_exception_cards_land_in_two_groups() -> None:
    payroll = {
        "account": "Wages",
        "card_kind": "exception",
        "hints": {},
        "sources": [
            {"source_file": "redhawk_payroll_mar_2026.xlsx", "amount": 10.0},
        ],
    }
    vendor = {
        "account": "Equipment COGS",
        "card_kind": "exception",
        "hints": {},
        "sources": [
            {"source_file": "redhawk_vendor_invoices_mar_2026.xlsx", "amount": 1.0},
        ],
    }
    assert group_for_item(payroll) == "payroll"
    assert group_for_item(vendor) == "supplier_invoices"
    summary = build_tie_out_summary(
        [
            "redhawk_payroll_mar_2026.xlsx",
            "redhawk_vendor_invoices_mar_2026.xlsx",
        ],
        [payroll, vendor],
    )
    by_key = {g["key"]: g for g in summary["groups"]}
    assert by_key["payroll"]["status"] == "gap"
    assert by_key["supplier_invoices"]["status"] == "gap"
    assert summary["compared"] == 2
