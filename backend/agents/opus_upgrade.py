from __future__ import annotations

from datetime import date

from backend.api.deps import get_llm_client, get_reports_repo, get_runs_repo
from backend.domain.contracts import NarrativeJSON
from backend.logger import get_logger, get_trace_id
from backend.tools.guardrail import verify_guardrail

logger = get_logger(__name__)

_OPUS_MODEL = "claude-opus-4-7"
_PROMPT_FILE = "opus_narrative_prompt.txt"


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

        context = {
            "period": str(period),
            "current_summary": current_pandas,
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

        # Guardrail: verify numbers against current pandas_summary only.
        recon_values: list[float] = []
        for item in reconciliations:
            if isinstance(item, dict):
                for key in ("delta", "gl_amount", "non_gl_total"):
                    v = item.get(key)
                    if isinstance(v, (int, float)):
                        recon_values.append(float(v))

        passed, reason = verify_guardrail(
            claude_json=result.model_dump(),
            pandas_summary=current_pandas,
            reconciliation_values=recon_values if recon_values else None,
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
