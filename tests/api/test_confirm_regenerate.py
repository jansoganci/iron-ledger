"""POST /runs/{id}/confirm refuses to replace entries without regenerate consent."""

from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient
import pytest

from backend.api.auth import get_company_id, get_current_user
from backend.domain.entities import Report
from backend.domain.run_state_machine import RunStatus
from backend.main import app
from backend import messages

client = TestClient(app, raise_server_exceptions=False)

PERIOD = "2026-03-01"


@pytest.fixture(autouse=True)
def _override_auth():
    previous_user = app.dependency_overrides.get(get_current_user)
    previous_company = app.dependency_overrides.get(get_company_id)
    app.dependency_overrides[get_current_user] = lambda: "user-1"
    app.dependency_overrides[get_company_id] = lambda: "co-1"
    yield
    if previous_user is not None:
        app.dependency_overrides[get_current_user] = previous_user
    else:
        app.dependency_overrides.pop(get_current_user, None)
    if previous_company is not None:
        app.dependency_overrides[get_company_id] = previous_company
    else:
        app.dependency_overrides.pop(get_company_id, None)


def _awaiting_run(regenerate: bool = False) -> dict:
    preview: dict = {
        "rows": [
            {"account": "Service Revenue", "category": "REVENUE", "amount": 100.0}
        ],
        "source_column": "amount",
    }
    if regenerate:
        preview["_regenerate"] = True
    return {
        "id": "run-123",
        "status": RunStatus.AWAITING_CONFIRMATION.value,
        "company_id": "co-1",
        "period": PERIOD,
        "parse_preview": preview,
        "storage_key": "key",
    }


def _existing_report() -> Report:
    return Report(
        id="rep-1",
        company_id="co-1",
        period=date(2026, 3, 1),
        summary="original",
        anomaly_count=0,
        error_count=0,
    )


def _patch_confirm(run: dict, existing: Report | None):
    runs = MagicMock()
    runs.get_by_id.return_value = run
    reports = MagicMock()
    reports.get.return_value = existing
    entries = MagicMock()
    accounts = MagicMock()
    accounts.batch_get_or_create.return_value = {"Service Revenue": "acct-1"}
    return runs, reports, entries, accounts


@patch("backend.api.routers.uploads.run_opus_upgrade")
@patch("backend.api.routers.uploads.run_comparison_and_report")
@patch("backend.api.routers.uploads.get_accounts_repo")
@patch("backend.api.routers.uploads.get_entries_repo")
@patch("backend.api.routers.uploads.get_reports_repo")
@patch("backend.api.routers.uploads.get_runs_repo")
def test_confirm_without_flag_is_409_when_report_exists(
    mock_runs, mock_reports, mock_entries, mock_accounts, _cmp, _opus
):
    runs, reports, entries, accounts = _patch_confirm(
        _awaiting_run(), _existing_report()
    )
    mock_runs.return_value = runs
    mock_reports.return_value = reports
    mock_entries.return_value = entries
    mock_accounts.return_value = accounts

    resp = client.post("/runs/run-123/confirm", json={"overrides": []})

    assert resp.status_code == 409
    assert resp.json()["detail"] == messages.REGENERATE_REQUIRED
    entries.replace_period.assert_not_called()
    runs.set_regenerate.assert_not_called()


@patch("backend.api.routers.uploads.run_opus_upgrade")
@patch("backend.api.routers.uploads.run_comparison_and_report")
@patch("backend.api.routers.uploads.get_accounts_repo")
@patch("backend.api.routers.uploads.get_entries_repo")
@patch("backend.api.routers.uploads.get_reports_repo")
@patch("backend.api.routers.uploads.get_runs_repo")
def test_confirm_first_period_without_flag_writes_entries(
    mock_runs, mock_reports, mock_entries, mock_accounts, _cmp, _opus
):
    runs, reports, entries, accounts = _patch_confirm(_awaiting_run(), None)
    mock_runs.return_value = runs
    mock_reports.return_value = reports
    mock_entries.return_value = entries
    mock_accounts.return_value = accounts

    resp = client.post("/runs/run-123/confirm", json={"overrides": []})

    assert resp.status_code == 200
    entries.replace_period.assert_called_once()
    written = entries.replace_period.call_args[0][2]
    assert len(written) == 1
    assert written[0].account_id == "acct-1"


@patch("backend.api.routers.uploads.run_opus_upgrade")
@patch("backend.api.routers.uploads.run_comparison_and_report")
@patch("backend.api.routers.uploads.get_accounts_repo")
@patch("backend.api.routers.uploads.get_entries_repo")
@patch("backend.api.routers.uploads.get_reports_repo")
@patch("backend.api.routers.uploads.get_runs_repo")
def test_confirm_with_flag_replaces_entries_when_report_exists(
    mock_runs, mock_reports, mock_entries, mock_accounts, _cmp, _opus
):
    runs, reports, entries, accounts = _patch_confirm(
        _awaiting_run(), _existing_report()
    )
    mock_runs.return_value = runs
    mock_reports.return_value = reports
    mock_entries.return_value = entries
    mock_accounts.return_value = accounts

    resp = client.post(
        "/runs/run-123/confirm", json={"overrides": [], "regenerate": True}
    )

    assert resp.status_code == 200
    entries.replace_period.assert_called_once()
    runs.set_regenerate.assert_called_once_with("run-123", True)


@patch("backend.api.routers.uploads.run_parser_until_preview")
@patch("backend.api.routers.uploads.get_runs_repo")
def test_retry_copies_regenerate_flag(mock_runs, _parser):
    old = {
        "id": "old-run",
        "status": RunStatus.GUARDRAIL_FAILED.value,
        "company_id": "co-1",
        "period": PERIOD,
        "storage_key": "stored-file",
        "parse_preview": {"_regenerate": True, "rows": []},
    }
    new = {"id": "new-run"}
    runs = MagicMock()
    runs.get_by_id.return_value = old
    runs.create.return_value = new
    mock_runs.return_value = runs

    resp = client.post("/runs/old-run/retry")

    assert resp.status_code == 200
    assert resp.json()["run_id"] == "new-run"
    runs.set_regenerate.assert_called_once_with("new-run", True)
