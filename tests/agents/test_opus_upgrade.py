"""Opus upgrade — copy-only net income and strict guardrail."""

from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock

from backend.agents.opus_upgrade import _pnl_totals_from_summary, run_opus_upgrade
from backend.domain.contracts import NarrativeJSON
from backend.domain.entities import Report


def test_opus_prompt_does_not_ask_to_derive_net() -> None:
    from pathlib import Path

    text = Path("backend/prompts/opus_narrative_prompt.txt").read_text()
    assert "if derivable" not in text
    assert "net_income" in text
    assert "Do not derive net income" in text
    assert "Do not subtract" in text


def test_pnl_totals_from_summary_are_python_only() -> None:
    totals = _pnl_totals_from_summary(
        {
            "accounts": {
                "Service": {"category": "REVENUE", "current": 1_000.0},
                "Other": {"category": "OTHER_INCOME", "current": 100.0},
                "Materials": {"category": "COGS", "current": 400.0},
                "Ops": {"category": "OPEX", "current": 200.0},
                "Office": {"category": "G&A", "current": 50.0},
                "Labs": {"category": "R&D", "current": 25.0},
                "Noise": {"category": "OTHER", "current": 9_999.0},
            }
        }
    )
    assert totals["gross_profit_total"] == 700.0
    assert totals["net_income"] == 425.0
    assert totals["net_margin_pct"] == 38.64


def test_pnl_totals_zero_revenue_sets_margin_zero() -> None:
    totals = _pnl_totals_from_summary(
        {"accounts": {"Rent": {"category": "OPEX", "current": 50.0}}}
    )
    assert totals["net_income"] == -50.0
    assert totals["net_margin_pct"] == 0.0


def _wire_opus(monkeypatch, *, pandas_summary, reconciliations, narrative):
    from backend.agents import opus_upgrade as mod

    runs = MagicMock()
    reports = MagicMock()
    llm = MagicMock()
    monkeypatch.setattr(mod, "get_runs_repo", lambda: runs)
    monkeypatch.setattr(mod, "get_reports_repo", lambda: reports)
    monkeypatch.setattr(mod, "get_llm_client", lambda: llm)

    period = date(2026, 3, 1)
    runs.get_latest_run_id_for_period.return_value = "run-1"
    runs.get_by_id.return_value = {"pandas_summary": pandas_summary}
    runs.get_prior_pandas_summaries.return_value = []
    reports.get.return_value = Report(
        id="r-1",
        company_id="c-1",
        period=period,
        summary="base narrative",
        reconciliations=reconciliations,
    )
    llm.call.return_value = narrative
    return runs, reports, llm, period


def test_opus_upgrade_copies_net_income_and_passes_strict(monkeypatch) -> None:
    pandas_summary = {
        "accounts": {
            "Revenue": {"category": "REVENUE", "current": 300_000.0},
            "COGS": {"category": "COGS", "current": 100_000.0},
            "OpEx": {"category": "OPEX", "current": 50_000.0},
        }
    }
    narrative = NarrativeJSON(
        narrative="Net income was $150,000.00 this month.",
        numbers_used=[150_000.0],
        reconciliation_classifications={},
    )
    runs, reports, llm, period = _wire_opus(
        monkeypatch,
        pandas_summary=pandas_summary,
        reconciliations=[],
        narrative=narrative,
    )

    run_opus_upgrade("run-1", "c-1", period)

    context = llm.call.call_args.kwargs["context"]
    assert context["current_summary"]["net_income"] == 150_000.0
    assert context["current_summary"]["gross_profit_total"] == 200_000.0
    assert context["current_summary"]["net_margin_pct"] == 50.0
    reports.upgrade_summary.assert_called_once()
    runs.set_opus_status.assert_called_with("run-1", "done")


def test_opus_upgrade_invented_dollar_fails_closed(monkeypatch) -> None:
    pandas_summary = {
        "accounts": {
            "Revenue": {"category": "REVENUE", "current": 300_000.0},
            "COGS": {"category": "COGS", "current": 100_000.0},
        }
    }
    recon = [
        {
            "account": "Revenue",
            "gl_amount": 300_000.0,
            "non_gl_total": 300_000.0,
            "delta": 0.0,
            "hints": {"n_active": 85, "implied_monthly": 1_200.0},
            "matches": [
                {
                    "gross": 1_000.0,
                    "fee": 45.0,
                    "net": 955.0,
                    "gl_amount": 1_000.0,
                    "candidate_count": 1,
                }
            ],
            "sources": [{"amount": 300_000.0}],
        }
    ]
    narrative = NarrativeJSON(
        narrative="We found $999 missing.",
        numbers_used=[999.0],
        reconciliation_classifications={},
    )
    runs, reports, llm, period = _wire_opus(
        monkeypatch,
        pandas_summary=pandas_summary,
        reconciliations=recon,
        narrative=narrative,
    )

    from backend.agents import opus_upgrade as mod

    spy_calls: list[dict] = []
    real = mod.verify_guardrail

    def _spy(*args, **kwargs):
        spy_calls.append(kwargs)
        return real(*args, **kwargs)

    monkeypatch.setattr(mod, "verify_guardrail", _spy)

    run_opus_upgrade("run-1", "c-1", period)

    assert spy_calls and spy_calls[0]["strict"] is True
    assert 85.0 in spy_calls[0]["reconciliation_values"]
    assert 1_200.0 in spy_calls[0]["reconciliation_values"]
    assert 45.0 in spy_calls[0]["reconciliation_values"]
    runs.set_opus_status.assert_called_with("run-1", "failed")
    reports.upgrade_summary.assert_not_called()
    assert llm.call.call_args.kwargs["context"]["current_summary"]["net_income"] == (
        200_000.0
    )
