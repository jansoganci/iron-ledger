"""A duplicate monthly report fails cleanly and never replaces what exists.

Regression for the live failure on run a84d3e60: the narrative and guardrail
both succeeded, the reports insert hit `reports_monthly_unique`, and because
GENERATING had no edge to any failed state the run sat in `generating`
forever with no user-facing error.

Two rules pinned here, and the first is the one that matters most:

  1. A second write for the same (company_id, period) does NOT delete or
     overwrite the existing report. Silently replacing a verified report is
     not a decision a re-run may make on its own.
  2. The run reaches a terminal REPORT_FAILED state carrying a message that
     names the conflict, rather than stalling.
"""

from __future__ import annotations

import uuid
from datetime import date

import pytest

from backend import messages
from backend.agents.interpreter import InterpreterAgent
from backend.domain.contracts import AccountSummary, NarrativeJSON, PandasSummary
from backend.domain.entities import Report
from backend.domain.errors import DuplicateEntryError
from backend.domain.run_state_machine import RunStateMachine, RunStatus

PERIOD = date(2026, 3, 1)
COMPANY = uuid.uuid4()
RUN_ID = "run-under-test"


# ---------------------------------------------------------------------------
# The state machine edge itself
# ---------------------------------------------------------------------------


def test_generating_can_reach_report_failed() -> None:
    """Without this edge the run had nowhere to go and stalled at 98%."""
    assert (
        RunStateMachine.transition(RunStatus.GENERATING, RunStatus.REPORT_FAILED)
        is RunStatus.REPORT_FAILED
    )


def test_report_failed_is_terminal() -> None:
    with pytest.raises(Exception):
        RunStateMachine.transition(RunStatus.REPORT_FAILED, RunStatus.COMPLETE)


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


class _ExistingReportRepo:
    """Stands in for the unique index: a second write for a period is refused.

    Records every write so the test can prove the stored report was left
    exactly as it was — no delete, no overwrite.
    """

    def __init__(self, existing: Report | None = None) -> None:
        self.stored: dict[tuple[str, date], Report] = {}
        if existing is not None:
            self.stored[(existing.company_id, existing.period)] = existing
        self.write_attempts: list[Report] = []

    def write(self, report: Report) -> Report:
        self.write_attempts.append(report)
        key = (report.company_id, report.period)
        if key in self.stored:
            raise DuplicateEntryError(
                "duplicate key value violates unique constraint "
                '"reports_monthly_unique"'
            )
        self.stored[key] = report
        return report


class _FailingReportRepo(_ExistingReportRepo):
    """A database failure that is NOT a duplicate."""

    def write(self, report: Report) -> Report:
        self.write_attempts.append(report)
        raise RuntimeError("connection reset by peer")


class _FakeRunsRepo:
    def __init__(self) -> None:
        self.status = RunStatus.COMPARING.value
        self.updates: list[tuple[str, dict]] = []

    def get_by_id(self, run_id: str) -> dict:
        return {"id": run_id, "status": self.status}

    def update_status(self, run_id: str, status, extra: dict | None = None) -> None:
        self.status = status.value if hasattr(status, "value") else str(status)
        self.updates.append((self.status, extra or {}))


class _FakeLLM:
    """Returns a narrative whose numbers match pandas exactly, so the
    guardrail passes and execution reaches the report write."""

    def call(self, **kwargs):
        return NarrativeJSON(
            narrative="Revenue was 1000.00 for the period.",
            numbers_used=[1000.00],
            reconciliation_classifications={},
        )


class _FakeStorage:
    def upload(self, *a, **k):
        return "key"

    def download(self, *a, **k):
        return b""

    def delete(self, *a, **k):
        return None


def _summary() -> PandasSummary:
    return PandasSummary(
        accounts={
            "Service Revenue": AccountSummary(
                account="Service Revenue",
                category="REVENUE",
                current=1000.00,
                historical_avg=1000.00,
                variance_pct=0.0,
                severity="low",
            )
        },
        period=PERIOD,
        company_id=COMPANY,
    )


def _existing_report() -> Report:
    return Report(
        id="the-original-report",
        company_id=str(COMPANY),
        period=PERIOD,
        summary="ORIGINAL — must survive untouched",
        anomaly_count=7,
        error_count=0,
    )


def _interpreter(reports_repo, runs_repo) -> InterpreterAgent:
    return InterpreterAgent(
        llm_client=_FakeLLM(),
        reports_repo=reports_repo,
        runs_repo=runs_repo,
        file_storage=_FakeStorage(),
    )


# ---------------------------------------------------------------------------
# Rule 1 — the existing report is never replaced
# ---------------------------------------------------------------------------


def test_second_run_leaves_the_existing_report_untouched() -> None:
    original = _existing_report()
    reports = _ExistingReportRepo(existing=original)
    runs = _FakeRunsRepo()

    ok = _interpreter(reports, runs).run(_summary(), [], RUN_ID)

    assert ok is False
    survivor = reports.stored[(str(COMPANY), PERIOD)]
    assert survivor is original
    assert survivor.id == "the-original-report"
    assert survivor.summary == "ORIGINAL — must survive untouched"
    assert survivor.anomaly_count == 7
    # Exactly one period key — nothing deleted and re-added under another id.
    assert len(reports.stored) == 1


# ---------------------------------------------------------------------------
# Rule 2 — terminal state with a message that names the conflict
# ---------------------------------------------------------------------------


def test_duplicate_ends_in_report_failed_not_a_generating_stall() -> None:
    reports = _ExistingReportRepo(existing=_existing_report())
    runs = _FakeRunsRepo()

    _interpreter(reports, runs).run(_summary(), [], RUN_ID)

    assert runs.status == RunStatus.REPORT_FAILED.value
    assert runs.status != RunStatus.GENERATING.value
    final_extra = runs.updates[-1][1]
    assert final_extra["error_message"] == messages.REPORT_ALREADY_EXISTS
    assert "already exists" in final_extra["error_message"]


def test_duplicate_message_is_distinct_from_a_database_failure() -> None:
    """A conflict tells the user to delete the report; a DB error tells them
    to retry. Collapsing the two would give the wrong instruction."""
    dup_runs = _FakeRunsRepo()
    _interpreter(_ExistingReportRepo(existing=_existing_report()), dup_runs).run(
        _summary(), [], RUN_ID
    )

    err_runs = _FakeRunsRepo()
    _interpreter(_FailingReportRepo(), err_runs).run(_summary(), [], RUN_ID)

    assert dup_runs.status == RunStatus.REPORT_FAILED.value
    assert err_runs.status == RunStatus.REPORT_FAILED.value

    dup_msg = dup_runs.updates[-1][1]["error_message"]
    err_msg = err_runs.updates[-1][1]["error_message"]
    assert dup_msg == messages.REPORT_ALREADY_EXISTS
    assert err_msg == messages.REPORT_WRITE_FAILED
    assert dup_msg != err_msg


def test_first_write_for_a_fresh_period_still_succeeds() -> None:
    """The guard must not block the ordinary path."""
    reports = _ExistingReportRepo()
    runs = _FakeRunsRepo()

    ok = _interpreter(reports, runs).run(_summary(), [], RUN_ID)

    assert ok is True
    assert runs.status == RunStatus.COMPLETE.value
    assert len(reports.stored) == 1


# ---------------------------------------------------------------------------
# The adapter itself must never issue a DELETE
# ---------------------------------------------------------------------------


class _RecordingTable:
    """Records which operations the repo performs against `reports`."""

    def __init__(self, log: list[str]) -> None:
        self._log = log

    def insert(self, row):
        self._log.append("insert")
        self._resp = type("R", (), {"data": [dict(row)]})()
        return self

    def delete(self):
        self._log.append("delete")
        return self

    def eq(self, *_a, **_k):
        return self

    def execute(self):
        return getattr(self, "_resp", type("R", (), {"data": []})())


class _RecordingClient:
    def __init__(self) -> None:
        self.ops: list[str] = []

    def table(self, name: str):
        self.ops.append(f"table:{name}")
        return _RecordingTable(self.ops)


def test_reports_repo_write_issues_no_delete() -> None:
    """Pins the reverted behaviour.

    An earlier version made `write` delete the existing monthly report before
    inserting. That silently destroyed a verified report — and, as it turned
    out, invited the surrounding rows to be cleaned up with it. The adapter
    inserts and nothing else; the unique index decides what happens on a
    duplicate.
    """
    from backend.adapters.supabase_repos import SupabaseReportsRepo

    client = _RecordingClient()
    SupabaseReportsRepo(client).write(_existing_report())

    assert "delete" not in client.ops, f"write() issued a DELETE: {client.ops}"
    assert "insert" in client.ops


# ---------------------------------------------------------------------------
# Bug 2 — the Opus upgrade prompt must name the six tokens
# ---------------------------------------------------------------------------


def test_opus_prompt_pins_the_six_classification_tokens() -> None:
    """Regression for the every-run opus_upgrade validation failure.

    `NarrativeJSON.reconciliation_classifications` is typed to the six
    snake_case tokens, but `opus_narrative_prompt.txt` only ever asked for
    "<classification string>" and never listed them. Opus answered with prose
    labels — 'missing journal entry', 'accrual mismatch' — every value failed
    the Literal, and the whole upgrade was discarded with opus_status=failed.

    Claude cannot be expected to hit a closed vocabulary it was never shown.
    """
    from pathlib import Path

    from backend.domain.contracts import ReconciliationClassification

    prompt = Path("backend/prompts/opus_narrative_prompt.txt").read_text().casefold()
    tokens = ReconciliationClassification.__args__

    assert len(tokens) == 6
    for token in tokens:
        assert token in prompt, f"{token} is not named in the Opus prompt"

    # The prose forms Opus actually returned must be explicitly ruled out,
    # not merely absent by luck.
    assert "missing journal entry" in prompt
    assert "accrual mismatch" in prompt
