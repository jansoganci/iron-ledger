"""Dil 3 — period lock. No LLM, no database: repos are fakes or mocks.

A closed month is read-only: upload, Replace (confirm) and retry return 409 and
write nothing. Reopening keeps the close row, logs an event and lets a new
analysis run again. Another company's month is never affected.
"""

from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from backend import messages
from backend.api.auth import get_company_id, get_current_user
from backend.domain.entities import Report
from backend.domain.run_state_machine import RunStatus
from backend.main import app
from tests.api.test_confirm_regenerate import (
    PERIOD,
    _awaiting_run,
    _existing_report,
    _patch_confirm,
)

client = TestClient(app, raise_server_exceptions=False)
ORCH = "backend.api.routers.uploads"


@pytest.fixture(autouse=True)
def _auth():
    state = {"user": "user-1", "company": "co-1"}
    previous_user = app.dependency_overrides.get(get_current_user)
    previous_company = app.dependency_overrides.get(get_company_id)
    app.dependency_overrides[get_current_user] = lambda: state["user"]
    app.dependency_overrides[get_company_id] = lambda: state["company"]
    yield state
    for dep, previous in (
        (get_current_user, previous_user),
        (get_company_id, previous_company),
    ):
        if previous is not None:
            app.dependency_overrides[dep] = previous
        else:
            app.dependency_overrides.pop(dep, None)


def _report_repo(report: Report | None):
    reports = MagicMock()
    reports.get.return_value = report
    return reports


def _close(period: str = PERIOD):
    with patch(
        "backend.api.routers.periods.get_reports_repo",
        return_value=_report_repo(_existing_report()),
    ):
        return client.post(f"/periods/{period}/close", json={"confirm": True})


def _confirm(regenerate: bool = True, company: str = "co-1"):
    """POST /runs/run-123/confirm against mocked repos. Returns (resp, mocks)."""
    run = _awaiting_run()
    run["company_id"] = company
    runs, reports, entries, accounts = _patch_confirm(run, _existing_report())
    with patch(f"{ORCH}.run_opus_upgrade"), patch(
        f"{ORCH}.run_comparison_and_report"
    ), patch(f"{ORCH}.get_accounts_repo", return_value=accounts), patch(
        f"{ORCH}.get_entries_repo", return_value=entries
    ), patch(
        f"{ORCH}.get_reports_repo", return_value=reports
    ), patch(
        f"{ORCH}.get_runs_repo", return_value=runs
    ):
        resp = client.post(
            "/runs/run-123/confirm",
            json={"overrides": [], "regenerate": regenerate},
        )
    return resp, runs, entries


def _upload(period: str = PERIOD):
    runs = MagicMock()
    runs.create.return_value = {"id": "new-run", "status": "pending"}
    storage = MagicMock()
    with patch(f"{ORCH}.get_runs_repo", return_value=runs), patch(
        f"{ORCH}.get_file_storage", return_value=storage
    ), patch(f"{ORCH}.get_reports_repo", return_value=_report_repo(None)), patch(
        f"{ORCH}.run_parser_until_preview"
    ):
        resp = client.post(
            "/upload",
            data={"period": period, "regenerate": "true"},
            files=[("files", ("gl.xlsx", b"x", "application/octet-stream"))],
        )
    return resp, runs, storage


def _retry():
    old = {
        "id": "old-run",
        "status": RunStatus.GUARDRAIL_FAILED.value,
        "company_id": "co-1",
        "period": PERIOD,
        "storage_key": "stored-file",
        "parse_preview": {},
    }
    runs = MagicMock()
    runs.get_by_id.return_value = old
    runs.create.return_value = {"id": "new-run"}
    with patch(f"{ORCH}.get_runs_repo", return_value=runs), patch(
        f"{ORCH}.run_parser_until_preview"
    ):
        resp = client.post("/runs/old-run/retry")
    return resp, runs


# --- open month ----------------------------------------------------------


def test_open_month_can_be_replaced() -> None:
    resp, runs, entries = _confirm(regenerate=True)
    assert resp.status_code == 200
    entries.replace_period.assert_called_once()
    runs.set_regenerate.assert_called_once_with("run-123", True)
    assert _upload()[0].status_code == 200


def test_closing_needs_explicit_confirm_and_a_finished_report(
    period_closes_repo,
) -> None:
    with patch(
        "backend.api.routers.periods.get_reports_repo",
        return_value=_report_repo(_existing_report()),
    ):
        no_confirm = client.post(f"/periods/{PERIOD}/close", json={})
        assert no_confirm.status_code == 422
        assert no_confirm.json()["detail"] == messages.PERIOD_CLOSE_CONFIRM_REQUIRED
    with patch(
        "backend.api.routers.periods.get_reports_repo",
        return_value=_report_repo(None),
    ):
        no_report = client.post(f"/periods/{PERIOD}/close", json={"confirm": True})
        assert no_report.status_code == 409
        assert no_report.json()["detail"] == messages.PERIOD_CLOSE_NEEDS_REPORT
    assert period_closes_repo.rows == []  # nothing closes by itself


def test_close_records_who_and_when_and_blocks_a_second_close(
    period_closes_repo,
) -> None:
    resp = _close()
    assert resp.status_code == 200
    body = resp.json()
    assert body["closed"] is True
    assert body["close"]["closed_by_email"] == "user-1@example.test"
    assert body["close"]["closed_by_you"] is True
    assert body["close"]["closed_at"]
    assert [e["event"] for e in body["log"]] == ["closed"]

    again = _close()
    assert again.status_code == 409
    assert again.json()["detail"] == messages.PERIOD_ALREADY_CLOSED
    assert len(period_closes_repo.rows) == 1


def test_period_must_be_the_first_of_a_month() -> None:
    assert client.get("/periods/2026-03-15/close").status_code == 422
    assert client.get("/periods/not-a-date/close").status_code == 422


# --- closed month --------------------------------------------------------


def test_closed_month_refuses_replace_upload_and_retry_and_writes_nothing() -> None:
    assert _close().status_code == 200

    resp, runs, entries = _confirm(regenerate=True)
    assert resp.status_code == 409
    assert resp.json()["detail"] == messages.PERIOD_CLOSED
    entries.replace_period.assert_not_called()  # monthly rows untouched
    runs.set_regenerate.assert_not_called()
    runs.update_status.assert_not_called()

    resp, runs, storage = _upload()
    assert resp.status_code == 409
    assert resp.json()["detail"] == messages.PERIOD_CLOSED
    runs.create.assert_not_called()
    storage.upload.assert_not_called()

    resp, runs = _retry()
    assert resp.status_code == 409
    assert resp.json()["detail"] == messages.PERIOD_CLOSED
    runs.create.assert_not_called()


def test_closed_month_report_stays_readable() -> None:
    """The lock guards writes only; GET status still answers for a closed month."""
    _close()
    state = client.get(f"/periods/{PERIOD}/close").json()
    assert state["closed"] is True


def test_closed_month_stops_a_run_already_in_flight() -> None:
    from backend.agents import orchestrator

    _close()
    with patch.object(orchestrator, "ComparisonAgent") as comparison, patch.object(
        orchestrator, "_fail_if_not_terminal"
    ) as fail:
        orchestrator.run_comparison_and_report(
            run_id="run-1",
            company_id="co-1",
            period=date(2026, 3, 1),
            storage_key="k",
        )
    comparison.assert_not_called()
    fail.assert_called_once_with("run-1", messages.PERIOD_CLOSED)


def test_close_after_the_first_read_does_not_start_the_report() -> None:
    from backend.agents import orchestrator
    from backend.domain.errors import PeriodClosedError

    with patch.object(
        orchestrator, "is_period_closed", return_value=False
    ), patch.object(orchestrator, "ComparisonAgent") as comparison, patch.object(
        orchestrator, "InterpreterAgent"
    ) as interpreter, patch.object(
        orchestrator, "get_runs_repo"
    ) as runs, patch.object(
        orchestrator, "_fail_if_not_terminal"
    ) as fail:
        runs.return_value.get_by_id.return_value = {"parse_preview": {}}
        comparison.return_value.run.side_effect = PeriodClosedError()
        orchestrator.run_comparison_and_report(
            run_id="run-1",
            company_id="co-1",
            period=date(2026, 3, 1),
            storage_key="k",
        )
    interpreter.return_value.run.assert_not_called()
    fail.assert_called_once_with("run-1", messages.PERIOD_CLOSED)


def test_closed_month_is_not_rewritten_by_the_opus_upgrade() -> None:
    from backend.agents import opus_upgrade

    _close()
    with patch.object(opus_upgrade, "get_llm_client") as llm, patch.object(
        opus_upgrade, "get_runs_repo"
    ) as runs:
        opus_upgrade.run_opus_upgrade("run-1", "co-1", date(2026, 3, 1))
    llm.assert_not_called()
    runs.assert_not_called()


# --- other companies and other months ------------------------------------


def test_another_company_and_another_month_are_not_affected(_auth) -> None:
    assert _close().status_code == 200  # co-1, March

    _auth["company"] = "co-2"
    resp, _, entries = _confirm(regenerate=True, company="co-2")
    assert resp.status_code == 200
    entries.replace_period.assert_called_once()
    assert client.get(f"/periods/{PERIOD}/close").json()["closed"] is False

    _auth["company"] = "co-1"
    assert client.get("/periods/2026-04-01/close").json()["closed"] is False
    assert _upload("2026-04-01")[0].status_code == 200


def test_quarterly_reports_do_not_use_the_lock() -> None:
    import backend.api.routers.quarterly as quarterly

    assert not hasattr(quarterly, "ensure_period_open")
    assert "period_lock" not in open(quarterly.__file__).read()


# --- reopen --------------------------------------------------------------


def test_reopen_needs_confirm_and_a_closed_month(period_closes_repo) -> None:
    assert client.post(f"/periods/{PERIOD}/reopen", json={}).status_code == 422
    nothing = client.post(f"/periods/{PERIOD}/reopen", json={"confirm": True})
    assert nothing.status_code == 409
    assert nothing.json()["detail"] == messages.PERIOD_NOT_CLOSED
    assert period_closes_repo.log == []


def test_reopen_keeps_the_close_logs_it_and_allows_a_new_analysis(
    period_closes_repo,
) -> None:
    _close()
    resp = client.post(f"/periods/{PERIOD}/reopen", json={"confirm": True})
    assert resp.status_code == 200
    body = resp.json()

    # What the user sees: open again, with the history of what happened.
    assert body["closed"] is False
    assert body["close"] is None
    assert [e["event"] for e in body["log"]] == ["closed", "reopened"]
    assert all(e["actor_email"] == "user-1@example.test" for e in body["log"])

    # The close is kept, not deleted.
    assert len(period_closes_repo.rows) == 1
    row = period_closes_repo.rows[0]
    assert row["closed_by"] == "user-1" and row["closed_at"]
    assert row["reopened_by"] == "user-1" and row["reopened_at"]

    # A new analysis is allowed again.
    resp, runs, entries = _confirm(regenerate=True)
    assert resp.status_code == 200
    entries.replace_period.assert_called_once()
    assert _upload()[0].status_code == 200

    # Closing again starts a fresh lock without erasing history.
    assert _close().status_code == 200
    assert len(period_closes_repo.rows) == 2
    assert [
        e["event"] for e in client.get(f"/periods/{PERIOD}/close").json()["log"]
    ] == [
        "closed",
        "reopened",
        "closed",
    ]
