"""Excel export: coverage rows render as INFO / Not compared."""

from __future__ import annotations

from datetime import date
from io import BytesIO

import openpyxl

from backend import messages
from backend.tools.excel_export import build_close_package
from backend.tools.close_controls import build_control_summary


def test_coverage_row_exports_as_info_not_compared() -> None:
    raw = build_close_package(
        entries=[
            {
                "account": "Sales",
                "category": "REVENUE",
                "amount": 100.0,
                "source_breakdown": [],
            }
        ],
        reconciliations=[
            {
                "account": "Advertising — Meta",
                "category": "OPEX",
                "gl_amount": 8200.0,
                "non_gl_total": 0.0,
                "delta": -8200.0,
                "severity": "high",
                "classification": None,
                "card_kind": "coverage",
                "hints": {"is_gl_only": True},
                "sources": [],
            }
        ],
        period=date(2026, 3, 1),
        company_name="Vandelay",
    )
    wb = openpyxl.load_workbook(BytesIO(raw))
    ws = wb["Reconciliations"]
    assert ws.cell(row=2, column=1).value == messages.BANK_OUTSIDE_ATTESTATION
    assert ws.cell(row=3, column=1).value == messages.CONTROL_SCOPE_INSTALL_FUEL
    accounts = {ws.cell(row=r, column=1).value: r for r in range(1, ws.max_row + 1)}
    row = accounts["Advertising — Meta"]
    assert ws.cell(row=row, column=6).value == "INFO"
    assert ws.cell(row=row, column=7).value == "Not compared"


def test_excel_keeps_control_incomplete_reason_and_next_action() -> None:
    summary = build_control_summary(
        period=date(2026, 3, 1),
        source_files=["gl.xlsx", "payroll_a.xlsx", "payroll_b.xlsx"],
        per_file_rows={},
        gl_amounts={},
        amount_scopes={},
        file_total_mappings={},
        mapping_pending_files=set(),
        recon_items=[],
    ).model_dump(mode="json")
    raw = build_close_package(
        entries=[],
        reconciliations=[],
        period=date(2026, 3, 1),
        company_name="Synthetic",
        control_summary=summary,
    )
    ws = openpyxl.load_workbook(BytesIO(raw))["Reconciliations"]
    rows = list(ws.values)
    control = summary["controls"][0]
    row = next(r for r in rows if r[0] == control["label"])
    assert row[6] == control["next_action"]
    assert row[7] == control["incomplete_reason"]
    assert ws.column_dimensions["H"].width >= 40


def test_recon_sheet_states_bank_rec_is_outside_even_when_empty() -> None:
    raw = build_close_package(
        entries=[],
        reconciliations=[],
        period=date(2026, 3, 1),
        company_name="Redhawk",
    )
    wb = openpyxl.load_workbook(BytesIO(raw))
    ws = wb["Reconciliations"]
    assert ws.cell(row=2, column=1).value == messages.BANK_OUTSIDE_ATTESTATION
    assert ws.cell(row=3, column=1).value == messages.CONTROL_SCOPE_INSTALL_FUEL


def test_control_summary_exports_tied_out_evidence() -> None:
    raw = build_close_package(
        entries=[],
        reconciliations=[],
        period=date(2026, 3, 1),
        company_name="Redhawk",
        control_summary={
            "compared": 1,
            "with_exceptions": 0,
            "not_evaluated": 2,
            "coverage_account_count": 4,
            "scope_note": messages.CONTROL_SCOPE_INSTALL_FUEL,
            "controls": [
                {
                    "label": "Payroll",
                    "status": "tied_out",
                    "source_file": "payroll.xlsx",
                    "amount_scope": "Base Compensation",
                    "gl_targets": ["Owner Salary"],
                    "next_action": messages.CONTROL_NEXT_REVIEW_EVIDENCE,
                    "comparisons": [
                        {
                            "gl_account": "Owner Salary",
                            "supporting_amount": 5500.0,
                            "gl_amount": 5500.0,
                            "difference": 0.0,
                            "complete": True,
                        }
                    ],
                }
            ],
        },
    )
    wb = openpyxl.load_workbook(BytesIO(raw))
    ws = wb["Reconciliations"]
    values = [ws.cell(row=r, column=1).value for r in range(1, ws.max_row + 1)]
    assert "Payroll" in values
    assert "Control summary" in values
    assert messages.CONTROL_SCOPE_INSTALL_FUEL in values
