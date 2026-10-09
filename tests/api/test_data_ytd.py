"""The Data API adds a company-scoped, deterministic YTD summary."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from backend.api.auth import get_company_id, get_current_user
from backend.domain.entities import MonthlyEntry
from backend.main import app

client = TestClient(app, raise_server_exceptions=False)


@pytest.fixture(autouse=True)
def _auth():
    saved = dict(app.dependency_overrides)
    app.dependency_overrides[get_current_user] = lambda: "user-1"
    app.dependency_overrides[get_company_id] = lambda: "company-1"
    yield
    app.dependency_overrides.clear()
    app.dependency_overrides.update(saved)


def test_data_ytd_uses_auth_company_and_selected_month() -> None:
    entries = MagicMock()
    entries.list_for_year.return_value = [
        MonthlyEntry(
            id="entry-1",
            company_id="company-1",
            account_id="rev",
            period=date(2026, 3, 1),
            actual_amount=Decimal("250.00"),
            source_file="gl.xlsx",
        )
    ]
    accounts = MagicMock()
    accounts.get_accounts_by_id.return_value = {
        "rev": {"name": "Revenue", "category": "REVENUE"}
    }
    entries_patch = patch(
        "backend.api.routers.reports.get_entries_repo", return_value=entries
    )
    accounts_patch = patch(
        "backend.api.routers.reports.get_accounts_repo", return_value=accounts
    )
    with entries_patch, accounts_patch:
        url = "/data?year=2026&through_month=4&company_id=other"
        response = client.get(url)

    assert response.status_code == 200
    assert response.json()["ytd"]["months"][2]["values"]["revenue"] == 250.0
    assert response.json()["ytd"]["months"][3]["values"] is None
    assert response.json()["ytd"]["totals"]["revenue"] == 250.0
    entries.list_for_year.assert_called_once_with(
        "company-1", date(2026, 1, 1), date(2026, 12, 31)
    )
    accounts.get_accounts_by_id.assert_called_once_with("company-1")


def test_data_ytd_rejects_invalid_month_before_query() -> None:
    with patch("backend.api.routers.reports.get_entries_repo") as get_entries:
        response = client.get("/data?year=2026&through_month=13")
    assert response.status_code == 422
    get_entries.assert_not_called()
