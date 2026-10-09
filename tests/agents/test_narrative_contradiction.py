"""The narrative must agree with the control cards. No LLM, no database.

A coverage account (GL line with no supporting file) is "not compared". A
narrative that calls it a missing journal entry, or high severity, is rejected,
retried once, and never published if it happens twice. The number guardrail is
unchanged and still fails after two attempts.
"""

from __future__ import annotations

import uuid
from datetime import date
from unittest.mock import MagicMock

from backend import messages
from backend.agents.interpreter import InterpreterAgent
from backend.domain.contracts import AccountSummary, NarrativeJSON, PandasSummary
from backend.domain.run_state_machine import RunStatus
from backend.tools.narrative_check import (
    coverage_accounts,
    find_coverage_contradictions,
    find_unbacked_missing_je,
    has_missing_je_card,
)
from tests.agents.test_interpreter_schema_retry import (
    COMPANY,
    PERIOD,
    RUN_ID,
    _FakeReportsRepo,
    _FakeRunsRepo,
    _interpreter,
)

COVERAGE = {
    "account": "Installation Revenue",
    "category": "REVENUE",
    "card_kind": "coverage",
    "gl_amount": 28400.0,
    "non_gl_total": 0.0,
    "delta": -28400.0,
    "hints": {"is_gl_only": True},
}
SOURCE_ONLY = {
    "account": "Owner Bonus",
    "category": "OPEX",
    "gl_amount": None,
    "non_gl_total": 500.0,
    "delta": 500.0,
    "hints": {"is_source_only": True},
}
STALE = {
    "account": "Service Revenue",
    "category": "REVENUE",
    "gl_amount": 3540.0,
    "non_gl_total": 3825.0,
    "delta": 285.0,
    "hints": {"n_active": 85, "n_billed_in_period": 82, "count_delta": 3},
}
RECONS = [COVERAGE, SOURCE_ONLY, STALE]

BAD = (
    "Installation Revenue was 28400.00. This is a high-severity gap, "
    "classification missing_je."
)
BAD_PHRASE = (
    "Installation Revenue was 28400.00. A journal entry may be missing for "
    "Installation Revenue."
)
GOOD = (
    "Installation Revenue was 28400.00. The general ledger shows it, but no "
    "uploaded file includes this account, so it was not compared. This is not a "
    "missing journal entry."
)


def _summary() -> PandasSummary:
    return PandasSummary(
        accounts={
            "Installation Revenue": AccountSummary(
                account="Installation Revenue",
                category="REVENUE",
                current=28400.00,
                historical_avg=28400.00,
                variance_pct=0.0,
                severity="low",
            )
        },
        period=PERIOD,
        company_id=COMPANY,
    )


def _narr(text: str, numbers=(28400.00,)) -> NarrativeJSON:
    return NarrativeJSON(
        narrative=text,
        numbers_used=list(numbers),
        reconciliation_classifications={},
    )


class _ScriptedLLM:
    def __init__(self, *narratives: NarrativeJSON) -> None:
        self.narratives = list(narratives)
        self.prompts: list[str] = []
        self.contexts: list[dict] = []

    def call(self, **kwargs):
        self.prompts.append(kwargs["prompt"])
        self.contexts.append(kwargs["context"])
        return self.narratives[len(self.prompts) - 1]


def _run(llm, recons=None):
    runs, reports = _FakeRunsRepo(), _FakeReportsRepo()
    ok = _interpreter(llm, runs=runs, reports=reports).run(
        _summary(), [], RUN_ID, reconciliations=recons or [dict(i) for i in RECONS]
    )
    return ok, runs, reports


# --- the pure check ------------------------------------------------------


def test_only_coverage_items_are_coverage_accounts() -> None:
    assert coverage_accounts(RECONS) == {"Installation Revenue"}
    assert coverage_accounts(None) == set()


def test_missing_je_and_severity_on_a_coverage_account_are_rejected() -> None:
    covered = {"Installation Revenue", "Rent & Utilities"}
    for text in (
        BAD,
        BAD_PHRASE,
        "Rent & Utilities has a missing journal entry.",
        "Rent & Utilities: Classification: missing_je. Action: attach the lease.",
        "The Rent & Utilities balance is a high severity item.",
        "Installation Revenue needs the missing JE posted.",
    ):
        assert find_coverage_contradictions(text, covered), text


def test_not_compared_wording_passes() -> None:
    covered = {"Installation Revenue", "Rent & Utilities"}
    for text in (
        GOOD,
        "The general ledger shows $1,650.00 for Rent & Utilities. None of the "
        "files you uploaded include this account, so it was not compared. This "
        "is not a missing journal entry.",
        "Rent & Utilities isn't a missing JE; it was not compared.",
    ):
        assert find_coverage_contradictions(text, covered) == [], text


def test_real_source_only_missing_je_and_stale_reference_pass() -> None:
    covered = coverage_accounts(RECONS)
    text = (
        "Owner Bonus shows 500.00 in payroll.xlsx with no matching entry in the "
        "GL. A journal entry may be missing. Classification: missing_je.\n"
        "Service Revenue has a 285.00 gap, classification stale_reference. "
        "Installation Revenue was not compared. This is not a missing journal "
        "entry."
    )
    assert find_coverage_contradictions(text, covered) == []


def test_other_accounts_are_not_confused_with_coverage_names() -> None:
    covered = {"Insurance"}
    known = {"Insurance", "Auto Insurance Premium"}
    text = "Auto Insurance Premium has a missing journal entry."
    assert find_coverage_contradictions(text, covered, known) == []
    assert find_coverage_contradictions(
        "Insurance has a missing journal entry.", covered, known
    )


def test_a_sentence_without_an_account_belongs_to_the_last_named_one() -> None:
    covered = {"Installation Revenue"}
    known = covered | {"Owner Bonus"}
    paragraph = (
        "Installation Revenue gap of 28400.00. Classification: missing_je. "
        "Action: attach billing detail."
    )
    assert find_coverage_contradictions(paragraph, covered, known) == [
        "Classification: missing_je."
    ]
    other = "Owner Bonus gap of 500.00. Classification: missing_je."
    assert find_coverage_contradictions(other, covered, known) == []


# Second paragraph names no account, so the coverage check cannot see it.
GENERIC = (
    "Installation Revenue was 28400.00 and was not compared.\n"
    "Some journal entries may be missing."
)


def test_generic_missing_je_without_a_missing_je_card_is_rejected() -> None:
    for text in (
        "Some journal entries may be missing.",
        "Several accounts appear to be missing journal entries.",
        "There may be unrecorded journal entries this month.",
        "Watch for a missing JE before you close.",
    ):
        assert find_unbacked_missing_je(text, backed=False) == [text], text


def test_generic_missing_je_with_a_missing_je_card_passes() -> None:
    assert find_unbacked_missing_je("Some journal entries may be missing.", True) == []


def test_negated_missing_je_passes_without_a_card() -> None:
    for text in (
        "No missing journal entries were found.",
        "Installation Revenue was not compared. This is not a missing journal entry.",
    ):
        assert find_unbacked_missing_je(text, backed=False) == [], text


def test_only_a_non_coverage_missing_je_card_backs_the_wording() -> None:
    assert has_missing_je_card([{**SOURCE_ONLY, "classification": "missing_je"}])
    assert not has_missing_je_card([{**STALE, "classification": "stale_reference"}])
    assert not has_missing_je_card([{**COVERAGE, "classification": "missing_je"}])
    assert not has_missing_je_card(None)


# --- interpreter ---------------------------------------------------------


def test_coverage_missing_je_is_retried_once_then_published_when_fixed() -> None:
    llm = _ScriptedLLM(_narr(BAD), _narr(GOOD))
    ok, runs, reports = _run(llm)

    assert ok is True
    assert llm.prompts == ["narrative_prompt.txt", "narrative_prompt_reinforced.txt"]
    assert "narrative_corrections" not in llm.contexts[0]
    assert any(
        "Installation Revenue" in s for s in llm.contexts[1]["narrative_corrections"]
    )
    assert runs.status == RunStatus.COMPLETE.value
    assert reports.written[0].summary == GOOD


def test_coverage_not_compared_passes_first_try() -> None:
    llm = _ScriptedLLM(_narr(GOOD))
    ok, runs, reports = _run(llm)
    assert ok is True and len(llm.prompts) == 1
    assert reports.written


def test_source_only_missing_je_passes_first_try() -> None:
    text = (
        "Installation Revenue was 28400.00 and was not compared. "
        "Owner Bonus shows 500.00 in payroll.xlsx with no matching entry in the "
        "GL. A journal entry may be missing."
    )
    llm = _ScriptedLLM(_narr(text, (28400.00, 500.00)))
    ok, _, reports = _run(llm)
    assert ok is True and len(llm.prompts) == 1
    assert reports.written


def test_generic_missing_je_with_no_missing_je_card_is_retried_then_fixed() -> None:
    llm = _ScriptedLLM(_narr(GENERIC), _narr(GOOD))
    ok, runs, reports = _run(llm, recons=[dict(COVERAGE), dict(STALE)])

    assert ok is True
    assert llm.prompts == ["narrative_prompt.txt", "narrative_prompt_reinforced.txt"]
    corrections = llm.contexts[1]["narrative_corrections"]
    assert corrections == [
        "No reconciliation item in this report is a missing journal entry. "
        "Rewrite the sentence below so it does not say a journal entry is "
        "missing. Sentence: Some journal entries may be missing."
    ]
    assert reports.written[0].summary == GOOD


def test_generic_missing_je_twice_does_not_publish() -> None:
    llm = _ScriptedLLM(_narr(GENERIC), _narr(GENERIC))
    ok, runs, reports = _run(llm, recons=[dict(COVERAGE), dict(STALE)])

    assert ok is False
    assert reports.written == []
    assert runs.status == RunStatus.GUARDRAIL_FAILED.value
    assert runs.updates[-1][1]["error_message"] == (
        messages.NARRATIVE_CONTRADICTION_FAILED
    )


def test_claude_class_the_cards_will_not_show_does_not_back_the_wording() -> None:
    # Service Revenue has a roster count gap, so its card is forced to
    # stale_reference whatever Claude proposes.
    claimed = NarrativeJSON(
        narrative=GENERIC,
        numbers_used=[28400.00],
        reconciliation_classifications={"Service Revenue": "missing_je"},
    )
    llm = _ScriptedLLM(claimed, claimed)
    ok, _, reports = _run(llm, recons=[dict(COVERAGE), dict(STALE)])

    assert ok is False
    assert reports.written == []


def test_claude_missing_je_class_that_survives_the_merge_backs_the_wording() -> None:
    plain = {
        "account": "Office Supplies",
        "category": "OPEX",
        "gl_amount": 1200.0,
        "non_gl_total": 1450.0,
        "delta": 250.0,
        "hints": {},
    }
    claimed = NarrativeJSON(
        narrative=GENERIC,
        numbers_used=[28400.00],
        reconciliation_classifications={"Office Supplies": "missing_je"},
    )
    llm = _ScriptedLLM(claimed)
    ok, _, reports = _run(llm, recons=[dict(COVERAGE), plain])

    assert ok is True and len(llm.prompts) == 1
    assert reports.written


def test_two_contradictions_do_not_publish_and_do_not_verify() -> None:
    llm = _ScriptedLLM(_narr(BAD), _narr(BAD_PHRASE))
    ok, runs, reports = _run(llm)

    assert ok is False
    assert len(llm.prompts) == 2
    assert reports.written == []  # nothing published, nothing marked verified
    assert runs.status == RunStatus.GUARDRAIL_FAILED.value
    error = runs.updates[-1][1]["error_message"]
    assert error == messages.NARRATIVE_CONTRADICTION_FAILED
    assert "couldn't write this report" in error and "saved" in error
    assert "try again" in error


def test_number_mismatch_still_fails_after_two_attempts() -> None:
    wrong = _narr("Installation Revenue was 99999.00.", (99999.00,))
    llm = _ScriptedLLM(wrong, wrong)
    ok, runs, reports = _run(llm)

    assert ok is False
    assert len(llm.prompts) == 2
    assert reports.written == []
    assert runs.status == RunStatus.GUARDRAIL_FAILED.value
    assert (
        runs.updates[-1][1]["error_message"] != messages.NARRATIVE_CONTRADICTION_FAILED
    )


# --- Opus upgrade --------------------------------------------------------


def test_opus_upgrade_with_contradiction_keeps_the_existing_report(monkeypatch) -> None:
    from tests.agents.test_opus_upgrade import _wire_opus
    from backend.agents.opus_upgrade import run_opus_upgrade

    pandas_summary = {
        "accounts": {
            "Installation Revenue": {"category": "REVENUE", "current": 28400.0}
        }
    }
    runs, reports, llm, period = _wire_opus(
        monkeypatch,
        pandas_summary=pandas_summary,
        reconciliations=[dict(COVERAGE)],
        narrative=_narr(BAD),
    )
    run_opus_upgrade("run-1", "c-1", period)

    reports.upgrade_summary.assert_not_called()
    runs.set_opus_status.assert_called_with("run-1", "failed")


def test_opus_upgrade_with_coverage_wording_still_upgrades(monkeypatch) -> None:
    from tests.agents.test_opus_upgrade import _wire_opus
    from backend.agents.opus_upgrade import run_opus_upgrade

    pandas_summary = {
        "accounts": {
            "Installation Revenue": {"category": "REVENUE", "current": 28400.0}
        }
    }
    runs, reports, llm, period = _wire_opus(
        monkeypatch,
        pandas_summary=pandas_summary,
        reconciliations=[dict(COVERAGE)],
        narrative=_narr(GOOD),
    )
    run_opus_upgrade("run-1", "c-1", period)

    reports.upgrade_summary.assert_called_once()
    runs.set_opus_status.assert_called_with("run-1", "done")


def _opus_with_cards(monkeypatch, cards):
    from tests.agents.test_opus_upgrade import _wire_opus
    from backend.agents.opus_upgrade import run_opus_upgrade

    pandas_summary = {
        "accounts": {
            "Installation Revenue": {"category": "REVENUE", "current": 28400.0}
        }
    }
    runs, reports, _, period = _wire_opus(
        monkeypatch,
        pandas_summary=pandas_summary,
        reconciliations=cards,
        narrative=_narr(GENERIC),
    )
    run_opus_upgrade("run-1", "c-1", period)
    return runs, reports


def test_opus_generic_missing_je_without_a_card_keeps_the_report(monkeypatch) -> None:
    runs, reports = _opus_with_cards(
        monkeypatch, [dict(COVERAGE), {**STALE, "classification": "stale_reference"}]
    )
    reports.upgrade_summary.assert_not_called()
    runs.set_opus_status.assert_called_with("run-1", "failed")


def test_opus_generic_missing_je_with_a_saved_card_upgrades(monkeypatch) -> None:
    runs, reports = _opus_with_cards(
        monkeypatch,
        [dict(COVERAGE), {**SOURCE_ONLY, "classification": "missing_je"}],
    )
    reports.upgrade_summary.assert_called_once()
    runs.set_opus_status.assert_called_with("run-1", "done")
