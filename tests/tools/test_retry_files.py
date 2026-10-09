"""Which files Retry may re-run. Pure, no database."""

from __future__ import annotations

from datetime import date

from backend.tools.retry_files import files_for_retry

USER = "3f2b8c1e-9a4d-4e6f-8b2a-1c3d5e7f9a0b"
PERIOD = date(2026, 3, 1)
GL = f"{USER}/2026-03-01/gl.xlsx"
PAYROLL = f"{USER}/2026-03-01/payroll.xlsx"
OTHER = "7a1c2e3f-4b5d-4c6e-9f8a-0b1c2d3e4f5a"


def _run(**extra) -> dict:
    run = {"storage_key": GL, "file_count": 1, "parse_preview": {}}
    run.update(extra)
    return run


def test_single_file_run_retries_its_one_key() -> None:
    assert files_for_retry(_run(), USER, PERIOD).keys == (GL,)


def test_stored_list_is_kept_in_order() -> None:
    run = _run(file_count=2, parse_preview={"storage_keys": [PAYROLL, GL]})
    assert files_for_retry(run, USER, PERIOD).keys == (PAYROLL, GL)


def test_multi_file_run_without_a_list_is_refused() -> None:
    decision = files_for_retry(_run(file_count=2), USER, PERIOD)
    assert decision.refusal == "reupload" and decision.keys == ()


def test_a_key_outside_this_users_folder_is_refused() -> None:
    foreign = f"{OTHER}/2026-03-01/gl.xlsx"
    for keys in (
        [GL, foreign],
        [f"{USER}/2026-04-01/gl.xlsx"],
        ["gl.xlsx"],
        [f"{USER}/2026-03-01/../gl.xlsx"],
        [""],
        "not-a-list",
    ):
        run = _run(parse_preview={"storage_keys": keys})
        assert files_for_retry(run, USER, PERIOD).refusal == "reupload", keys


def test_empty_list_is_refused_rather_than_falling_back_to_the_first_file() -> None:
    run = _run(file_count=2, parse_preview={"storage_keys": []})
    assert files_for_retry(run, USER, PERIOD).refusal == "reupload"


def test_missing_single_file_asks_for_an_upload() -> None:
    decision = files_for_retry(_run(storage_key=None), USER, PERIOD)
    assert decision.refusal == "no_file"


def test_list_written_by_consolidation_is_what_the_next_retry_reads() -> None:
    stored = [GL, PAYROLL]
    decision = files_for_retry(
        _run(
            file_count=2, storage_key=stored[0], parse_preview={"storage_keys": stored}
        ),
        USER,
        PERIOD,
    )
    assert decision.refusal is None and decision.keys == tuple(stored)
