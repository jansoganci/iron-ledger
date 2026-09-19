"""Schema retry and invented-token merge for the monthly interpreter.

The live Riverbend failure died inside llm.call on
exception_three_way_matches. These tests stay offline: no Anthropic, no
Supabase. Numbers still come from pandas; the guardrail is not weakened.
"""

from __future__ import annotations

import json
import uuid
from datetime import date

from pydantic import ValidationError

from backend import messages
from backend.agents.interpreter import (
    InterpreterAgent,
    _apply_reconciliation_classifications,
)
from backend.domain.contracts import (
    AccountSummary,
    NarrativeJSON,
    PandasSummary,
)
from backend.domain.errors import GuardrailError
from backend.domain.run_state_machine import RunStatus
from backend.tools.close_controls import unpack_report_reconciliations

PERIOD = date(2026, 3, 1)
COMPANY = uuid.uuid4()
RUN_ID = "run-schema-retry"


class _FakeRunsRepo:
    def __init__(self) -> None:
        self.status = RunStatus.COMPARING.value
        self.updates: list[tuple[str, dict]] = []

    def get_by_id(self, run_id: str) -> dict:
        return {"id": run_id, "status": self.status}

    def update_status(self, run_id: str, status, extra: dict | None = None) -> None:
        self.status = status.value if hasattr(status, "value") else str(status)
        self.updates.append((self.status, extra or {}))


class _FakeReportsRepo:
    def __init__(self) -> None:
        self.written: list = []

    def write(self, report):
        self.written.append(report)
        return report


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


def _ok_narrative() -> NarrativeJSON:
    return NarrativeJSON(
        narrative="Revenue was 1000.00 for the period.",
        numbers_used=[1000.00],
        reconciliation_classifications={},
    )


def _match(**overrides) -> dict:
    payload = {
        "match_id": "po-missing",
        "processor_ref": "po_1Qz9Pw7eZvRB",
        "bank_ref": None,
        "gl_ref": None,
        "gl_account": "Undeposited Funds",
        "gl_amount": None,
        "gross": 1000.0,
        "fee": 0.0,
        "net": 1000.0,
        "settlement_date": date(2026, 3, 15),
        "match_kind": "none",
        "ambiguous": False,
        "candidate_count": 1,
        "unmatched": True,
        "classification": "missing_je",
    }
    payload.update(overrides)
    return payload


def _uf_item() -> dict:
    return {
        "account": "Undeposited Funds",
        "category": "REVENUE",
        "sources": [],
        "gl_amount": 1000.0,
        "non_gl_total": 1000.0,
        "delta": 0.0,
        "hints": {},
        "matches": [_match()],
    }


def _interpreter(llm, runs=None, reports=None) -> InterpreterAgent:
    return InterpreterAgent(
        llm_client=llm,
        reports_repo=reports or _FakeReportsRepo(),
        runs_repo=runs or _FakeRunsRepo(),
        file_storage=_FakeStorage(),
    )


def _schema_error() -> ValidationError:
    try:
        NarrativeJSON.model_validate(
            {"narrative": "Revenue was 1000.00.", "numbers_used": "not-a-list"}
        )
    except ValidationError as exc:
        return exc
    raise AssertionError("expected ValidationError")


# ---------------------------------------------------------------------------
# A — coercion then pandas merge
# ---------------------------------------------------------------------------


def test_invented_token_residue_still_wins() -> None:
    parsed = NarrativeJSON.model_validate(
        {
            "narrative": "Revenue was 1000.00.",
            "numbers_used": [1000.00],
            "reconciliation_classifications": {
                "Undeposited Funds": "exception_three_way_matches",
            },
        }
    )
    items = [_uf_item()]
    _apply_reconciliation_classifications(
        items, parsed.reconciliation_classifications or {}
    )
    assert items[0]["classification"] == "missing_je"


def test_unknown_token_falls_back_to_hints() -> None:
    parsed = NarrativeJSON.model_validate(
        {
            "narrative": "Office Rent is 200.00.",
            "numbers_used": [200.00],
            "reconciliation_classifications": {"Office Rent": "made_this_up"},
        }
    )
    items = [
        {
            "account": "Office Rent",
            "hints": {},
            "classification": None,
        }
    ]
    _apply_reconciliation_classifications(
        items, parsed.reconciliation_classifications or {}
    )
    assert items[0]["classification"] == "stale_reference"


def test_invented_token_does_not_kill_the_run() -> None:
    """Coerced token; pandas residue is stored; report is written."""

    class _InventedTokenLLM:
        def call(self, **kwargs):
            return kwargs["schema"].model_validate(
                {
                    "narrative": "Revenue was 1000.00 for the period.",
                    "numbers_used": [1000.00],
                    "reconciliation_classifications": {
                        "Undeposited Funds": "exception_three_way_matches",
                    },
                }
            )

    runs = _FakeRunsRepo()
    reports = _FakeReportsRepo()
    agent = _interpreter(_InventedTokenLLM(), runs=runs, reports=reports)
    ok = agent.run(_summary(), [], RUN_ID, reconciliations=[_uf_item()])

    assert ok is True
    assert runs.status == RunStatus.COMPLETE.value
    stored_items, _ = unpack_report_reconciliations(reports.written[0].reconciliations)
    stored = stored_items[0]
    assert stored["classification"] == "missing_je"


# ---------------------------------------------------------------------------
# B — schema retry, distinct from guardrail
# ---------------------------------------------------------------------------


class _SchemaThenOkLLM:
    def __init__(self) -> None:
        self.prompts: list[str] = []

    def call(self, **kwargs):
        self.prompts.append(kwargs["prompt"])
        if len(self.prompts) == 1:
            raise _schema_error()
        return _ok_narrative()


def test_schema_error_retries_with_reinforced_prompt() -> None:
    llm = _SchemaThenOkLLM()
    runs = _FakeRunsRepo()
    reports = _FakeReportsRepo()
    agent = _interpreter(llm, runs=runs, reports=reports)
    ok = agent.run(_summary(), [], RUN_ID)

    assert ok is True
    assert llm.prompts == [
        "narrative_prompt.txt",
        "narrative_prompt_reinforced.txt",
    ]
    assert runs.status == RunStatus.COMPLETE.value
    assert reports.written


def test_json_decode_error_retries_once() -> None:
    class _BrokenThenOk:
        def __init__(self) -> None:
            self.calls = 0

        def call(self, **kwargs):
            self.calls += 1
            if self.calls == 1:
                raise json.JSONDecodeError("Expecting value", "", 0)
            return _ok_narrative()

    llm = _BrokenThenOk()
    ok = _interpreter(llm).run(_summary(), [], RUN_ID)
    assert ok is True
    assert llm.calls == 2


def test_exhausted_schema_retry_is_not_an_internal_error() -> None:
    class _AlwaysBroken:
        def call(self, **kwargs):
            raise _schema_error()

    runs = _FakeRunsRepo()
    reports = _FakeReportsRepo()
    ok = _interpreter(_AlwaysBroken(), runs=runs, reports=reports).run(
        _summary(), [], RUN_ID
    )

    assert ok is False
    assert runs.status == RunStatus.GUARDRAIL_FAILED.value
    assert reports.written == []
    last_extra = runs.updates[-1][1]
    assert last_extra["error_message"] == messages.NARRATIVE_SCHEMA_FAILED
    assert last_extra["error_message"] != messages.INTERNAL_ERROR
    assert "verified" not in last_extra["error_message"].lower()


def test_guardrail_mismatch_still_fails_closed() -> None:
    class _WrongNumber:
        def __init__(self) -> None:
            self.prompts: list[str] = []

        def call(self, **kwargs):
            self.prompts.append(kwargs["prompt"])
            return NarrativeJSON(
                narrative="Revenue was 999999.00 for the period.",
                numbers_used=[999999.00],
                reconciliation_classifications={},
            )

    llm = _WrongNumber()
    runs = _FakeRunsRepo()
    reports = _FakeReportsRepo()
    agent = _interpreter(llm, runs=runs, reports=reports)
    ok = agent.run(_summary(), [], RUN_ID)

    assert ok is False
    assert llm.prompts == [
        "narrative_prompt.txt",
        "narrative_prompt_reinforced.txt",
    ]
    assert runs.status == RunStatus.GUARDRAIL_FAILED.value
    assert reports.written == []
    last_extra = runs.updates[-1][1]
    assert last_extra["error_message"] != messages.NARRATIVE_SCHEMA_FAILED
    assert last_extra["error_message"] != messages.INTERNAL_ERROR
    assert "raw_data_url" in last_extra


def test_guardrail_mismatch_raises_guardrail_error() -> None:
    class _WrongNumber:
        def call(self, **kwargs):
            return NarrativeJSON(
                narrative="Revenue was 999999.00.",
                numbers_used=[999999.00],
                reconciliation_classifications={},
            )

    agent = _interpreter(_WrongNumber())
    try:
        agent._run_with_guardrail(_summary(), [], RUN_ID)
    except GuardrailError as exc:
        assert "Mismatch" in str(exc) or "verified" in str(exc).lower()
        return
    raise AssertionError("expected GuardrailError")
