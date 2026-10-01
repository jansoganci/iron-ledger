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
    assert row[2] == "payroll_a.xlsx, payroll_b.xlsx"
    assert row[6] == control["next_action"]
    assert row[7] == control["incomplete_reason"]
    assert ws.column_dimensions["H"].width >= 40
    assert ws.column_dimensions["E"].width == 28
    assert ws.row_dimensions[rows.index(row) + 1].height is not None


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
    assert "Comparison evidence" in values
    assert messages.CONTROL_SCOPE_INSTALL_FUEL in values
    header_rows = [
        r
        for r in range(1, ws.max_row + 1)
        if ws.cell(row=r, column=1).value == "Control"
    ]
    assert len(header_rows) >= 2
    summary_headers = [ws.cell(row=header_rows[0], column=c).value for c in range(1, 9)]
    evidence_headers = [
        ws.cell(row=header_rows[1], column=c).value for c in range(1, 8)
    ]
    assert summary_headers == [
        "Control",
        "Status",
        "Source file",
        "Amount scope",
        "GL target",
        "Difference ($)",
        "Next action",
        "Why not compared",
    ]
    assert evidence_headers == [
        "Control",
        "Source file",
        "GL account",
        "Supporting amount ($)",
        "GL amount ($)",
        "Difference ($)",
        "Classification / incomplete reason",
    ]
    evidence_row = header_rows[1] + 1
    assert ws.cell(row=evidence_row, column=1).value == "Payroll"
    assert ws.cell(row=evidence_row, column=2).value == "payroll.xlsx"
    assert ws.cell(row=evidence_row, column=3).value == "Owner Salary"
    assert ws.cell(row=evidence_row, column=4).value == 5500.0
    assert ws.cell(row=evidence_row, column=5).value == 5500.0
    assert ws.cell(row=evidence_row, column=6).value == 0.0
    assert ws.column_dimensions["C"].width == 28
    assert ws.column_dimensions["E"].width == 28
    assert ws.column_dimensions["H"].width == 48
    assert ws.cell(row=evidence_row, column=2).alignment.wrap_text is True


def test_recon_rows_do_not_reset_control_column_widths() -> None:
    raw = build_close_package(
        entries=[],
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
        company_name="Redhawk",
        control_summary={
            "compared": 1,
            "with_exceptions": 1,
            "not_evaluated": 0,
            "coverage_account_count": 1,
            "controls": [
                {
                    "label": "Contracts",
                    "status": "has_exceptions",
                    "source_file": "redhawk_contracts_mar_2026.xlsx",
                    "source_files": ["redhawk_contracts_mar_2026.xlsx"],
                    "amount_scope": "Monthly Fee",
                    "gl_targets": ["Service Revenue"],
                    "next_action": messages.CONTROL_NEXT_REVIEW_EXCEPTION,
                    "comparisons": [
                        {
                            "gl_account": "Service Revenue",
                            "supporting_amount": 3825.0,
                            "gl_amount": 3540.0,
                            "difference": 285.0,
                            "classification": "stale_reference",
                            "complete": True,
                        }
                    ],
                }
            ],
        },
    )
    ws = openpyxl.load_workbook(BytesIO(raw))["Reconciliations"]
    assert ws.column_dimensions["E"].width == 28
    assert ws.column_dimensions["C"].width == 28
    assert ws.column_dimensions["B"].width == 36
    evidence = next(
        r
        for r in range(1, ws.max_row + 1)
        if ws.cell(row=r, column=3).value == "Service Revenue"
        and ws.cell(row=r, column=4).value == 3825.0
    )
    assert ws.cell(row=evidence, column=5).value == 3540.0
    assert ws.cell(row=evidence, column=6).value == 285.0
    assert ws.cell(row=evidence, column=2).value == "redhawk_contracts_mar_2026.xlsx"
