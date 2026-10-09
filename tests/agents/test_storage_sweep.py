"""The 7-day upload sweep: second read, failures isolated, no filenames logged."""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone

from backend.agents.storage_sweep import sweep_abandoned_uploads

NOW = datetime(2026, 10, 9, 12, 0, tzinfo=timezone.utc)
USER = "3f2b8c1e-9a4d-4e6f-8b2a-1c3d5e7f9a0b"
SECRET_NAME = "john_smith_payroll.xlsx"


def _ts(age: timedelta) -> str:
    return (NOW - age).replace(tzinfo=None).isoformat()


def _row(company: str, period: str, age: timedelta) -> dict:
    return {
        "company_id": company,
        "period": period,
        "storage_key": f"{USER}/{period}/gl.xlsx",
        "created_at": _ts(age),
        "updated_at": _ts(age),
    }


class _Runs:
    def __init__(self, rows: list[dict], latest: dict[tuple[str, str], dict]):
        self.rows = rows
        self.latest = latest
        self.latest_calls: list[tuple[str, date]] = []

    def list_runs_with_storage_key(self) -> list[dict]:
        return self.rows

    def latest_run_activity(self, company_id: str, period: date) -> dict | None:
        self.latest_calls.append((company_id, period))
        return self.latest.get((company_id, str(period)))


class _Storage:
    def __init__(self, files: dict[str, list[str]], fail_on: set[str] = frozenset()):
        self.files = files
        self.fail_on = fail_on
        self.deleted: list[str] = []

    def list_folder(self, folder: str) -> list[str]:
        if folder in self.fail_on:
            raise RuntimeError("storage down")
        return [f"{folder}/{name}" for name in self.files.get(folder, [])]

    def delete_many(self, storage_keys: list[str]) -> None:
        self.deleted.extend(storage_keys)


def test_stale_folder_loses_every_file_including_extra_multi_file_uploads() -> None:
    row = _row("c-1", "2026-03-01", timedelta(days=8))
    runs = _Runs([row], {("c-1", "2026-03-01"): row})
    folder = f"{USER}/2026-03-01"
    storage = _Storage({folder: ["gl.xlsx", SECRET_NAME]})

    counts = sweep_abandoned_uploads(runs, storage, now=NOW)

    assert storage.deleted == [f"{folder}/gl.xlsx", f"{folder}/{SECRET_NAME}"]
    assert counts["folders_deleted"] == 1 and counts["files_deleted"] == 2
    assert runs.latest_calls == [("c-1", date(2026, 3, 1))]


def test_new_upload_seen_on_the_second_read_stops_the_delete() -> None:
    old = _row("c-1", "2026-03-01", timedelta(days=8))
    started_now = {"created_at": _ts(timedelta(seconds=5)), "updated_at": None}
    runs = _Runs([old], {("c-1", "2026-03-01"): started_now})
    storage = _Storage({f"{USER}/2026-03-01": ["gl.xlsx"]})

    counts = sweep_abandoned_uploads(runs, storage, now=NOW)

    assert storage.deleted == []
    assert counts["skipped_recent"] == 1


def test_missing_second_read_keeps_the_folder() -> None:
    old = _row("c-1", "2026-03-01", timedelta(days=8))
    storage = _Storage({f"{USER}/2026-03-01": ["gl.xlsx"]})
    sweep_abandoned_uploads(_Runs([old], {}), storage, now=NOW)
    assert storage.deleted == []


def test_recent_folder_is_not_touched() -> None:
    row = _row("c-1", "2026-03-01", timedelta(days=3))
    runs = _Runs([row], {("c-1", "2026-03-01"): row})
    storage = _Storage({f"{USER}/2026-03-01": ["gl.xlsx"]})

    counts = sweep_abandoned_uploads(runs, storage, now=NOW)

    assert storage.deleted == [] and counts["candidates"] == 0
    assert runs.latest_calls == []


def test_one_failing_folder_does_not_stop_the_others() -> None:
    march = _row("c-1", "2026-03-01", timedelta(days=9))
    april = _row("c-1", "2026-04-01", timedelta(days=9))
    runs = _Runs(
        [march, april],
        {("c-1", "2026-03-01"): march, ("c-1", "2026-04-01"): april},
    )
    storage = _Storage(
        {f"{USER}/2026-04-01": ["gl.xlsx"]}, fail_on={f"{USER}/2026-03-01"}
    )

    counts = sweep_abandoned_uploads(runs, storage, now=NOW)

    assert storage.deleted == [f"{USER}/2026-04-01/gl.xlsx"]
    assert counts["failed"] == 1 and counts["folders_deleted"] == 1


def test_already_empty_folder_is_a_no_op() -> None:
    row = _row("c-1", "2026-03-01", timedelta(days=30))
    runs = _Runs([row], {("c-1", "2026-03-01"): row})
    storage = _Storage({})

    counts = sweep_abandoned_uploads(runs, storage, now=NOW)

    assert storage.deleted == [] and counts["folders_deleted"] == 0


def test_logs_carry_counts_not_filenames(caplog) -> None:
    row = _row("c-1", "2026-03-01", timedelta(days=8))
    april = _row("c-1", "2026-04-01", timedelta(days=8))
    runs = _Runs(
        [row, april], {("c-1", "2026-03-01"): row, ("c-1", "2026-04-01"): april}
    )
    storage = _Storage(
        {f"{USER}/2026-03-01": [SECRET_NAME]}, fail_on={f"{USER}/2026-04-01"}
    )

    with caplog.at_level(logging.INFO):
        sweep_abandoned_uploads(runs, storage, now=NOW)

    assert caplog.records
    for record in caplog.records:
        blob = repr(record.__dict__)
        assert SECRET_NAME not in blob
        assert USER not in blob
