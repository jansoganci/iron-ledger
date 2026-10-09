"""Retry re-runs every file of a multi-file analysis, or asks for a fresh upload."""

from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock, patch

import pytest

from backend import messages
from backend.api.auth import get_company_id, get_current_user
from backend.api.rate_limit import limiter
from backend.domain.run_state_machine import RunStatus
from backend.main import app
from tests.api.test_confirm_regenerate import PERIOD, client

USER = "user-1"
GL = f"{USER}/{PERIOD}/gl.xlsx"
PAYROLL = f"{USER}/{PERIOD}/payroll.xlsx"


@pytest.fixture(autouse=True)
def _auth():
    previous_user = app.dependency_overrides.get(get_current_user)
    previous_company = app.dependency_overrides.get(get_company_id)
    app.dependency_overrides[get_current_user] = lambda: USER
    app.dependency_overrides[get_company_id] = lambda: "co-1"
    limiter.reset()
    yield
    limiter.reset()
    if previous_user is not None:
        app.dependency_overrides[get_current_user] = previous_user
    else:
        app.dependency_overrides.pop(get_current_user, None)
    if previous_company is not None:
        app.dependency_overrides[get_company_id] = previous_company
    else:
        app.dependency_overrides.pop(get_company_id, None)


def _runs(old: dict) -> MagicMock:
    runs = MagicMock()
    runs.get_by_id.return_value = old
    runs.create.return_value = {"id": "new-run"}
    return runs


def _old(**extra) -> dict:
    run = {
        "id": "old-run",
        "status": RunStatus.GUARDRAIL_FAILED.value,
        "company_id": "co-1",
        "period": PERIOD,
        "storage_key": GL,
        "file_count": 1,
        "parse_preview": {},
    }
    run.update(extra)
    return run


@patch("backend.api.routers.uploads.run_multi_file_parser_with_mapping")
@patch("backend.api.routers.uploads.run_parser_until_preview")
@patch("backend.api.routers.uploads.get_runs_repo")
def test_multi_file_retry_re_runs_every_file_in_order(mock_runs, single, multi):
    keys = [PAYROLL, GL]
    mock_runs.return_value = _runs(
        _old(file_count=2, parse_preview={"storage_keys": keys})
    )

    resp = client.post("/runs/old-run/retry")

    assert resp.status_code == 200
    assert resp.json()["run_id"] == "new-run"
    single.assert_not_called()
    multi.assert_called_once_with(
        run_id="new-run",
        storage_keys=keys,
        company_id="co-1",
        period=date.fromisoformat(PERIOD),
    )
    mock_runs.return_value.set_storage_key.assert_called_once_with("new-run", PAYROLL)


@patch("backend.api.routers.uploads.run_multi_file_parser_with_mapping")
@patch("backend.api.routers.uploads.run_parser_until_preview")
@patch("backend.api.routers.uploads.get_runs_repo")
def test_single_file_retry_is_unchanged(mock_runs, single, multi):
    mock_runs.return_value = _runs(_old(storage_key="stored-file"))

    resp = client.post("/runs/old-run/retry")

    assert resp.status_code == 200
    multi.assert_not_called()
    single.assert_called_once()
    assert single.call_args.kwargs["storage_key"] == "stored-file"


@patch("backend.api.routers.uploads.run_parser_until_preview")
@patch("backend.api.routers.uploads.get_runs_repo")
def test_old_multi_file_run_without_a_list_asks_for_a_fresh_upload(mock_runs, single):
    mock_runs.return_value = _runs(_old(file_count=2, storage_key=GL))

    resp = client.post("/runs/old-run/retry")

    assert resp.status_code == 422
    assert resp.json()["detail"] == messages.RETRY_REUPLOAD
    single.assert_not_called()
    mock_runs.return_value.create.assert_not_called()


@patch("backend.api.routers.uploads.run_multi_file_parser_with_mapping")
@patch("backend.api.routers.uploads.get_runs_repo")
def test_a_key_from_another_folder_is_refused(mock_runs, multi):
    mock_runs.return_value = _runs(
        _old(parse_preview={"storage_keys": [GL, "someone-else/2026-03-01/gl.xlsx"]})
    )

    resp = client.post("/runs/old-run/retry")

    assert resp.status_code == 422
    assert resp.json()["detail"] == messages.RETRY_REUPLOAD
    multi.assert_not_called()
    mock_runs.return_value.create.assert_not_called()


def test_retry_messages_say_what_to_do_next() -> None:
    assert "upload the files again" in messages.RETRY_REUPLOAD
    assert "upload again" in messages.RETRY_NO_FILE
