from __future__ import annotations

from datetime import date

from backend import messages
from backend.agents.comparison import ComparisonAgent
from backend.agents.consolidator import consolidate
from backend.agents.interpreter import InterpreterAgent
from backend.agents.parser import ParserAgent
from backend.api.deps import (
    get_accounts_repo,
    get_anomalies_repo,
    get_entries_repo,
    get_file_storage,
    get_llm_client,
    get_reports_repo,
    get_runs_repo,
)
from backend.domain.contracts import DiscoveryPlan
from backend.domain.errors import DiscoveryLowConfidence
from backend.domain.run_state_machine import RunStateMachine, RunStatus
from backend.logger import get_logger, get_trace_id

logger = get_logger(__name__)

# Terminal states — orchestrators must not try to transition out of these.
# Inner handlers (ParserAgent._fail, interpreter's guardrail_failed path)
# already performed the transition; the outer catch-all would otherwise
# collide with "Cannot transition X → X" InvalidRunTransition errors.
_TERMINAL_STATUSES = frozenset(
    {
        RunStatus.COMPLETE.value,
        RunStatus.UPLOAD_FAILED.value,
        RunStatus.PARSING_FAILED.value,
        RunStatus.GUARDRAIL_FAILED.value,
    }
)


def _fail_if_not_terminal(run_id: str, error_message: str) -> None:
    """Best-effort transition to PARSING_FAILED. No-op if already terminal.

    Called by the outer `except Exception` handler in each orchestrator
    function as a last-resort safety net when an inner handler didn't
    (or couldn't) already transition the run to a terminal state.
    """
    try:
        runs_repo = get_runs_repo()
        run = runs_repo.get_by_id(run_id)
        current = run.get("status")
        if current in _TERMINAL_STATUSES:
            # Inner handler already did its job — nothing to do here.
            return
        failed_status = RunStateMachine.transition(current, RunStatus.PARSING_FAILED)
        runs_repo.update_status(
            run_id,
            failed_status,
            extra={"error_message": error_message},
        )
    except Exception as inner:
        logger.error(
            "outer handler failed to transition to parsing_failed",
            extra={"run_id": run_id, "inner_error": str(inner)},
        )


def run_multi_file_parser_until_preview(
    run_id: str,
    storage_keys: list[str],
    company_id: str,
    period: date,
) -> None:
    """Parse N files silently, consolidate, store combined preview, await confirmation.

    Each file is parsed (download → discover → normalize → map) without writing
    to monthly_entries. Results are consolidated by ConsolidatorAgent into one
    combined parse_preview that the confirm route will write to the DB.

    parse_preview shape for multi-file runs:
      {
        "rows": [{account, amount, category}],          # consolidated totals
        "source_column": "Consolidated",
        "drops": {},
        "source_breakdown_by_account": {account: [{source_file, amount, row_count}]},
        "reconciliations": [{account, delta, severity, ...}],   # ReconciliationItem dicts
        "is_multi_file": true
      }
    """
    try:
        parser = ParserAgent(
            file_storage=get_file_storage(),
            llm_client=get_llm_client(),
            accounts_repo=get_accounts_repo(),
            runs_repo=get_runs_repo(),
        )

        runs_repo = get_runs_repo()

        runs_repo.update_status(
            run_id,
            RunStatus.PARSING,
            extra={
                "step": 1,
                "step_label": f"Reading {len(storage_keys)} files...",
                "progress_pct": 10,
            },
        )

        # Parse each file silently — no state transitions per file.
        # Collect (label, preview_rows, source_column, raw_df) per file.
        # raw_df retains per-row date columns for hint computation.
        import pandas as pd

        per_file_data: list[tuple[str, list[dict], str, pd.DataFrame]] = []
        for i, key in enumerate(storage_keys):
            label = key.split("/")[-1]  # use filename as source label
            try:
                preview_rows, source_column, raw_df = parser.parse_file_silently(
                    storage_key=key,
                    company_id=company_id,
                    period=period,
                    run_id=run_id,
                )
                per_file_data.append((label, preview_rows, source_column, raw_df))
                logger.info(
                    "multi_file_parsed",
                    extra={
                        "run_id": run_id,
                        "file": label,
                        "accounts": len(preview_rows),
                        "index": i + 1,
                        "total": len(storage_keys),
                        "trace_id": get_trace_id(),
                    },
                )
            except Exception as exc:
                logger.error(
                    "multi_file_parse_error",
                    extra={
                        "run_id": run_id,
                        "file": label,
                        "error": str(exc),
                        "trace_id": get_trace_id(),
                    },
                )
                _fail_if_not_terminal(run_id, messages.PARSE_FAILED)
                return

        runs_repo.update_status(
            run_id,
            RunStatus.PARSING,
            extra={
                "step": 2,
                "step_label": "Consolidating files...",
                "progress_pct": 50,
            },
        )

        # Build aggregated DataFrames for ConsolidatorAgent.
        # Also keep raw DataFrames keyed by filename for hint_computer.
        source_dfs: list[tuple[str, pd.DataFrame]] = []
        source_raw_dfs: dict[str, pd.DataFrame] = {}
        for label, preview_rows, _, raw_df in per_file_data:
            source_dfs.append((label, pd.DataFrame(preview_rows)))
            source_raw_dfs[label] = raw_df

        consolidated_df, recon_items = consolidate(source_dfs)

        # Compute data-driven hints for each reconciliation item.
        from backend.tools.hint_computer import compute_hints

        for item in recon_items:
            item.hints = compute_hints(
                item=item,
                consolidated_df=consolidated_df,
                period=period,
                source_raw_dfs=source_raw_dfs,
            )

        # Build the combined parse_preview in the same format the confirm route expects.
        # source_breakdown is included per-row so ParsePreviewPanel can render the
        # Sources column (which file contributed how much to each consolidated account).
        rows = [
            {
                "account": row["account"],
                "amount": float(row["amount"]),
                "category": row["category"],
                "confidence": 1.0,
                "source_breakdown": [
                    {"source_file": s["source_file"], "amount": s["amount"]}
                    for s in (row.get("source_breakdown") or [])
                ],
            }
            for _, row in consolidated_df.iterrows()
        ]

        source_breakdown_by_account: dict[str, list[dict]] = {}
        for _, row in consolidated_df.iterrows():
            acct = row["account"]
            source_breakdown_by_account[acct] = row.get("source_breakdown") or []

        reconciliations_payload = [item.model_dump(mode="json") for item in recon_items]

        parse_preview = {
            "rows": rows,
            "source_column": "Consolidated",
            "drops": {},
            "source_breakdown_by_account": source_breakdown_by_account,
            "reconciliations": reconciliations_payload,
            "is_multi_file": True,
        }

        runs_repo.set_parse_preview(run_id, parse_preview)
        runs_repo.set_file_count(run_id, len(storage_keys))

        await_status = RunStateMachine.transition(
            RunStatus.PARSING, RunStatus.AWAITING_CONFIRMATION
        )
        runs_repo.update_status(
            run_id,
            await_status,
            extra={
                "step": 3,
                "step_label": "Waiting for your review...",
                "progress_pct": 50,
            },
        )

        logger.info(
            "multi_file_consolidation_complete",
            extra={
                "run_id": run_id,
                "files": len(storage_keys),
                "consolidated_accounts": len(rows),
                "reconciliation_items": len(recon_items),
                "trace_id": get_trace_id(),
            },
        )

    except Exception as exc:
        logger.error(
            "run_multi_file_parser_until_preview unhandled exception",
            extra={
                "run_id": run_id,
                "error": str(exc),
                "trace_id": get_trace_id(),
            },
            exc_info=True,
        )
        _fail_if_not_terminal(run_id, messages.INTERNAL_ERROR)


def run_parser_until_preview(
    run_id: str,
    storage_key: str,
    company_id: str,
    period: date,
) -> None:
    """Run the parser and stop at AWAITING_CONFIRMATION.

    The pipeline resumes via POST /runs/{run_id}/confirm once the user
    reviews the preview and clicks "Confirm & Analyze".
    """
    try:
        parser = ParserAgent(
            file_storage=get_file_storage(),
            llm_client=get_llm_client(),
            accounts_repo=get_accounts_repo(),
            runs_repo=get_runs_repo(),
        )
        parser.run(
            run_id=run_id,
            company_id=company_id,
            storage_key=storage_key,
            period=period,
        )
    except DiscoveryLowConfidence as exc:
        # NOT a failure — Discovery wants user confirmation before continuing.
        # Contract (Step 9b): ParserAgent.discover() persists plan + _preview
        # to runs.discovery_plan BEFORE raising. Orchestrator only transitions
        # state so the frontend can switch to the DiscoveryConfirmationModal.
        logger.info(
            "discovery_awaiting_confirmation",
            extra={
                "run_id": run_id,
                "discovery_confidence": exc.plan.discovery_confidence,
                "trace_id": get_trace_id(),
            },
        )
        try:
            runs_repo = get_runs_repo()
            run = runs_repo.get_by_id(run_id)
            new_status = RunStateMachine.transition(
                run["status"], RunStatus.AWAITING_DISCOVERY_CONFIRMATION
            )
            runs_repo.update_status(
                run_id,
                new_status,
                extra={
                    "step": 2,
                    "step_label": "Waiting for your review...",
                    "progress_pct": 30,
                },
            )
        except Exception as inner:
            logger.error(
                "failed to transition to awaiting_discovery_confirmation",
                extra={"run_id": run_id, "inner_error": str(inner)},
            )
        return
    except Exception as exc:
        logger.error(
            "orchestrator.parser unhandled exception",
            extra={
                "run_id": run_id,
                "error": str(exc),
                "trace_id": get_trace_id(),
            },
            exc_info=True,
        )
        _fail_if_not_terminal(run_id, messages.INTERNAL_ERROR)


def run_comparison_and_report(
    run_id: str,
    company_id: str,
    period: date,
    storage_key: str,
) -> None:
    """Run comparison + interpreter after the user confirms the preview.

    Called from POST /runs/{run_id}/confirm as a BackgroundTask.
    The run is already in COMPARING when this fires.
    """
    try:
        comparison = ComparisonAgent(
            entries_repo=get_entries_repo(),
            anomalies_repo=get_anomalies_repo(),
            runs_repo=get_runs_repo(),
            accounts_repo=get_accounts_repo(),
        )
        interpreter = InterpreterAgent(
            llm_client=get_llm_client(),
            reports_repo=get_reports_repo(),
            runs_repo=get_runs_repo(),
            file_storage=get_file_storage(),
        )

        # Read reconciliations stored during multi-file parse (None for single-file runs)
        try:
            run_row = get_runs_repo().get_by_id(run_id)
            parse_preview = run_row.get("parse_preview") or {}
            reconciliations: list[dict] | None = (
                parse_preview.get("reconciliations") or None
            )
        except Exception:
            reconciliations = None

        pandas_summary = comparison.run(
            run_id=run_id,
            company_id=company_id,
            period=period,
        )

        try:
            get_runs_repo().set_pandas_summary(
                run_id, pandas_summary.model_dump(mode="json")
            )
        except Exception as summary_exc:
            logger.warning(
                "set_pandas_summary failed",
                extra={"run_id": run_id, "error": str(summary_exc)},
            )

        anomalies = get_anomalies_repo().list_for_period(company_id, period)

        completed = interpreter.run(
            pandas_summary=pandas_summary,
            anomalies=anomalies,
            run_id=run_id,
            reconciliations=reconciliations,
        )

        logger.info(
            "orchestrator complete",
            extra={
                "run_id": run_id,
                "anomaly_count": len(anomalies),
                "completed": completed,
                "trace_id": get_trace_id(),
            },
        )

        if completed:
            try:
                get_file_storage().delete(storage_key)
                logger.info(
                    "storage_cleanup_success",
                    extra={
                        "run_id": run_id,
                        "storage_key": storage_key,
                        "trace_id": get_trace_id(),
                    },
                )
            except Exception as cleanup_exc:
                logger.warning(
                    "storage_cleanup_failed",
                    extra={
                        "run_id": run_id,
                        "storage_key": storage_key,
                        "error": str(cleanup_exc),
                        "trace_id": get_trace_id(),
                    },
                )

    except Exception as exc:
        logger.error(
            "orchestrator unhandled exception",
            extra={
                "run_id": run_id,
                "error": str(exc),
                "trace_id": get_trace_id(),
            },
            exc_info=True,
        )
        _fail_if_not_terminal(run_id, messages.INTERNAL_ERROR)


def run_parser_after_discovery_approval(
    run_id: str,
    company_id: str,
    period: date,
    storage_key: str,
) -> None:
    """BackgroundTask fired from POST /runs/{run_id}/confirm-discovery.

    Resumes the pipeline from the approved plan:
    re-download → normalize → validate → map_accounts → parse_preview →
    AWAITING_CONFIRMATION.

    Step 9a skeleton: reads the stored plan, strips DB-only `_`-prefixed
    keys, validates it into a DiscoveryPlan, then delegates to
    `ParserAgent.resume_from_plan()` — which Step 9b will implement.
    Until 9b lands, calling this endpoint transitions the run to
    PARSING_FAILED via the bare-exception safety net below (AttributeError
    on the missing method). Acceptable interim behavior.
    """
    try:
        runs_repo = get_runs_repo()
        run = runs_repo.get_by_id(run_id)
        plan_dict = run.get("discovery_plan")
        if not plan_dict:
            logger.error(
                "resume_from_plan missing discovery_plan",
                extra={"run_id": run_id, "trace_id": get_trace_id()},
            )
            failed_status = RunStateMachine.transition(
                run["status"], RunStatus.PARSING_FAILED
            )
            runs_repo.update_status(
                run_id,
                failed_status,
                extra={"error_message": messages.INTERNAL_ERROR},
            )
            return

        # Strip DB-only keys (D7: `_preview` etc.) before Pydantic validation.
        clean = {k: v for k, v in plan_dict.items() if not str(k).startswith("_")}
        plan = DiscoveryPlan.model_validate(clean)

        parser = ParserAgent(
            file_storage=get_file_storage(),
            llm_client=get_llm_client(),
            accounts_repo=get_accounts_repo(),
            runs_repo=get_runs_repo(),
        )
        # Step 9b will add ParserAgent.resume_from_plan(). Until then the
        # getattr-guard below logs a clear TODO and falls through to the
        # bare-exception handler (→ PARSING_FAILED).
        resume = getattr(parser, "resume_from_plan", None)
        if resume is None:
            logger.error(
                "ParserAgent.resume_from_plan not yet implemented (Step 9b)",
                extra={"run_id": run_id, "trace_id": get_trace_id()},
            )
            raise NotImplementedError("ParserAgent.resume_from_plan — Step 9b")
        resume(
            run_id=run_id,
            company_id=company_id,
            storage_key=storage_key,
            period=period,
            plan=plan,
        )
    except Exception as exc:
        logger.error(
            "run_parser_after_discovery_approval unhandled exception",
            extra={
                "run_id": run_id,
                "error": str(exc),
                "trace_id": get_trace_id(),
            },
            exc_info=True,
        )
        _fail_if_not_terminal(run_id, messages.INTERNAL_ERROR)
