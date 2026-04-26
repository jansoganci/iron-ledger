from __future__ import annotations

import uuid
from datetime import date

from backend import messages
from backend.domain.contracts import NarrativeJSON, PandasSummary
from backend.domain.entities import Anomaly, Report
from backend.domain.errors import GuardrailError
from backend.domain.ports import FileStorage, LLMClient, ReportsRepo, RunsRepo
from backend.domain.run_state_machine import RunStateMachine, RunStatus
from backend.logger import get_logger, get_trace_id
from backend.tools.guardrail import verify_guardrail

logger = get_logger(__name__)

NARRATIVE_MODEL = "claude-opus-4-7"  # no user toggle in MVP


def _guardrail_user_message(exc_str: str) -> str:
    """Translate a GuardrailError message into plain-English user guidance.

    Extracts the mismatched number and explains the most common cause so the
    user knows what to check rather than seeing a raw technical error.
    """
    import re

    match = re.search(r"Mismatch:\s*([-\d,.]+)", exc_str)
    if match:
        raw = match.group(1)
        try:
            val = float(raw.replace(",", ""))
            abs_val = abs(val)
            formatted = f"${abs_val:,.2f}"
            sign_note = (
                " with a negative sign" if val < 0 else ""
            )
            neg_revenue_hint = (
                "Negative values in income or revenue accounts are the most common cause — "
                "check that revenue amounts in your GL file are entered as positive numbers. "
            ) if val < 0 else ""
            return (
                f"The AI report mentioned {formatted}{sign_note}, but that exact figure "
                f"could not be matched to your financial data. "
                f"{neg_revenue_hint}"
                f"You can download the unverified raw data below, fix the source file, "
                f"and re-upload to generate a verified report."
            )
        except ValueError:
            pass
    return (
        "The AI report contained a figure that could not be verified against your "
        "financial data after two attempts. Download the raw data below, review your "
        "source files for unexpected negative values or formatting issues, and re-upload."
    )


def _classify_from_hints(hints: dict) -> str:
    """Rule-based fallback when Claude doesn't return a classification.

    Priority order:
    1. GL-only or source-only → always missing_je (one side has no entry).
    2. Cross-period date → timing_cutoff.
    3. Both sources present, similar amount in another account → categorical_misclassification.
    4. Both sources present, accrual pattern → accrual_mismatch.
    5. Both sources present, general delta → stale_reference.
    """
    if hints.get("is_gl_only") or hints.get("is_source_only"):
        return "missing_je"
    if hints.get("crosses_period_boundary"):
        return "timing_cutoff"
    if hints.get("similar_amount_in_other_account"):
        return "categorical_misclassification"
    if hints.get("is_round_fraction"):
        return "accrual_mismatch"
    return "stale_reference"


class InterpreterAgent:
    def __init__(
        self,
        llm_client: LLMClient,
        reports_repo: ReportsRepo,
        runs_repo: RunsRepo,
        file_storage: FileStorage,
    ) -> None:
        self._llm = llm_client
        self._reports = reports_repo
        self._runs = runs_repo
        self._storage = file_storage

    def run(
        self,
        pandas_summary: PandasSummary,
        anomalies: list[Anomaly],
        run_id: str,
        reconciliations: list[dict] | None = None,
    ) -> bool:
        """Run interpretation pipeline. Returns True on complete, False on guardrail_failed.

        Never raises — all failure paths are handled by transitioning run state.
        """
        # comparing → generating
        run = self._runs.get_by_id(run_id)
        try:
            gen_status = RunStateMachine.transition(run["status"], RunStatus.GENERATING)
        except Exception as exc:
            logger.error(
                "interpreter invalid state transition",
                extra={
                    "run_id": run_id,
                    "current": run.get("status"),
                    "error": str(exc),
                },
            )
            return False

        self._runs.update_status(
            run_id,
            gen_status,
            extra={"step": 4, "step_label": "Generating report...", "progress_pct": 95},
        )
        self._update_generating_progress(
            run_id,
            progress_pct=96,
            step_label="Drafting narrative...",
        )

        try:
            narrative: NarrativeJSON = self._run_with_guardrail(
                pandas_summary, anomalies, run_id, reconciliations=reconciliations
            )
        except GuardrailError as exc:
            logger.warning(
                "guardrail_failed",
                extra={"run_id": run_id, "error": str(exc), "trace_id": get_trace_id()},
            )
            try:
                fail_status = RunStateMachine.transition(
                    RunStatus.GENERATING, RunStatus.GUARDRAIL_FAILED
                )
                self._runs.update_status(
                    run_id,
                    fail_status,
                    extra={
                        "error_message": _guardrail_user_message(str(exc)),
                        "raw_data_url": f"/runs/{run_id}/raw",
                    },
                )
            except Exception as inner:
                logger.error(
                    "failed to set guardrail_failed status",
                    extra={"run_id": run_id, "inner_error": str(inner)},
                )
            return False
        except Exception as exc:
            logger.error(
                "interpreter unexpected error",
                extra={"run_id": run_id, "error": str(exc), "trace_id": get_trace_id()},
                exc_info=True,
            )
            try:
                fail_status = RunStateMachine.transition(
                    RunStatus.GENERATING, RunStatus.GUARDRAIL_FAILED
                )
                self._runs.update_status(
                    run_id,
                    fail_status,
                    extra={"error_message": messages.INTERNAL_ERROR},
                )
            except Exception:
                pass
            return False

        # Update: narrative generated, finalizing report
        self._update_generating_progress(
            run_id,
            progress_pct=98,
            step_label="Finalizing report...",
        )

        # Merge per-item classifications from Claude back into reconciliation items.
        # Claude's output is used first; hint-based rules fill any gaps.
        if reconciliations:
            cls_map = narrative.reconciliation_classifications or {}
            for item in reconciliations:
                account = item.get("account", "")
                if account in cls_map:
                    item["classification"] = cls_map[account]
                elif not item.get("classification"):
                    item["classification"] = _classify_from_hints(item.get("hints", {}))

        # Write reports row
        report = self._reports.write(
            Report(
                id=str(uuid.uuid4()),
                company_id=str(pandas_summary.company_id),
                period=pandas_summary.period,
                summary=narrative.narrative,
                anomaly_count=len(
                    [a for a in anomalies if a.severity in ("high", "medium")]
                ),
                error_count=0,
                reconciliations=reconciliations,
            )
        )

        # generating → complete
        try:
            complete_status = RunStateMachine.transition(
                RunStatus.GENERATING, RunStatus.COMPLETE
            )
            self._runs.update_status(
                run_id,
                complete_status,
                extra={"progress_pct": 100, "report_id": report.id},
            )
        except Exception as exc:
            logger.error(
                "failed to transition to complete",
                extra={"run_id": run_id, "error": str(exc)},
            )

        logger.info(
            "interpreter complete",
            extra={
                "run_id": run_id,
                "report_id": report.id,
                "anomaly_count": report.anomaly_count,
                "trace_id": get_trace_id(),
            },
        )
        return True

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _run_with_guardrail(
        self,
        pandas_summary: PandasSummary,
        anomalies: list[Anomaly],
        run_id: str,
        max_retries: int = 2,
        reconciliations: list[dict] | None = None,
    ) -> NarrativeJSON:
        """Semantic retry loop — attempt 1 with base prompt, attempt 2 with reinforced prompt.

        Semantic retry is a content-quality concern, not an I/O concern.
        I/O retries (network/5xx) stay in anthropic_llm.py.
        """
        summary_dict = pandas_summary.model_dump(mode="json")
        anomaly_list = [
            {
                "account_id": a.account_id,
                "severity": a.severity,
                "description": a.description,
                "variance_pct": (
                    float(a.variance_pct) if a.variance_pct is not None else None
                ),
            }
            for a in anomalies
        ]
        context = {
            "pandas_summary": summary_dict,
            "anomalies": anomaly_list,
            "reconciliations": reconciliations or [],
        }

        # Build supplemental valid values from reconciliation source amounts.
        # Claude may mention individual source-level figures (e.g. "GL shows $5,420")
        # which differ from the consolidated pandas_summary total ($10,920 = GL + dept).
        # Passing these as extra reference values prevents false guardrail failures in
        # multi-file runs without weakening the check for single-file variance analysis.
        recon_values: list[float] = []
        for item in (reconciliations or []):
            for field in ("gl_amount", "non_gl_total", "delta"):
                v = item.get(field)
                if v is not None:
                    recon_values.append(float(v))
                    recon_values.append(float(abs(v)))
            for src in item.get("sources", []):
                recon_values.append(float(src.get("amount", 0)))

        last_message = ""
        for attempt in range(max_retries):
            # Keep users informed during longer LLM/guardrail work.
            if attempt > 0:
                self._update_generating_progress(
                    run_id,
                    progress_pct=97,
                    step_label=f"Re-checking narrative ({attempt + 1}/{max_retries})...",
                )
            prompt_file = (
                "narrative_prompt.txt"
                if attempt == 0
                else "narrative_prompt_reinforced.txt"
            )
            result: NarrativeJSON = self._llm.call(
                prompt=prompt_file,
                model=NARRATIVE_MODEL,
                context=context,
                schema=NarrativeJSON,
            )
            success, message = verify_guardrail(
                result.model_dump(), summary_dict, reconciliation_values=recon_values
            )
            logger.info(
                "guardrail_attempt",
                extra={
                    "event": "guardrail_attempt",
                    "run_id": run_id,
                    "attempt": attempt + 1,
                    "success": success,
                    "mismatch_detail": message if not success else None,
                    "trace_id": get_trace_id(),
                },
            )
            if success:
                return result
            last_message = message

        raise GuardrailError(
            f"Report could not be verified after {max_retries} attempts. "
            f"Last mismatch: {last_message}"
        )

    def _update_generating_progress(
        self,
        run_id: str,
        progress_pct: int,
        step_label: str,
    ) -> None:
        """Best-effort progress updates during GENERATING without changing state."""
        try:
            self._runs.update_status(
                run_id,
                RunStatus.GENERATING,
                extra={"step": 4, "step_label": step_label, "progress_pct": progress_pct},
            )
        except Exception as exc:
            logger.warning(
                "interpreter progress update failed",
                extra={"run_id": run_id, "progress_pct": progress_pct, "error": str(exc)},
            )
