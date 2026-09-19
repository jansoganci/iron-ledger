"""Named close controls — Python-only statuses and counts."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from backend import messages
from backend.tools.close_controls import (
    REPORT_RECON_SCHEMA,
    build_control_summary,
    build_legacy_control_summary,
    pack_report_reconciliations,
    unpack_report_reconciliations,
)
from backend.tools.mapping_grain import (
    is_file_total_candidate,
    proposed_contracts_gl,
    retarget_account_column,
    should_file_total_after_parse,
)
from backend.domain.contracts import DiscoveryPlan

PERIOD = date(2026, 3, 1)
REDHAWK = Path(__file__).resolve().parents[2] / "docs" / "demo_data" / "redhawk"


def _summary(**kwargs):
    defaults = dict(
        period=PERIOD,
        source_files=["gl.xlsx", "payroll.xlsx", "vendor.xlsx", "contracts.xlsx"],
        per_file_rows={},
        gl_amounts={},
        amount_scopes={
            "payroll.xlsx": "Base Compensation",
            "vendor.xlsx": "Amount",
            "contracts.xlsx": "Monthly Fee",
        },
        file_total_mappings={},
        mapping_pending_files=set(),
        recon_items=[],
        empty_files=set(),
        mapping_modes={},
    )
    defaults.update(kwargs)
    return build_control_summary(**defaults)


def test_redhawk_fixture_amounts_are_computed_in_python() -> None:
    payroll = pd.read_excel(REDHAWK / "redhawk_payroll_mar_2026.xlsx")
    vendor = pd.read_excel(REDHAWK / "redhawk_vendor_invoices_mar_2026.xlsx")
    contracts = pd.read_excel(REDHAWK / "redhawk_contracts_mar_2026.xlsx")
    gl = pd.read_excel(REDHAWK / "redhawk_gl_mar_2026.xlsx", header=4)

    by_role = payroll.groupby("Role")["Base Compensation"].sum().to_dict()
    assert by_role["Owner / Operations"] == 5500
    assert by_role["Office Administrator"] == 1400
    tech = (
        by_role["Lead Install Technician"]
        + by_role["Install Technician"]
        + by_role["Service Technician"]
    )
    assert tech == 6200

    by_line = vendor.groupby("Product Line")["Amount"].sum().to_dict()
    assert by_line["Equipment"] == 7200
    assert by_line["Central Station"] == 1105
    assert by_line["Vehicle"] == 1840
    assert by_line["Insurance"] == 1180
    assert by_line["Marketing"] == 780

    active = contracts[contracts["Status"].str.casefold() == "active"].copy()
    assert round(float(active["Monthly Fee"].sum()), 2) == 3825.00
    last = pd.to_datetime(active["Last Billed"])
    billed = active[(last.dt.year == 2026) & (last.dt.month == 3)]
    assert len(active) == 85
    assert len(billed) == 82

    gl_map = {
        str(row["Account"]): float(row["Amount"])
        for _, row in gl.iterrows()
        if pd.notna(row.get("Account")) and pd.notna(row.get("Amount"))
    }
    assert gl_map["Service Revenue"] == 3540
    assert gl_map["Technician Wages"] == 6200
    assert gl_map["Owner Salary"] == 5500
    assert gl_map["Admin Wages"] == 1400
    assert "Monitoring Revenue" not in gl_map


def test_clean_two_sided_comparison_without_exception_card() -> None:
    summary = _summary(
        source_files=["gl.xlsx", "payroll.xlsx"],
        per_file_rows={
            "payroll.xlsx": [
                {"account": "Owner Salary", "amount": 5500.0},
                {"account": "Technician Wages", "amount": 6200.0},
                {"account": "Admin Wages", "amount": 1400.0},
            ]
        },
        gl_amounts={
            "Owner Salary": 5500.0,
            "Technician Wages": 6200.0,
            "Admin Wages": 1400.0,
            "Rent & Utilities": 1650.0,
        },
        mapping_modes={"payroll.xlsx": "row"},
        recon_items=[
            {
                "account": "Rent & Utilities",
                "card_kind": "coverage",
                "hints": {"is_gl_only": True},
            }
        ],
    )
    payroll = next(c for c in summary.controls if c.key == "payroll")
    assert payroll.status == "tied_out"
    assert len(payroll.comparisons) == 3
    assert all(c.complete and c.difference == 0 for c in payroll.comparisons)
    assert summary.compared == 1
    assert summary.with_exceptions == 0
    assert summary.coverage_account_count == 1
    assert summary.not_evaluated == 2


def test_material_discrepancy_attributed_to_contracts() -> None:
    summary = _summary(
        source_files=["gl.xlsx", "contracts.xlsx"],
        per_file_rows={
            "contracts.xlsx": [{"account": "Service Revenue", "amount": 3825.0}]
        },
        gl_amounts={"Service Revenue": 3540.0},
        file_total_mappings={"contracts.xlsx": "Service Revenue"},
        mapping_modes={"contracts.xlsx": "file_total"},
        recon_items=[
            {
                "account": "Service Revenue",
                "card_kind": "exception",
                "classification": "stale_reference",
                "delta": 285.0,
                "sources": [
                    {"source_file": "contracts.xlsx", "amount": 3825.0},
                    {"source_file": "gl.xlsx", "amount": 3540.0},
                ],
            }
        ],
    )
    contracts = next(c for c in summary.controls if c.key == "contracts")
    assert contracts.status == "has_exceptions"
    assert contracts.comparisons[0].difference == 285.0
    assert contracts.comparisons[0].classification == "stale_reference"
    payroll = next(c for c in summary.controls if c.key == "payroll")
    vendors = next(c for c in summary.controls if c.key == "supplier_invoices")
    assert payroll.status == "source_missing"
    assert vendors.status == "source_missing"


def test_missing_source_missing_gl_empty_and_unconfirmed_mapping() -> None:
    missing = _summary(source_files=["gl.xlsx"], per_file_rows={}, gl_amounts={})
    assert all(c.status == "source_missing" for c in missing.controls)

    unconfirmed = _summary(
        source_files=["gl.xlsx", "payroll.xlsx"],
        per_file_rows={"payroll.xlsx": [{"account": "Role", "amount": 100.0}]},
        gl_amounts={"Owner Salary": 5500.0},
        mapping_pending_files={"payroll.xlsx"},
    )
    assert unconfirmed.controls[0].status == "mapping_required"

    empty = _summary(
        source_files=["gl.xlsx", "payroll.xlsx"],
        per_file_rows={"payroll.xlsx": []},
        gl_amounts={"Owner Salary": 5500.0},
        empty_files={"payroll.xlsx"},
        mapping_modes={"payroll.xlsx": "row"},
    )
    assert empty.controls[0].status == "not_compared"
    assert empty.controls[0].incomplete_reason == messages.CONTROL_EMPTY_SOURCE

    no_gl = _summary(
        source_files=["gl.xlsx", "contracts.xlsx"],
        per_file_rows={
            "contracts.xlsx": [{"account": "Service Revenue", "amount": 3825.0}]
        },
        gl_amounts={},
        file_total_mappings={"contracts.xlsx": "Service Revenue"},
        mapping_modes={"contracts.xlsx": "file_total"},
    )
    assert no_gl.controls[2].status == "not_compared"
    assert no_gl.controls[2].incomplete_reason == messages.CONTROL_MISSING_GL


def test_partial_coverage_cannot_pass_the_whole_control() -> None:
    summary = _summary(
        source_files=["gl.xlsx", "payroll.xlsx"],
        per_file_rows={
            "payroll.xlsx": [
                {"account": "Owner Salary", "amount": 5500.0},
                {"account": "Lead Install Technician", "amount": 2400.0},
            ]
        },
        gl_amounts={"Owner Salary": 5500.0},
        mapping_modes={"payroll.xlsx": "row"},
    )
    payroll = summary.controls[0]
    assert payroll.status == "not_compared"
    assert payroll.status != "tied_out"
    complete = [c for c in payroll.comparisons if c.complete]
    incomplete = [c for c in payroll.comparisons if not c.complete]
    assert complete and incomplete


def test_accountless_single_target_is_file_total() -> None:
    # Empty parsed data is no longer treated as proof of a single-target file.
    assert not should_file_total_after_parse("supplier_invoices", [], ["Rent"])
    assert not should_file_total_after_parse(
        "supplier_invoices", ["AlarmTech Industries"], ["Equipment & Parts"]
    )
    assert not is_file_total_candidate(
        "supplier_invoices",
        ["Vendor", "Amount"],
        unique_source_values=["Total"],
    )
    summary = _summary(
        source_files=["gl.xlsx", "invoices.xlsx"],
        per_file_rows={"invoices.xlsx": [{"account": "Insurance", "amount": 1180.0}]},
        gl_amounts={"Insurance": 1180.0},
        file_total_mappings={"invoices.xlsx": "Insurance"},
        mapping_modes={"invoices.xlsx": "file_total"},
        amount_scopes={"invoices.xlsx": "Amount"},
    )
    vendors = next(c for c in summary.controls if c.key == "supplier_invoices")
    assert vendors.status == "tied_out"
    assert vendors.mapping_mode == "file_total"


def test_accountless_multi_target_not_collapsed() -> None:
    assert not should_file_total_after_parse(
        "supplier_invoices",
        ["Equipment", "Insurance", "Marketing"],
        ["Equipment & Parts"],
    )
    assert not is_file_total_candidate(
        "supplier_invoices",
        ["Vendor", "Product Line", "Amount"],
        unique_source_values=["ADI", "Beacon"],
    )
    plan = DiscoveryPlan(
        header_row_index=0,
        skip_row_indices=[],
        column_mapping={"Vendor": "account", "Amount": "amount"},
        hierarchy_hints=[],
        discovery_confidence=0.9,
    )
    updated = retarget_account_column(
        plan, "supplier_invoices", ["Vendor", "Product Line", "Amount"]
    )
    assert updated.column_mapping["Product Line"] == "account"
    assert updated.column_mapping["Vendor"] is None


def test_overlapping_sources_do_not_false_pass() -> None:
    summary = _summary(
        source_files=["gl.xlsx", "payroll.xlsx", "vendor.xlsx"],
        per_file_rows={
            "payroll.xlsx": [{"account": "Technician Wages", "amount": 3000.0}],
            "vendor.xlsx": [{"account": "Technician Wages", "amount": 3200.0}],
        },
        gl_amounts={"Technician Wages": 6200.0},
        mapping_modes={"payroll.xlsx": "row", "vendor.xlsx": "row"},
    )
    payroll = next(c for c in summary.controls if c.key == "payroll")
    vendors = next(c for c in summary.controls if c.key == "supplier_invoices")
    assert payroll.status != "tied_out"
    assert vendors.status != "tied_out"
    assert payroll.status == "not_compared"
    assert vendors.status == "not_compared"


def test_install_fuel_absent_from_successful_counts() -> None:
    summary = _summary(
        source_files=["gl.xlsx", "payroll.xlsx"],
        per_file_rows={"payroll.xlsx": [{"account": "Owner Salary", "amount": 5500.0}]},
        gl_amounts={"Owner Salary": 5500.0, "Installation Revenue": 28400.0},
        mapping_modes={"payroll.xlsx": "row"},
        recon_items=[
            {
                "account": "Installation Revenue",
                "card_kind": "coverage",
                "hints": {"is_gl_only": True},
            },
            {
                "account": "Vehicle & Fuel",
                "card_kind": "coverage",
                "hints": {"is_gl_only": True},
            },
        ],
    )
    keys = {c.key for c in summary.controls}
    assert keys == {"payroll", "supplier_invoices", "contracts"}
    assert summary.scope_note == messages.CONTROL_SCOPE_INSTALL_FUEL
    assert summary.compared == 1
    assert summary.coverage_account_count == 2
    labels = " ".join(c.label.lower() for c in summary.controls)
    assert "install" not in labels
    assert "fuel" not in labels


def test_legacy_report_never_invents_tied_out() -> None:
    items = [
        {
            "account": "Equipment COGS",
            "card_kind": "exception",
            "sources": [
                {"source_file": "redhawk_vendor_invoices_mar_2026.xlsx", "amount": 1}
            ],
        }
    ]
    summary = build_legacy_control_summary(items)
    assert summary.legacy is True
    by_key = {c.key: c for c in summary.controls}
    assert by_key["supplier_invoices"].status == "has_exceptions"
    assert by_key["payroll"].status == "not_compared"
    assert by_key["payroll"].status != "tied_out"
    assert by_key["contracts"].status != "tied_out"


def test_pack_unpack_round_trip_and_historical_list() -> None:
    items = [{"account": "Rent", "card_kind": "coverage"}]
    summary = build_legacy_control_summary(items)
    packed = pack_report_reconciliations(items, summary)
    assert packed["schema"] == REPORT_RECON_SCHEMA
    out_items, out_summary = unpack_report_reconciliations(packed)
    assert out_items == items
    assert out_summary is not None
    assert out_summary.legacy is True

    legacy_items, legacy_summary = unpack_report_reconciliations(items)
    assert legacy_items == items
    assert legacy_summary is None


def test_contracts_proposal_is_service_revenue() -> None:
    assert proposed_contracts_gl(["Service Revenue", "Installation Revenue"]) == (
        "Service Revenue"
    )
    assert proposed_contracts_gl(["Installation Revenue"]) is None


@pytest.mark.parametrize("second_rows", [[], [{"account": "Wages", "amount": 500}]])
def test_multiple_files_in_one_control_cannot_pass(second_rows) -> None:
    summary = _summary(
        source_files=["gl.xlsx", "payroll_a.xlsx", "payroll_b.xlsx"],
        per_file_rows={
            "payroll_a.xlsx": [{"account": "Wages", "amount": 500}],
            "payroll_b.xlsx": second_rows,
        },
        gl_amounts={"Wages": 500 if not second_rows else 1000},
        empty_files={"payroll_b.xlsx"} if not second_rows else set(),
    )
    control = summary.controls[0]
    assert control.status == "not_compared"
    assert control.incomplete_reason == messages.CONTROL_MULTIPLE_SOURCES
    assert control.next_action == messages.CONTROL_NEXT_COMBINE_SOURCES
    assert control.comparisons == []
    assert summary.compared == 0


@pytest.mark.parametrize(
    "headers", [["Account", "Monthly Fee"], ["GL Account", "Monthly Fee"]]
)
def test_contracts_real_accounts_override_roster_file_total(headers) -> None:
    assert not is_file_total_candidate(
        "contracts", headers, roster_sidecar_present=True, amount_scope="Monthly Fee"
    )
    assert not should_file_total_after_parse(
        "contracts",
        ["Service Revenue", "Installation Revenue"],
        ["Service Revenue", "Installation Revenue"],
    )


def test_contracts_require_validated_monthly_fee_scope() -> None:
    headers = ["Customer ID", "Status", "Monthly Fee", "Last Billed"]
    assert is_file_total_candidate(
        "contracts", headers, roster_sidecar_present=True, amount_scope="Monthly Fee"
    )
    assert not is_file_total_candidate(
        "contracts", headers, roster_sidecar_present=False, amount_scope="Monthly Fee"
    )
    assert not is_file_total_candidate(
        "contracts",
        headers + ["Annual Fee"],
        roster_sidecar_present=True,
        amount_scope="Annual Fee",
    )
