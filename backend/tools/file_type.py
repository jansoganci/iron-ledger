"""Filename → SourceFileType. Shared so mapping and the close checklist cannot drift.

Needles stay conservative: a bank/processor file that also looks like a vendor
file must keep today's mapping behaviour. Grouping (tie-out summary) treats
unmatched names as "other", not as vendors.
"""

from __future__ import annotations

from pathlib import Path

FILE_TYPE_PATTERNS: dict[str, list[str]] = {
    "general_ledger": [
        "gl",
        "general_ledger",
        "quickbooks",
        "qb",
        "gl_export",
        "ledger",
    ],
    "payroll": ["payroll", "salary", "salaries", "wages", "gusto", "adp", "rippling"],
    "contracts": ["contract", "subscription", "recurring", "roster", "customer"],
    "supplier_invoices": ["invoice", "supplier", "vendor", "purchase", "bill", "ap"],
    # Item 1. Deliberately LAST: on overlap the pre-existing types win.
    # Bare "statement" is not a needle (would capture income_statement).
    # "deposit_account" rather than "deposit" so customer-deposit files stay.
    "bank_statement": ["bank", "bank_statement", "checking", "deposit_account"],
    "processor_settlement": [
        "stripe",
        "shopify_payout",
        "paypal",
        "square",
        "processor",
        "settlement",
        "payout",
    ],
}


def _stem(filename: str) -> str:
    name = Path(filename).name
    return name.lower().replace("-", "_").replace(" ", "_").split(".")[0]


def match_file_type(filename: str) -> str | None:
    """First matching SourceFileType, or None when no needle hits."""
    stem = _stem(filename)
    for file_type, patterns in FILE_TYPE_PATTERNS.items():
        if any(p in stem for p in patterns):
            return file_type
    return None


def detect_file_type(filename: str) -> str:
    """Infer SourceFileType from the filename stem — no user input required.

    Unmatched names fall back to supplier_invoices. That is the mapping-path
    contract; checklist grouping uses match_file_type instead.
    """
    matched = match_file_type(filename)
    return matched if matched is not None else "supplier_invoices"
