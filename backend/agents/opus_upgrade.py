from __future__ import annotations

from datetime import date

from backend.api.deps import get_llm_client, get_reports_repo, get_runs_repo
from backend.domain.contracts import NarrativeJSON
from backend.logger import get_logger, get_trace_id
from backend.tools.guardrail import (
    collect_reconciliation_reference_values,
    verify_guardrail,
)

logger = get_logger(__name__)

_OPUS_MODEL = "claude-opus-4-7"
_PROMPT_FILE = "opus_narrative_prompt.txt"

_REVENUE_CATS = frozenset({"REVENUE", "OTHER_INCOME"})
_COGS_CATS = frozenset({"COGS"})
_OPEX_CATS = frozenset({"OPEX", "G&A", "R&D"})


def _pnl_totals_from_summary(pandas_summary: dict) -> dict[str, float]:
    """Python-only P&L rollup so Opus copies net_income instead of deriving it."""
    revenue = 0.0
    cogs = 0.0
    opex = 0.0
    accounts = pandas_summary.get("accounts") or {}
    if isinstance(accounts, dict):
        for account_data in accounts.values():
            if not isinstance(account_data, dict):
                continue
            category = account_data.get("category", "OTHER")
            current = float(account_data.get("current") or 0.0)
            if category in _REVENUE_CATS:
                revenue += current
            elif category in _COGS_CATS:
                cogs += current
            elif category in _OPEX_CATS:
                opex += current
    gross_profit = revenue - cogs
    net_income = gross_profit - opex
    net_margin_pct = (net_income / revenue * 100) if revenue else 0.0
    return {
        "net_income": round(net_income, 2),
        "gross_profit_total": round(gross_profit, 2),
        "net_margin_pct": round(net_margin_pct, 2),
    }


def run_opus_upgrade(run_id: str, company_id: str, period: date) -> None:
    """Background task. Runs Opus with prior 3 months' data, upgrades report.

    Never raises — silent fail on any error. The Haiku report stays intact
    if anything goes wrong.
    """
    try:
        runs_repo = get_runs_repo()
        reports_repo = get_reports_repo()
        llm_client = get_llm_client()

        # Mark running so the frontend banner appears.
        runs_repo.set_opus_status(run_id, "running")

        # Race condition guard: abort if a newer upload exists for this period.
        latest_id = runs_repo.get_latest_run_id_for_period(company_id, period)
        if latest_id != run_id:
            logger.info(
                "opus_upgrade aborted: newer run exists",
                extra={
                    "run_id": run_id,
                    "latest_id": latest_id,
                    "trace_id": get_trace_id(),
                },
            )
            runs_repo.set_opus_status(run_id, "failed")
            return

        # Fetch current month's pandas_summary.
        current_run = runs_repo.get_by_id(run_id)
        current_pandas = current_run.get("pandas_summary")
        if not current_pandas:
            logger.warning(
                "opus_upgrade: no pandas_summary on run",
                extra={"run_id": run_id, "trace_id": get_trace_id()},
            )
            runs_repo.set_opus_status(run_id, "failed")
            return

        # Fetch current report (for reconciliations context).
        current_report = reports_repo.get(company_id, period)
        if not current_report:
            logger.warning(
                "opus_upgrade: no report found",
                extra={"run_id": run_id, "trace_id": get_trace_id()},
            )
            runs_repo.set_opus_status(run_id, "failed")
            return

        reconciliations = current_report.reconciliations or []

        # Fetch up to 3 prior months' summaries for trend context.
        prior_rows = runs_repo.get_prior_pandas_summaries(
            company_id=company_id,
            before_period=period,
            limit=3,
        )
        prior_summaries = [
            {
                "period": str(r["period"]),
                "accounts": r["pandas_summary"].get("accounts", {}),
            }
            for r in prior_rows
            if r.get("pandas_summary")
        ]

        pnl = _pnl_totals_from_summary(current_pandas)
        current_summary = dict(current_pandas)
        current_summary.update(pnl)

        context = {
            "period": str(period),
            "current_summary": current_summary,
            "prior_summaries": prior_summaries,
            "reconciliations": reconciliations,
        }

        logger.info(
            "opus_upgrade calling LLM",
            extra={
                "run_id": run_id,
                "prior_months": len(prior_summaries),
                "reconciliation_items": len(reconciliations),
                "trace_id": get_trace_id(),
            },
        )

        result = llm_client.call(
            prompt=_PROMPT_FILE,
            model=_OPUS_MODEL,
            context=context,
            schema=NarrativeJSON,
        )

        recon_values = collect_reconciliation_reference_values(reconciliations)

        passed, reason = verify_guardrail(
            claude_json=result.model_dump(),
            pandas_summary=current_summary,
            reconciliation_values=recon_values if recon_values else None,
            strict=True,
            run_id=run_id,
        )

        if not passed:
            logger.warning(
                "opus_upgrade guardrail failed",
                extra={"run_id": run_id, "reason": reason, "trace_id": get_trace_id()},
            )
            runs_repo.set_opus_status(run_id, "failed")
            return

        # Guardrail passed — atomically overwrite the report.
        reports_repo.upgrade_summary(
            company_id=company_id,
            period=period,
            new_summary=result.narrative,
        )
        runs_repo.set_opus_status(run_id, "done")

        logger.info(
            "opus_upgrade complete",
            extra={"run_id": run_id, "trace_id": get_trace_id()},
        )

    except Exception as exc:
        logger.error(
            "opus_upgrade unhandled exception",
            extra={"run_id": run_id, "error": str(exc), "trace_id": get_trace_id()},
            exc_info=True,
        )
        try:
            get_runs_repo().set_opus_status(run_id, "failed")
        except Exception:
            pass
