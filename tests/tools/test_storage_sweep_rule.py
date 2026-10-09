"""Which upload folders the 7-day sweep may delete. Pure, no clock."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from backend.tools.storage_sweep_rule import (
    RETENTION,
    folder_for_key,
    folders_to_sweep,
    last_activity,
    parse_timestamp,
)

NOW = datetime(2026, 10, 9, 12, 0, tzinfo=timezone.utc)
USER = "3f2b8c1e-9a4d-4e6f-8b2a-1c3d5e7f9a0b"
OTHER_USER = "7a1c2e3f-4b5d-4c6e-9f8a-0b1c2d3e4f5a"
PERIOD = "2026-03-01"
KEY = f"{USER}/{PERIOD}/redhawk_gl_mar_2026.xlsx"


def _ts(age: timedelta) -> str:
    """Naive UTC, the way runs.updated_at is stored."""
    return (NOW - age).replace(tzinfo=None).isoformat()


def _row(age: timedelta, *, company="c-1", period=PERIOD, key=KEY) -> dict:
    return {
        "company_id": company,
        "period": period,
        "storage_key": key,
        "created_at": _ts(age + timedelta(hours=1)),
        "updated_at": _ts(age),
    }


# --- folder_for_key -------------------------------------------------------


def test_well_formed_key_gives_user_and_period_folder() -> None:
    assert folder_for_key(KEY, PERIOD) == f"{USER}/{PERIOD}"


def test_malformed_keys_are_never_swept() -> None:
    for key in (
        None,
        "",
        "file.xlsx",
        f"{PERIOD}/file.xlsx",
        f"not-a-uuid/{PERIOD}/file.xlsx",
        f"{USER}/2026-13-01/file.xlsx",
        f"{USER}/../file.xlsx",
        f"{USER}/{PERIOD}/",
        f"{USER}/{PERIOD}/sub/file.xlsx",
        f"/{USER}/{PERIOD}/file.xlsx",
    ):
        assert folder_for_key(key, PERIOD) is None, key


def test_key_from_another_period_is_not_swept_under_this_period() -> None:
    assert folder_for_key(f"{USER}/2026-04-01/file.xlsx", PERIOD) is None


# --- timestamps -----------------------------------------------------------


def test_timestamps_are_read_as_utc() -> None:
    naive = parse_timestamp("2026-10-09T12:00:00.123456")
    zulu = parse_timestamp("2026-10-09T12:00:00Z")
    offset = parse_timestamp("2026-10-09T15:00:00+03:00")
    assert naive.tzinfo is not None
    assert zulu == offset == NOW
    assert parse_timestamp("garbage") is None
    assert parse_timestamp(None) is None


def test_last_activity_uses_the_later_stamp() -> None:
    row = {"created_at": _ts(timedelta(days=10)), "updated_at": _ts(timedelta(days=2))}
    assert NOW - last_activity(row) == timedelta(days=2)
    assert last_activity({"created_at": None, "updated_at": "bad"}) is None


# --- folders_to_sweep -----------------------------------------------------


def test_retention_is_seven_days() -> None:
    assert RETENTION == timedelta(days=7)


def test_folder_older_than_seven_days_is_swept() -> None:
    swept = folders_to_sweep([_row(timedelta(days=8))], NOW)
    assert [(s.company_id, s.period, s.folder) for s in swept] == [
        ("c-1", PERIOD, f"{USER}/{PERIOD}")
    ]


def test_seven_day_boundary() -> None:
    assert folders_to_sweep([_row(RETENTION)], NOW) == []
    assert folders_to_sweep([_row(RETENTION + timedelta(seconds=1))], NOW)


def test_guardrail_failed_run_inside_retention_keeps_its_file_for_retry() -> None:
    assert folders_to_sweep([_row(timedelta(days=6, hours=23))], NOW) == []


def test_newest_run_of_the_month_decides() -> None:
    old = _row(timedelta(days=30))
    fresh = _row(timedelta(hours=2))
    assert folders_to_sweep([old, fresh], NOW) == []


def test_unreadable_timestamp_keeps_the_folder() -> None:
    old = _row(timedelta(days=30))
    unknown = {**_row(timedelta(days=30)), "created_at": None, "updated_at": None}
    assert folders_to_sweep([old, unknown], NOW) == []
    assert folders_to_sweep([unknown, old], NOW) == []


def test_months_and_companies_are_judged_separately() -> None:
    april_key = f"{OTHER_USER}/2026-04-01/gl.xlsx"
    rows = [
        _row(timedelta(days=9)),
        _row(timedelta(days=1), company="c-2", period="2026-04-01", key=april_key),
    ]
    assert [s.folder for s in folders_to_sweep(rows, NOW)] == [f"{USER}/{PERIOD}"]


def test_folder_still_used_by_an_active_group_is_not_swept() -> None:
    rows = [
        _row(timedelta(days=9), company="c-1"),
        _row(timedelta(days=1), company="c-2"),
    ]
    assert folders_to_sweep(rows, NOW) == []


def test_rows_without_company_or_period_are_ignored() -> None:
    rows = [{**_row(timedelta(days=9)), "company_id": None}]
    assert folders_to_sweep(rows, NOW) == []
