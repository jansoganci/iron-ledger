from __future__ import annotations

import uuid
from datetime import date

from backend import messages
from backend.domain.contracts import NarrativeJSON, PandasSummary
from backend.domain.entities import Anomaly, Report
from backend.domain.errors import DuplicateEntryError, GuardrailError
from backend.domain.ports import FileStorage, LLMClient, ReportsRepo, RunsRepo
from backend.domain.run_state_machine import RunStateMachine, RunStatus
from backend.logger import get_logger, get_trace_id
from backend.tools.guardrail import verify_guardrail

logger = get_logger(__name__)

# Item 1 (E.6): account-level residue order — most action-requiring first.
# Mirrors batch_matcher._RESIDUE_PRIORITY; kept here so the interpreter does
# not import the matcher just to read a constant.
_RESIDUE_PRIORITY: tuple[str, ...] = (
    "missing_je",
    "categorical_misclassification",
    "stale_reference",
    "timing_cutoff",
    "structural_explained",
)

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
            sign_note = " with a negative sign" if val < 0 else ""
            neg_revenue_hint = (
                (
                    "Negative values in income or revenue accounts are the most common cause — "
                    "check that revenue amounts in your GL file are entered as positive numbers. "
                )
                if val < 0
                else ""
            )
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


def _hints_as_dict(hints) -> dict:
    if not hints:
        return {}
    if isinstance(hints, dict):
        return hints
    if hasattr(hints, "model_dump"):
        return hints.model_dump()
    return {}


def _classify_from_hints(hints: dict) -> str | None:
    """Rule-based fallback when Claude doesn't return a classification.

    Priority order:
    1. GL-only → no exception class (coverage card; not missing_je).
    2. Source-only → missing_je.
    3. Processor/platform netting → structural_explained.
    4. Customer deposit / 50% peşinat → timing_cutoff (not accrual_mismatch).
    5. Same-item ~12× annual prepayment → accrual_mismatch.
       Rationale vs 3–4: fee band (3–8%) and 50% deposit cannot be 12×;
       column-triggered deposit still wins because that speech act is
       unearned/liability, not “create a prepaid asset.”
    6. Cross-period date → timing_cutoff.
    7. Both sources present, similar amount in another account → categorical_misclassification.
    8. Both sources present, general delta → stale_reference.
    """
    if hints.get("is_gl_only"):
        return None
    if hints.get("is_source_only"):
        return "missing_je"
    if hints.get("is_processor_fee_gap"):
        return "structural_explained"
    if hints.get("is_customer_deposit") or hints.get("is_round_fraction"):
        return "timing_cutoff"
    if _is_annual_prepayment_hint(hints):
        return "accrual_mismatch"
    if hints.get("crosses_period_boundary"):
        return "timing_cutoff"
    if hints.get("similar_amount_in_other_account"):
        return "categorical_misclassification"
    return "stale_reference"


def _is_annual_prepayment_hint(hints: dict) -> bool:
    return bool(
        hints.get("looks_like_annual_prepayment")
        or hints.get("delta_matches_known_vendor")
    )


def _has_roster_count_gap(hints: dict) -> bool:
    """Item 4: active accounts that were not billed this period (R.6)."""
    delta = hints.get("count_delta")
    return delta is not None and delta > 0


def _is_coverage_item(item: dict) -> bool:
    if item.get("card_kind") == "coverage":
        return True
    hints = _hints_as_dict(item.get("hints"))
    return bool(hints.get("is_gl_only"))


def _residue_from_matches(matches: object) -> str | None:
    """Account-level class for an item carrying three-way `matches` (E.6).

    Nesting decision: per-batch classes live on each match; the item's own
    class is the most action-requiring one among them, so a card can never read
    "No action required" while a batch under it needs a JE or a reclass.
    Returns None when the item has no matches, leaving today's behaviour.
    """
    if not matches or not isinstance(matches, list):
        return None
    classes = set()
    for match in matches:
        if isinstance(match, dict):
            value = match.get("classification")
        else:
            value = getattr(match, "classification", None)
        if value is not None:
            classes.add(value)
    for candidate in _RESIDUE_PRIORITY:
        if candidate in classes:
            return candidate
    return None


def _apply_reconciliation_classifications(
    reconciliations: list[dict],
    cls_map: dict[str, str],
) -> None:
    """Merge Claude classes; pandas hints win for coverage / deposit / fee / annual."""
    for item in reconciliations:
        if _is_coverage_item(item):
            item["card_kind"] = "coverage"
            item["classification"] = None
            continue
        hints = _hints_as_dict(item.get("hints"))
        # Three-way matcher result outranks every account-total hint (C.7):
        # when real batches were matched we must not also tell the account-level
        # fee story — that would be double speech on one card. The class is the
        # pandas residue over the item's matches, never Claude's choice.
        residue = _residue_from_matches(item.get("matches"))
        if residue is not None:
            item["classification"] = residue
            continue
        # Pandas-backed speech acts are not Claude's to override.
        # Fee > deposit > annual: never two stories on one card.
        if hints.get("is_processor_fee_gap"):
            item["classification"] = "structural_explained"
            continue
        if hints.get("is_customer_deposit") or hints.get("is_round_fraction"):
            item["classification"] = "timing_cutoff"
            continue
        if _is_annual_prepayment_hint(hints):
            item["classification"] = "accrual_mismatch"
            continue
        # Item 4 (R.6): a stale roster is a statement about the reference list,
        # so it sits below fee/deposit/annual (statements about the money) and
        # above Claude's own map. count_delta == 0 attaches counts but forces
        # nothing — there is no "0 accounts" story.
        if _has_roster_count_gap(hints):
            item["classification"] = "stale_reference"
            continue
        account = item.get("account", "")
        if account in cls_map:
            proposed = cls_map[account]
            if proposed == "structural_explained":
                item["classification"] = _classify_from_hints(hints)
            else:
                item["classification"] = proposed
        elif not item.get("classification"):
            item["classification"] = _classify_from_hints(hints)


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
            _apply_reconciliation_classifications(reconciliations, cls_map)

        # Write reports row. The numbers are already verified by this point, so
        # a failure here is persistence, not correctness — it gets its own
        # terminal state rather than being reported as a guardrail failure.
        # Unhandled, this used to strand the run in GENERATING forever.
        try:
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
        except Exception as exc:
            # A duplicate is a different story from a database failure. The
            # period already has a verified report, and this run must not
            # decide on its own to replace it — say so plainly instead.
            duplicate = isinstance(exc, DuplicateEntryError)
            logger.error(
                "report_write_failed",
                extra={
                    "run_id": run_id,
                    "reason": "duplicate" if duplicate else "write_error",
                    "error": str(exc),
                    "trace_id": get_trace_id(),
                },
                exc_info=True,
            )
            try:
                fail_status = RunStateMachine.transition(
                    RunStatus.GENERATING, RunStatus.REPORT_FAILED
                )
                self._runs.update_status(
                    run_id,
                    fail_status,
                    extra={
                        "error_message": (
                            messages.REPORT_ALREADY_EXISTS
                            if duplicate
                            else messages.REPORT_WRITE_FAILED
                        )
                    },
                )
            except Exception as inner:
                logger.error(
                    "failed to set report_failed status",
                    extra={"run_id": run_id, "inner_error": str(inner)},
                )
            return False

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
        for item in reconciliations or []:
            for field in ("gl_amount", "non_gl_total", "delta"):
                v = item.get(field)
                if v is not None:
                    recon_values.append(float(v))
                    recon_values.append(float(abs(v)))
            # implied_monthly lives on the nested hints object
            # (ReconciliationHints), NOT on the item itself — reading
            # item.get("implied_monthly") would be a silent no-op. Pandas
            # derived: max(|GL|, |source|) / 12, set only when
            # looks_like_annual_prepayment is true.
            hints = item.get("hints") or {}
            if isinstance(hints, dict):
                implied_monthly = hints.get("implied_monthly")
                if implied_monthly is not None:
                    recon_values.append(float(implied_monthly))
                    recon_values.append(float(abs(implied_monthly)))
            # Item 1: every pandas number Claude is allowed to copy from a
            # nested BatchMatch must be a verified reference, or a correct
            # narrative fails the guardrail. fee_pct is deliberately ABSENT —
            # it is an internal gate (E.1), it is a percentage rather than
            # money, and putting it in this money pool is exactly the
            # mixed-unit bug the guardrail fix removed.
            for match in item.get("matches") or []:
                if not isinstance(match, dict):
                    match = getattr(match, "model_dump", dict)()
                for money_field in ("gross", "fee", "net", "gl_amount"):
                    v = match.get(money_field)
                    if v is not None:
                        recon_values.append(float(v))
                        recon_values.append(float(abs(v)))
                # A count, not money. Claude may copy it ("2 candidates"), so it
                # must be a reference; at cent tolerance it is a point value and
                # cannot widen anything.
                candidate_count = match.get("candidate_count")
                if candidate_count is not None:
                    recon_values.append(float(candidate_count))
            # Item 4: roster counts are point values (R.8) — integers and
            # money sums, never a ratio. No churn %, no "3 of 85" percentage
            # may ever enter this pool.
            if isinstance(hints, dict):
                for roster_field in (
                    "n_active",
                    "n_billed_in_period",
                    "count_delta",
                    "fee_sum_active",
                    "fee_sum_billed",
                ):
                    v = hints.get(roster_field)
                    if v is not None:
                        recon_values.append(float(v))
                        recon_values.append(float(abs(v)))
            for count_field in (
                "unmatched_count",
                "unmatched_processor_count",
                "unmatched_bank_count",
            ):
                v = item.get(count_field)
                if v is not None:
                    recon_values.append(float(v))
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
                result.model_dump(),
                summary_dict,
                reconciliation_values=recon_values,
                strict=True,
                run_id=run_id,
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
                extra={
                    "step": 4,
                    "step_label": step_label,
                    "progress_pct": progress_pct,
                },
            )
        except Exception as exc:
            logger.warning(
                "interpreter progress update failed",
                extra={
                    "run_id": run_id,
                    "progress_pct": progress_pct,
                    "error": str(exc),
                },
            )
