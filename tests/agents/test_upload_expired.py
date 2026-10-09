"""A file removed by the 7-day sweep ends the run with a plain message."""

from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock

import pytest

from backend import messages
from backend.agents import orchestrator
from backend.agents.parser import ParserAgent
from backend.domain.errors import StoredFileMissing
from backend.domain.run_state_machine import RunStatus

KEY = "3f2b8c1e-9a4d-4e6f-8b2a-1c3d5e7f9a0b/2026-03-01/gl.xlsx"
PERIOD = date(2026, 3, 1)


def _parser(runs: MagicMock) -> ParserAgent:
    storage = MagicMock()
    storage.download.side_effect = StoredFileMissing(KEY)
    return ParserAgent(storage, MagicMock(), MagicMock(), runs, MagicMock())


def _last_error(runs: MagicMock) -> tuple:
    args, kwargs = runs.update_status.call_args
    return args[1], kwargs["extra"]["error_message"]


def test_discover_on_an_expired_file_says_upload_again() -> None:
    runs = MagicMock()
    runs.get_by_id.return_value = {"status": RunStatus.PENDING.value}

    with pytest.raises(StoredFileMissing):
        _parser(runs).discover("run-1", "c-1", KEY, PERIOD)

    status, error = _last_error(runs)
    assert status == RunStatus.PARSING_FAILED
    assert error == messages.UPLOAD_EXPIRED


def test_confirm_after_expiry_says_upload_again() -> None:
    runs = MagicMock()

    with pytest.raises(StoredFileMissing):
        _parser(runs).resume_from_plan("run-1", "c-1", KEY, PERIOD, MagicMock())

    status, error = _last_error(runs)
    assert status == RunStatus.PARSING_FAILED
    assert error == messages.UPLOAD_EXPIRED


def test_multi_file_run_on_an_expired_file_says_upload_again(monkeypatch) -> None:
    runs = MagicMock()
    runs.get_by_id.return_value = {"status": RunStatus.PARSING.value}
    parser = MagicMock()
    parser.parse_file_silently.side_effect = StoredFileMissing(KEY)
    monkeypatch.setattr(orchestrator, "ParserAgent", lambda **_: parser)
    monkeypatch.setattr(orchestrator, "get_runs_repo", lambda: runs)
    for name in ("get_file_storage", "get_llm_client", "get_accounts_repo"):
        monkeypatch.setattr(orchestrator, name, MagicMock)

    orchestrator.run_multi_file_parser_until_preview("run-1", [KEY], "c-1", PERIOD)

    status, error = _last_error(runs)
    assert status == RunStatus.PARSING_FAILED
    assert error == messages.UPLOAD_EXPIRED


def test_expired_message_is_plain_and_actionable() -> None:
    assert "7 days" in messages.UPLOAD_EXPIRED
    assert "upload" in messages.UPLOAD_EXPIRED.lower()
