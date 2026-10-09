"""Excel export for TrueCost close packages.

Builds a 3-sheet .xlsx workbook from consolidated monthly data:
  Sheet 1 — Consolidated P&L   (one row per account, totals by category)
  Sheet 2 — Reconciliations     (cross-source discrepancies with severity)
  Sheet 3 — Source Breakdown    (per-account, per-file amounts)

Called by GET /report/{company_id}/{period}/export.xlsx.
Returns raw bytes; caller sets Content-Disposition header.
"""

from __future__ import annotations

import io
import math
from datetime import date

from backend import messages

import openpyxl
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

# ---------------------------------------------------------------------------
# Palette
# ---------------------------------------------------------------------------

_HEADER_FILL = PatternFill("solid", fgColor="1F3864")  # dark navy
_HEADER_FONT = Font(color="FFFFFF", bold=True, size=11)
_SUBHEADER_FILL = PatternFill("solid", fgColor="D6E4F0")  # light blue
_SEVERITY_FILLS = {
    "high": PatternFill("solid", fgColor="FFCCCC"),
    "medium": PatternFill("solid", fgColor="FFE5B4"),
    "low": PatternFill("solid", fgColor="FFFFCC"),
}
_COVERAGE_FILL = PatternFill("solid", fgColor="F3F4F6")  # info / not an exception
_CURRENCY_FMT = "#,##0.00"
_PCT_FMT = "0.0%"
_WRAP_ALIGN = Alignment(wrap_text=True, vertical="top")
_CONTROL_HEADERS = [
    "Control",
    "Status",
    "Source file",
    "Amount scope",
    "GL target",
    "Difference ($)",
    "Next action",
    "Why not compared",
]
_EVIDENCE_HEADERS = [
    "Control",
    "Source file",
    "GL account",
    "Supporting amount ($)",
    "GL amount ($)",
    "Difference ($)",
    "Classification / incomplete reason",
]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def close_package_filename(period: date) -> str:
    return f"truecost_{period.isoformat()}_close_package.xlsx"


def build_close_package(
    entries: list[dict],
    reconciliations: list[dict] | None,
    period: date,
    company_name: str,
    control_summary: dict | None = None,
) -> bytes:
    """Return raw .xlsx bytes for the close package workbook.

    Args:
        entries: list of dicts with keys: account, category, amount, source_breakdown
        reconciliations: list of ReconciliationItem dicts (may be None/empty)
        period: the reporting period
        company_name: shown in the header row
    """
    wb = openpyxl.Workbook()
    wb.properties.title = "TrueCost close package"
    wb.remove(wb.active)  # remove default Sheet

    _build_pl_sheet(wb, entries, period, company_name)
    _build_reconciliation_sheet(wb, reconciliations or [], period, control_summary)
    _build_source_breakdown_sheet(wb, entries, period)

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Sheet 1 — Consolidated P&L
# ---------------------------------------------------------------------------

_CATEGORY_ORDER = ["REVENUE", "COGS", "OPEX", "G&A", "R&D", "OTHER_INCOME", "OTHER"]


def _build_pl_sheet(
    wb: openpyxl.Workbook,
    entries: list[dict],
    period: date,
    company_name: str,
) -> None:
    ws = wb.create_sheet("Consolidated P&L")

    # Title row
    ws.append(
        [f"TrueCost — {company_name} — Consolidated P&L — {period.strftime('%B %Y')}"]
    )
    _style_row(ws, 1, font=Font(bold=True, size=13))
    ws.merge_cells("A1:D1")

    # Header
    ws.append(
        [
            "Account",
            "Category",
            "Amount ($)",
            "Sources (GL amount wins; other files are evidence)",
        ]
    )
    _style_header_row(ws, 2, 4)
    ws.column_dimensions["A"].width = 32
    ws.column_dimensions["B"].width = 18
    ws.column_dimensions["C"].width = 16
    ws.column_dimensions["D"].width = 70

    # Group by category in prescribed order
    by_cat: dict[str, list[dict]] = {}
    for e in entries:
        cat = e.get("category", "OTHER")
        by_cat.setdefault(cat, []).append(e)

    row_num = 3
    for cat in _CATEGORY_ORDER:
        cat_entries = by_cat.get(cat, [])
        if not cat_entries:
            continue

        # Category sub-header
        ws.append([cat, "", "", ""])
        for col in range(1, 5):
            cell = ws.cell(row=row_num, column=col)
            cell.fill = _SUBHEADER_FILL
            cell.font = Font(bold=True, size=10)
        row_num += 1

        cat_total = 0.0
        for e in sorted(cat_entries, key=lambda x: x["account"]):
            amount = float(e.get("amount", 0))
            cat_total += amount
            breakdown = e.get("source_breakdown") or []
            source_labels = ", ".join(
                f"{b['source_file']} ${b['amount']:,.0f}" for b in breakdown
            )
            ws.append([e["account"], cat, amount, source_labels])
            amt_cell = ws.cell(row=row_num, column=3)
            amt_cell.number_format = _CURRENCY_FMT
            # File names are long; wrap them instead of cutting them off.
            for col in range(1, 4):
                ws.cell(row=row_num, column=col).alignment = Alignment(vertical="top")
            ws.cell(row=row_num, column=4).alignment = Alignment(
                wrap_text=True, vertical="top"
            )
            _fit_wrapped_row(ws, row_num)
            row_num += 1

        # Category total
        ws.append(["", f"Total {cat}", cat_total, ""])
        total_cell = ws.cell(row=row_num, column=3)
        total_cell.number_format = _CURRENCY_FMT
        ws.cell(row=row_num, column=2).font = Font(bold=True)
        total_cell.font = Font(bold=True)
        row_num += 1

    ws.freeze_panes = "A3"


# ---------------------------------------------------------------------------
# Sheet 2 — Reconciliations
# ---------------------------------------------------------------------------


def _control_source_label(control: dict) -> str:
    files = [str(name) for name in (control.get("source_files") or []) if name]
    if files:
        return ", ".join(files)
    return str(control.get("source_file") or "")


def _build_reconciliation_sheet(
    wb: openpyxl.Workbook,
    reconciliations: list[dict],
    period: date,
    control_summary: dict | None = None,
) -> None:
    ws = wb.create_sheet("Reconciliations")

    for column, width in {
        "A": 24,
        "B": 36,
        "C": 28,
        "D": 22,
        "E": 28,
        "F": 16,
        "G": 42,
        "H": 48,
    }.items():
        ws.column_dimensions[column].width = width

    ws.append([f"TrueCost — Cross-Source Reconciliation — {period.strftime('%B %Y')}"])
    _style_row(ws, 1, font=Font(bold=True, size=13))
    ws.merge_cells("A1:H1")

    ws.append([messages.BANK_OUTSIDE_ATTESTATION])
    _style_row(ws, 2, font=Font(italic=True, size=10, color="5A5853"))
    ws.merge_cells("A2:H2")
    _fit_wrapped_row(ws, 2)

    ws.append([messages.CONTROL_SCOPE_INSTALL_FUEL])
    _style_row(ws, 3, font=Font(italic=True, size=10, color="5A5853"))
    ws.merge_cells("A3:H3")
    _fit_wrapped_row(ws, 3)

    row_num = 4
    if control_summary:
        compared = control_summary.get("compared", 0)
        with_exc = control_summary.get("with_exceptions", 0)
        not_eval = control_summary.get("not_evaluated", 0)
        coverage = control_summary.get("coverage_account_count", 0)
        ws.append(
            [
                "Control summary",
                f"{compared} compared",
                f"{with_exc} with exceptions",
                f"{not_eval} not evaluated",
                f"{coverage} GL accounts not compared",
            ]
        )
        _style_row(ws, row_num, font=Font(bold=True, size=10))
        row_num += 1
        ws.append(_CONTROL_HEADERS)
        _style_header_row(ws, row_num, len(_CONTROL_HEADERS))
        row_num += 1
        for control in control_summary.get("controls") or []:
            comps = control.get("comparisons") or []
            differences = [
                c.get("difference") for c in comps if c.get("difference") is not None
            ]
            diff_value = differences[0] if len(differences) == 1 else None
            status = str(control.get("status") or "").replace("_", " ")
            ws.append(
                [
                    control.get("label"),
                    status,
                    _control_source_label(control),
                    control.get("amount_scope") or "",
                    ", ".join(control.get("gl_targets") or []),
                    diff_value,
                    control.get("next_action") or "",
                    control.get("incomplete_reason") or "",
                ]
            )
            for col in (3, 5, 7, 8):
                ws.cell(row=row_num, column=col).alignment = _WRAP_ALIGN
            if diff_value is not None:
                ws.cell(row=row_num, column=6).number_format = _CURRENCY_FMT
            _fit_wrapped_row(ws, row_num)
            row_num += 1

        evidence_rows = [
            (control, comp)
            for control in control_summary.get("controls") or []
            for comp in (control.get("comparisons") or [])
        ]
        if evidence_rows:
            ws.append([])
            row_num += 1
            ws.append(["Comparison evidence"])
            _style_row(ws, row_num, font=Font(bold=True, size=10))
            row_num += 1
            ws.append(_EVIDENCE_HEADERS)
            _style_header_row(ws, row_num, len(_EVIDENCE_HEADERS))
            row_num += 1
            for control, comp in evidence_rows:
                reason = (comp.get("classification") or "").replace(
                    "_", " "
                ).title() or (comp.get("incomplete_reason") or "")
                ws.append(
                    [
                        control.get("label"),
                        _control_source_label(control),
                        comp.get("gl_account") or "",
                        comp.get("supporting_amount"),
                        comp.get("gl_amount"),
                        comp.get("difference"),
                        reason,
                    ]
                )
                for col in (2, 3, 7):
                    ws.cell(row=row_num, column=col).alignment = _WRAP_ALIGN
                for col in (4, 5, 6):
                    ws.cell(row=row_num, column=col).number_format = _CURRENCY_FMT
                _fit_wrapped_row(ws, row_num)
                row_num += 1
        ws.append([])
        row_num += 1

    if not reconciliations:
        ws.append(["No cross-source discrepancies detected for this period."])
        ws.freeze_panes = "A4"
        return

    headers = [
        "Account",
        "Category",
        "GL Amount ($)",
        "Dept/Source Total ($)",
        "Delta ($)",
        "Severity",
        "Classification",
    ]
    ws.append(headers)
    _style_header_row(ws, row_num, len(headers))
    row_num += 1
    for item in sorted(reconciliations, key=lambda x: -abs(x.get("delta", 0) or 0)):
        coverage = _is_coverage_item(item)
        severity = item.get("severity", "low")
        row = [
            item.get("account", ""),
            item.get("category", ""),
            item.get("gl_amount"),
            item.get("non_gl_total"),
            item.get("delta"),
            "INFO" if coverage else severity.upper(),
            (
                "Not compared"
                if coverage
                else (item.get("classification") or "").replace("_", " ").title()
            ),
        ]
        ws.append(row)
        fill = _COVERAGE_FILL if coverage else _SEVERITY_FILLS.get(severity)
        for col in range(1, 8):
            cell = ws.cell(row=row_num, column=col)
            if fill:
                cell.fill = fill
            if col in (3, 4, 5):
                cell.number_format = _CURRENCY_FMT
        _fit_wrapped_row(ws, row_num)
        row_num += 1

    ws.freeze_panes = "A4"

    row_num += 1
    ws.cell(row=row_num, column=1).value = "Source Detail"
    ws.cell(row=row_num, column=1).font = Font(bold=True, size=11)
    row_num += 1

    src_headers = ["Account", "Source File", "Amount ($)", "Row Count"]
    for col, h in enumerate(src_headers, 1):
        cell = ws.cell(row=row_num, column=col)
        cell.value = h
        cell.font = _HEADER_FONT
        cell.fill = _HEADER_FILL
    row_num += 1

    for item in reconciliations:
        for src in item.get("sources", []):
            ws.cell(row=row_num, column=1).value = item.get("account", "")
            ws.cell(row=row_num, column=2).value = src.get("source_file", "")
            ws.cell(row=row_num, column=2).alignment = _WRAP_ALIGN
            amt_cell = ws.cell(row=row_num, column=3)
            amt_cell.value = src.get("amount")
            amt_cell.number_format = _CURRENCY_FMT
            ws.cell(row=row_num, column=4).value = src.get("row_count")
            _fit_wrapped_row(ws, row_num)
            row_num += 1


# ---------------------------------------------------------------------------
# Sheet 3 — Source Breakdown
# ---------------------------------------------------------------------------


def _build_source_breakdown_sheet(
    wb: openpyxl.Workbook,
    entries: list[dict],
    period: date,
) -> None:
    ws = wb.create_sheet("Source Breakdown")

    ws.append(
        [
            f"TrueCost — Source Breakdown — {period.strftime('%B %Y')} "
            "(supporting files are evidence, not added)"
        ]
    )
    _style_row(ws, 1, font=Font(bold=True, size=13))
    ws.merge_cells("A1:E1")

    headers = ["Account", "Category", "Source File", "Amount ($)", "Row Count"]
    ws.append(headers)
    _style_header_row(ws, 2, 5)

    ws.column_dimensions["A"].width = 28
    ws.column_dimensions["B"].width = 16
    ws.column_dimensions["C"].width = 32
    ws.column_dimensions["D"].width = 16
    ws.column_dimensions["E"].width = 12

    row_num = 3
    for e in sorted(
        entries, key=lambda x: (x.get("category", ""), x.get("account", ""))
    ):
        breakdown = e.get("source_breakdown") or []
        if not breakdown:
            # Single-file run: write one row with filename as source
            ws.append(
                [
                    e["account"],
                    e.get("category", ""),
                    e.get("source_file", "—"),
                    float(e.get("amount", 0)),
                    "—",
                ]
            )
            ws.cell(row=row_num, column=4).number_format = _CURRENCY_FMT
            row_num += 1
        else:
            for src in breakdown:
                ws.append(
                    [
                        e["account"],
                        e.get("category", ""),
                        src.get("source_file", ""),
                        src.get("amount", 0),
                        src.get("row_count", ""),
                    ]
                )
                ws.cell(row=row_num, column=4).number_format = _CURRENCY_FMT
                row_num += 1

    ws.freeze_panes = "A3"


# ---------------------------------------------------------------------------
# Style helpers
# ---------------------------------------------------------------------------


def _is_coverage_item(item: dict) -> bool:
    if item.get("card_kind") == "coverage":
        return True
    hints = item.get("hints") or {}
    if isinstance(hints, dict):
        return bool(hints.get("is_gl_only"))
    return False


def _style_header_row(ws, row_num: int, columns: int) -> None:
    for col in range(1, columns + 1):
        cell = ws.cell(row=row_num, column=col)
        cell.font = _HEADER_FONT
        cell.fill = _HEADER_FILL
        cell.alignment = Alignment(
            horizontal="center", wrap_text=True, vertical="center"
        )
    ws.row_dimensions[row_num].height = 22


def _fit_wrapped_row(ws, row_num: int) -> None:
    max_lines = 1
    for cell in ws[row_num]:
        if cell.value is None:
            continue
        text = str(cell.value)
        width = ws.column_dimensions[get_column_letter(cell.column)].width or 12
        chars = max(int(width), 8)
        lines = 0
        for paragraph in text.splitlines() or [""]:
            lines += max(1, math.ceil(len(paragraph) / chars))
        wrap = bool(cell.alignment and cell.alignment.wrap_text)
        if wrap or "\n" in text:
            max_lines = max(max_lines, lines)
    ws.row_dimensions[row_num].height = min(15 * max_lines + 4, 75)


def _style_row(ws, row_num: int, font: Font | None = None) -> None:
    for cell in ws[row_num]:
        if font:
            cell.font = font
