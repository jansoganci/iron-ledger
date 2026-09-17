"""GET /report includes a Python-computed tie-out summary."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from backend.api.auth import (
    _company_cache,
    get_cached_company,
    get_company_id,
    get_current_user,
)
from backend.domain.entities import MonthlyEntry, Report
from backend.main import app

USER_ID = "user-tieout-1"
COMPANY_ID = "co-tieout-1"
PERIOD = date(2026, 3, 1)

client = TestClient(app, raise_server_exceptions=False)


def _company_row() -> dict:
    return {
        "id": COMPANY_ID,
        "name": "Redhawk Alarm & Security LLC",
        "sector": "security",
        "currency": "USD",
        "monthly_revenue_band": "under_100k",
    }


@pytest.fixture(autouse=True)
def _override_auth():
    saved = dict(app.dependency_overrides)
    app.dependency_overrides[get_current_user] = lambda: USER_ID
    app.dependency_overrides[get_company_id] = lambda: COMPANY_ID
    app.dependency_overrides[get_cached_company] = _company_row
    _company_cache[USER_ID] = (_company_row(), float("inf"))
    yield
    app.dependency_overrides.clear()
    app.dependency_overrides.update(saved)
    _company_cache.pop(USER_ID, None)


def test_get_report_tie_out_summary_from_entries_and_cards() -> None:
    report = Report(
        id="report-1",
        company_id=COMPANY_ID,
        period=PERIOD,
        summary="Payroll tied out. Vendors did not.",
        reconciliations=[
            {
                "account": "Equipment COGS",
                "category": "COGS",
                "card_kind": "exception",
                "delta": 700.0,
                "gl_amount": 1000.0,
                "non_gl_total": 1700.0,
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
                "category": "OPEX",
                "card_kind": "coverage",
                "delta": -3200.0,
                "gl_amount": 3200.0,
                "non_gl_total": 0.0,
                "hints": {"is_gl_only": True},
                "sources": [
                    {"source_file": "redhawk_gl_mar_2026.xlsx", "amount": 3200.0}
                ],
            },
        ],
    )
    entries = [
        MonthlyEntry(
            id="e1",
            company_id=COMPANY_ID,
            account_id="a1",
            period=PERIOD,
            actual_amount=1000,
            source_file="uploads/redhawk_payroll_mar_2026.xlsx",
        ),
        MonthlyEntry(
            id="e2",
            company_id=COMPANY_ID,
            account_id="a2",
            period=PERIOD,
            actual_amount=1700,
            source_file="uploads/redhawk_vendor_invoices_mar_2026.xlsx",
        ),
        MonthlyEntry(
            id="e3",
            company_id=COMPANY_ID,
            account_id="a3",
            period=PERIOD,
            actual_amount=3200,
            source_file="uploads/redhawk_gl_mar_2026.xlsx",
        ),
    ]
    reports = MagicMock()
    reports.get.return_value = report
    anomalies = MagicMock()
    anomalies.list_for_period.return_value = []
    accounts = MagicMock()
    accounts.get_accounts_by_id.return_value = {}
    entries_repo = MagicMock()
    entries_repo.list_for_period.return_value = entries

    with patch(
        "backend.api.routers.reports.get_reports_repo", return_value=reports
    ), patch(
        "backend.api.routers.reports.get_anomalies_repo", return_value=anomalies
    ), patch(
        "backend.api.routers.reports.get_accounts_repo", return_value=accounts
    ), patch(
        "backend.api.routers.reports.get_entries_repo", return_value=entries_repo
    ):
        resp = client.get(f"/report/{COMPANY_ID}/2026-03-01")

    assert resp.status_code == 200, resp.text
    body = resp.json()
    summary = body["tie_out_summary"]
    by_key = {g["key"]: g for g in summary["groups"]}
    assert by_key["payroll"]["status"] == "clean"
    assert by_key["supplier_invoices"]["status"] == "gap"
    assert summary["not_compared"] == 1
    vendor_item = next(
        i for i in body["reconciliations"] if i["account"] == "Equipment COGS"
    )
    assert vendor_item["tie_out_group"] == "supplier_invoices"
    rent = next(i for i in body["reconciliations"] if i["account"] == "Rent")
    assert rent["tie_out_group"] is None


def test_get_report_still_forbids_another_company() -> None:
    resp = client.get("/report/some-other-company/2026-03-01")
    assert resp.status_code == 403


def test_report_page_leads_with_tie_out_then_exceptions_then_narrative() -> None:
    summary = (
        Path(__file__).resolve().parents[2]
        / "frontend"
        / "src"
        / "components"
        / "ReportSummary.tsx"
    ).read_text(encoding="utf-8")
    i_tie = summary.index("<TieOutSummaryCard")
    i_exceptions = summary.index("<ReconciliationPanel")
    i_narrative = summary.index("narrativeParts.map")
    i_bank = summary.index("<BankAttestation")
    i_badge = summary.index("Numbers verified")
    i_footer = summary.index("This does not mean the month is closed.")
    assert i_tie < i_exceptions < i_narrative < i_bank
    assert i_badge < i_tie
    assert i_footer > i_bank
