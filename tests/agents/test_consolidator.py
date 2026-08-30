"""Unit tests for ConsolidatorAgent.

Tests use two hand-crafted DataFrames — one "GL export" and one "department
payroll sheet" — to verify union, fuzzy match, roll-up, and delta detection
without touching any database or LLM.
"""

from __future__ import annotations

import pandas as pd
import pytest

from backend.agents.consolidator import (
    _build_canonical_map,
    _is_gl_label,
    _is_material,
    _severity,
    consolidate,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _gl_df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "account": [
                "Revenue",
                "Payroll",
                "Supplier Invoices",
                "Vehicle Expenses",
            ],
            "category": ["REVENUE", "OPEX", "COGS", "OPEX"],
            "amount": [3825.0, 44900.0, 36100.0, 2100.0],
        }
    )


def _payroll_df() -> pd.DataFrame:
    """Department payroll sheet — same account name as GL, different amount.

    Delta: $44,200 dept vs $44,900 GL → $700 gap (categorical misclassification
    in the GL where one bonus landed in Contractors instead of Payroll).
    Fuzzy matching handles minor formatting variants (e.g. "Payroll" vs
    "Payroll Expenses"), NOT semantically different terms like "Wages & Salaries".
    """
    return pd.DataFrame(
        {
            "account": ["Payroll", "Service Contracts"],
            "category": ["OPEX", "REVENUE"],
            "amount": [44200.0, 3540.0],
        }
    )


def _supplier_df() -> pd.DataFrame:
    """Supplier invoices file — matches 'Supplier Invoices' in GL but differs."""
    return pd.DataFrame(
        {
            "account": ["Supplier Invoices"],
            "category": ["COGS"],
            "amount": [37800.0],  # GL shows 36100 → $1700 gap
        }
    )


# ---------------------------------------------------------------------------
# _is_gl_label
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "label,expected",
    [
        ("gl_export.xlsx", True),
        ("GL_Export_March.xlsx", True),
        ("quickbooks_march.xlsx", True),
        ("payroll_march.xlsx", False),
        ("supplier_invoices.xlsx", False),
        ("bank_statement.csv", False),
    ],
)
def test_is_gl_label(label: str, expected: bool) -> None:
    assert _is_gl_label(label) == expected


# ---------------------------------------------------------------------------
# _build_canonical_map — fuzzy matching
# ---------------------------------------------------------------------------


def test_canonical_map_exact_merge() -> None:
    df = pd.DataFrame({"account": ["Payroll", "Payroll"]})
    mapping = _build_canonical_map(df)
    assert mapping["Payroll"] == "Payroll"
    assert len(set(mapping.values())) == 1


def test_canonical_map_fuzzy_merge() -> None:
    """Minor formatting variants should merge at >= 90% WRatio.

    90% threshold catches typos and trailing-word variants, not semantically
    different terms (e.g. "Payroll" vs "Wages & Salaries" won't merge — that
    requires a domain synonym table, which is post-MVP).
    """
    df = pd.DataFrame({"account": ["Payroll", "Payroll Expenses"]})
    mapping = _build_canonical_map(df)
    assert mapping["Payroll"] == mapping["Payroll Expenses"]


def test_canonical_map_no_merge_on_unrelated() -> None:
    df = pd.DataFrame({"account": ["Revenue", "Supplier Invoices", "Payroll"]})
    mapping = _build_canonical_map(df)
    # All three are distinct — no merging
    assert len(set(mapping.values())) == 3


# ---------------------------------------------------------------------------
# consolidate() — two-source scenario (GL + payroll)
# ---------------------------------------------------------------------------


def test_consolidate_produces_consolidated_df() -> None:
    consolidated, _ = consolidate(
        [("gl_export.xlsx", _gl_df()), ("payroll_march.xlsx", _payroll_df())]
    )
    assert isinstance(consolidated, pd.DataFrame)
    assert "account" in consolidated.columns
    assert "amount" in consolidated.columns
    assert "source_breakdown" in consolidated.columns
    assert len(consolidated) > 0


def test_consolidate_payroll_delta_flagged() -> None:
    """$700 payroll gap between dept sheet and GL must produce a ReconciliationItem."""
    _, recon_items = consolidate(
        [("gl_export.xlsx", _gl_df()), ("payroll_march.xlsx", _payroll_df())]
    )
    payroll_items = [
        r
        for r in recon_items
        if "payroll" in r.account.lower() or "wages" in r.account.lower()
    ]
    assert (
        len(payroll_items) >= 1
    ), "Expected a reconciliation item for the payroll delta"
    item = payroll_items[0]
    assert abs(item.delta) == pytest.approx(700.0, abs=1.0)
    assert item.card_kind == "exception"
    assert item.severity in ("low", "medium", "high")


def test_consolidate_source_breakdown_populated() -> None:
    consolidated, _ = consolidate(
        [("gl_export.xlsx", _gl_df()), ("supplier_invoices.xlsx", _supplier_df())]
    )
    supplier_row = consolidated[consolidated["account"] == "Supplier Invoices"]
    assert not supplier_row.empty
    breakdown = supplier_row.iloc[0]["source_breakdown"]
    assert isinstance(breakdown, list)
    assert len(breakdown) == 2  # one entry per source
    files = {b["source_file"] for b in breakdown}
    assert "gl_export.xlsx" in files
    assert "supplier_invoices.xlsx" in files


def test_consolidate_supplier_delta_flagged() -> None:
    """$1700 supplier gap must be flagged as a reconciliation item."""
    _, recon_items = consolidate(
        [("gl_export.xlsx", _gl_df()), ("supplier_invoices.xlsx", _supplier_df())]
    )
    supplier_items = [r for r in recon_items if "supplier" in r.account.lower()]
    assert len(supplier_items) >= 1
    assert abs(supplier_items[0].delta) == pytest.approx(1700.0, abs=1.0)


def test_consolidate_single_source_no_reconciliations() -> None:
    """With only one source, no cross-source reconciliations should be produced."""
    _, recon_items = consolidate([("gl_export.xlsx", _gl_df())])
    assert recon_items == []


# ---------------------------------------------------------------------------
# Materiality helpers
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "delta,delta_pct,expected",
    [
        (50.0, 0.10, False),  # below dollar min
        (100.0, None, False),  # dollar min, no pct (source-only)
        (100.0, 0.01, False),  # $100 and 1%
        (100.0, 0.10, True),  # $100 and 10%
        (100.0, 0.05, False),  # pct must be strictly > 5%
        (400.0, 0.02, False),  # $400 and 2%
        (400.0, 0.20, True),  # $400 and 20%
        (500.0, 0.001, True),  # hard gate ignores pct
        (200.0, -1.0, True),  # GL-only ~100%
        (200.0, None, False),  # source-only under hard gate
        (600.0, None, True),  # source-only hard gate
        (5000.0, 0.0, True),
    ],
)
def test_is_material(
    delta: float, delta_pct: float | None, expected: bool
) -> None:
    assert _is_material(delta, delta_pct) == expected


def test_and_gate_two_sided_100_on_10000_not_flagged() -> None:
    """Pre-analysis case B: GL $10,000 vs $10,100 → 1%, no item."""
    gl = pd.DataFrame(
        {"account": ["Revenue"], "category": ["REVENUE"], "amount": [10_000.0]}
    )
    src = pd.DataFrame(
        {"account": ["Revenue"], "category": ["REVENUE"], "amount": [10_100.0]}
    )
    _, items = consolidate(
        [("gl_export.xlsx", gl), ("dept.xlsx", src)]
    )
    assert items == []


def test_and_gate_gl_only_rent_200_still_flagged() -> None:
    """Pre-analysis case F: GL-only Rent $200 (pct ≈ 100%) still flags."""
    gl = pd.DataFrame(
        {
            "account": ["Rent", "Payroll"],
            "category": ["OPEX", "OPEX"],
            "amount": [200.0, 10_000.0],
        }
    )
    src = pd.DataFrame(
        {"account": ["Payroll"], "category": ["OPEX"], "amount": [10_000.0]}
    )
    _, items = consolidate(
        [("gl_export.xlsx", gl), ("payroll.xlsx", src)]
    )
    rent = [i for i in items if i.account == "Rent"]
    assert len(rent) == 1
    assert rent[0].hints.is_gl_only
    assert rent[0].card_kind == "coverage"
    assert abs(rent[0].delta) == pytest.approx(200.0)


def test_and_gate_source_only_200_not_flagged() -> None:
    """Pre-analysis case G: source-only $200 (pct None) does not flag."""
    gl = pd.DataFrame(
        {"account": ["Payroll"], "category": ["OPEX"], "amount": [10_000.0]}
    )
    src = pd.DataFrame(
        {
            "account": ["Payroll", "Bonus"],
            "category": ["OPEX", "OPEX"],
            "amount": [10_000.0, 200.0],
        }
    )
    _, items = consolidate(
        [("gl_export.xlsx", gl), ("payroll.xlsx", src)]
    )
    bonus = [i for i in items if "bonus" in i.account.lower()]
    assert bonus == []


def test_and_gate_two_sided_400_at_2pct_not_flagged() -> None:
    gl = pd.DataFrame(
        {"account": ["Revenue"], "category": ["REVENUE"], "amount": [20_000.0]}
    )
    src = pd.DataFrame(
        {"account": ["Revenue"], "category": ["REVENUE"], "amount": [20_400.0]}
    )
    _, items = consolidate(
        [("gl_export.xlsx", gl), ("dept.xlsx", src)]
    )
    assert items == []


def test_and_gate_two_sided_400_at_20pct_flagged() -> None:
    gl = pd.DataFrame(
        {"account": ["Revenue"], "category": ["REVENUE"], "amount": [2_000.0]}
    )
    src = pd.DataFrame(
        {"account": ["Revenue"], "category": ["REVENUE"], "amount": [2_400.0]}
    )
    _, items = consolidate(
        [("gl_export.xlsx", gl), ("dept.xlsx", src)]
    )
    assert len(items) == 1
    assert abs(items[0].delta) == pytest.approx(400.0)


def test_and_gate_hard_500_flags_despite_tiny_pct() -> None:
    gl = pd.DataFrame(
        {"account": ["Revenue"], "category": ["REVENUE"], "amount": [500_000.0]}
    )
    src = pd.DataFrame(
        {"account": ["Revenue"], "category": ["REVENUE"], "amount": [500_500.0]}
    )
    _, items = consolidate(
        [("gl_export.xlsx", gl), ("dept.xlsx", src)]
    )
    assert len(items) == 1
    assert abs(items[0].delta) == pytest.approx(500.0)


@pytest.mark.parametrize(
    "abs_delta,expected_severity",
    [
        (400.0, "low"),
        (500.0, "medium"),
        (4999.0, "medium"),
        (5000.0, "high"),
        (50000.0, "high"),
    ],
)
def test_severity(abs_delta: float, expected_severity: str) -> None:
    assert _severity(abs_delta) == expected_severity
