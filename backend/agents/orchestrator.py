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
    get_companies_repo,
    get_entries_repo,
    get_file_storage,
    get_llm_client,
    get_reports_repo,
    get_runs_repo,
    get_source_mappings_repo,
)
from backend.agents.account_mapper import AccountMapper
from backend.domain.contracts import (
    DEFAULT_GL_CATEGORIES,
    DiscoveryPlan,
    MappingDraft,
    MappingDraftItem,
)
from backend.domain.errors import DiscoveryLowConfidence, MappingAmbiguous
from backend.domain.run_state_machine import RunStateMachine, RunStatus
from backend.logger import get_logger, get_trace_id
from backend.tools.file_type import FILE_TYPE_PATTERNS, detect_file_type
from backend.tools.mapping_grain import (
    FILE_TOTAL_PATTERN,
    proposed_contracts_gl,
    should_file_total_after_parse,
)
from backend.tools.source_mapping import (
    annotate_draft_items,
    auto_map_payroll,
    index_stored,
    is_payroll,
    needs_user_review,
    remembered_decisions,
)

# Tests still import these aliases from orchestrator.
_FILE_TYPE_PATTERNS = FILE_TYPE_PATTERNS
_detect_file_type = detect_file_type


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
        RunStatus.REPORT_FAILED.value,
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
                preview_rows, source_column, raw_df, sidecar = _unpack_parse(
                    parser.parse_file_silently(
                        storage_key=key,
                        company_id=company_id,
                        period=period,
                        run_id=run_id,
                        file_type="general_ledger",
                    )
                )
                per_file_data.append(
                    (
                        label,
                        preview_rows,
                        source_column,
                        raw_df,
                        True,
                        "general_ledger",
                        sidecar,
                    )
                )
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
        for label, preview_rows, _, raw_df, *_ in per_file_data:
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
            companies_repo=get_companies_repo(),
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
            # Mark any quarterly report covering this period as stale
            try:
                month = period.month
                quarter = (month - 1) // 3 + 1
                year = period.year
                get_reports_repo().mark_quarterly_stale(company_id, year, quarter)
                logger.info(
                    "marked_quarterly_stale",
                    extra={
                        "company_id": company_id,
                        "year": year,
                        "quarter": quarter,
                        "trace_id": get_trace_id(),
                    },
                )
            except Exception as stale_exc:
                # Non-critical — log and continue
                logger.warning(
                    "mark_quarterly_stale failed",
                    extra={"period": str(period), "error": str(stale_exc)},
                )

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
    AWAITING_CONFIRMATION using ParserAgent.resume_from_plan().
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
        parser.resume_from_plan(
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


# ---------------------------------------------------------------------------
# AccountMapper pipeline — Phase A + Phase B
# ---------------------------------------------------------------------------

# File-type needles live in backend.tools.file_type so the close checklist
# and the mapper cannot drift. Re-exported under the original names.


def _attach_roster_counts(recon_items, per_file_data, period, run_id) -> None:
    """Item 4 — attach RMR roster counts to the mapped GL revenue item.

    Runs beside the consolidator, never inside it, exactly like
    _attach_batch_matches. Every gate below fails closed: attach nothing and
    log, leaving today's dollar-only behaviour untouched.

    R.4 — one roster file per run.
    R.5 — the roster must resolve to exactly one mapped GL account.
    R.7 — never resurrect an item consolidate already dropped as immaterial.
    """
    from backend.tools import roster_counts

    rosters = [
        entry
        for entry in per_file_data
        if len(entry) >= 7 and entry[5] == "contracts" and entry[6] is not None
    ]

    # R.4: merging two rosters needs a cross-file identity rule that does not
    # exist; guessing one would double-count or silently drop accounts.
    if len(rosters) != 1:
        if len(rosters) > 1:
            logger.info(
                "roster_counts_skipped",
                extra={
                    "run_id": run_id,
                    "reason": "more than one contracts file",
                    "files": len(rosters),
                },
            )
        else:
            # Counts silently going missing cost a full diagnostic session
            # once already: a contracts file present but carrying no sidecar
            # looks identical to no contracts file at all. Names are never
            # logged — counts only.
            contracts_files = sum(
                1
                for entry in per_file_data
                if len(entry) >= 6 and entry[5] == "contracts"
            )
            logger.info(
                "roster_counts_skipped",
                extra={
                    "run_id": run_id,
                    "reason": "no contracts file with a sidecar",
                    "contracts_files": contracts_files,
                    "files": len(per_file_data),
                },
            )
        return

    label, preview_rows, _, _, _, _, sidecar = rosters[0][:7]

    # R.5: attaching "85 accounts" to a line that only represents some of them
    # would be false, so require exactly one mapped account.
    accounts = sorted({str(r.get("account")) for r in (preview_rows or [])})
    if len(accounts) != 1:
        logger.info(
            "roster_counts_skipped",
            extra={
                "run_id": run_id,
                "reason": "roster did not map to exactly one " "GL account",
                "mapped_accounts": len(accounts),
            },
        )
        return
    target_account = accounts[0]

    counts = roster_counts.compute(sidecar, period)
    if counts is None:
        return

    # R.7: a count-only card is not a reason to override materiality.
    target = next((i for i in recon_items if i.account == target_account), None)
    if target is None:
        logger.info(
            "roster_counts_no_item",
            extra={
                "run_id": run_id,
                "account": target_account,
                "reason": "account not present in recon items (immaterial or "
                "fully tied out); counts discarded",
            },
        )
        return

    target.hints.n_active = counts.n_active
    target.hints.n_billed_in_period = counts.n_billed_in_period
    target.hints.count_delta = counts.count_delta
    target.hints.fee_sum_active = counts.fee_sum_active
    target.hints.fee_sum_billed = counts.fee_sum_billed
    target.hints.fee_gap = counts.fee_gap

    logger.info(
        "roster_counts_attached",
        extra={
            "run_id": run_id,
            "account": target_account,
            "n_active": counts.n_active,
            "n_billed_in_period": counts.n_billed_in_period,
            "count_delta": counts.count_delta,
        },
    )


def _attach_batch_matches(recon_items, per_file_data, period, run_id) -> None:
    """Run the Item 1 three-way matcher beside the consolidator.

    The consolidator must never become the matcher (spec C.6), so this runs
    after consolidate() on the sidecars the parser preserved, and only attaches
    its result to the Undeposited Funds reconciliation item.

    Gate: BOTH a processor/FSM sidecar AND a bank sidecar must be present.
    Without a settlement file there is no net side, so nothing can be tied out
    three ways — Vandelay payouts with no bank file must fall back to Kova 1's
    account-total fee hint rather than have this claim a three-way match.
    """
    from backend.tools.batch_matcher import match
    from backend.tools.sidecar import _DEFAULT_UF_ACCOUNT_NAME

    sidecars: dict[str, object] = {}
    for entry in per_file_data:
        if len(entry) < 7:
            continue
        file_type, sidecar = entry[5], entry[6]
        if sidecar is not None and file_type not in sidecars:
            sidecars[file_type] = sidecar

    if "processor_settlement" not in sidecars or "bank_statement" not in sidecars:
        if sidecars.get("processor_settlement") is not None:
            logger.info(
                "batch_matcher_skipped_no_bank_file",
                extra={
                    "run_id": run_id,
                    "reason": "processor file without a bank file",
                },
            )
        return

    result = match(
        sidecars.get("processor_settlement"),
        sidecars.get("general_ledger"),
        sidecars.get("bank_statement"),
        period,
        _DEFAULT_UF_ACCOUNT_NAME,
    )
    if not result.matches:
        return

    target = next(
        (i for i in recon_items if i.account == _DEFAULT_UF_ACCOUNT_NAME), None
    )
    if target is None:
        # No UF line on the consolidated view — nothing to nest under. Do not
        # invent a card; log so this is visible rather than silent.
        logger.warning(
            "batch_matcher_no_uf_item",
            extra={
                "run_id": run_id,
                "uf_account": _DEFAULT_UF_ACCOUNT_NAME,
                "matches": len(result.matches),
            },
        )
        return

    target.matches = result.matches
    logger.info(
        "batch_matcher_attached",
        extra={
            "run_id": run_id,
            "account": target.account,
            "matches": len(result.matches),
            "unmatched_processor": result.unmatched_processor_count,
            "unmatched_bank": result.unmatched_bank_count,
        },
    )


def _unpack_parse(result) -> tuple:
    """Unpack parse_file_silently, tolerating the pre-Item-1 three-tuple.

    Existing orchestrator tests stub the parser with a 3-tuple; the real parser
    now returns a 4th element (the matcher sidecar, None for every file type
    the matcher does not consume).
    """
    if len(result) == 4:
        return result
    preview_rows, source_column, raw_df = result
    return preview_rows, source_column, raw_df, None


def run_multi_file_parser_with_mapping(
    run_id: str,
    storage_keys: list[str],
    company_id: str,
    period: date,
) -> None:
    """Phase A: parse all files, map non-GL source values, pause only if needed.

    Payroll lines are identity-mapped and never shown for review. Vendor and
    expense names are compared to saved mappings; Haiku still runs, and a
    disagreement pauses for the user. If nothing needs a decision, Phase B
    (`apply_mapping_and_consolidate`) runs immediately.

    When review is required, Phase B is triggered by POST /runs/{id}/confirm-mappings.
    All-GL uploads still skip mapping and consolidate directly.
    """
    import pandas as pd

    from backend.agents.consolidator import _is_gl_label

    try:
        parser = ParserAgent(
            file_storage=get_file_storage(),
            llm_client=get_llm_client(),
            accounts_repo=get_accounts_repo(),
            runs_repo=get_runs_repo(),
        )
        mapper = AccountMapper(llm_client=get_llm_client())
        runs_repo = get_runs_repo()
        accounts_repo = get_accounts_repo()

        runs_repo.update_status(
            run_id,
            RunStatus.PARSING,
            extra={
                "step": 1,
                "step_label": f"Reading {len(storage_keys)} files...",
                "progress_pct": 10,
            },
        )

        # GL files first so accounts_repo is populated before dept files are mapped.
        sorted_keys = sorted(
            storage_keys, key=lambda k: 0 if _is_gl_label(k.split("/")[-1]) else 1
        )

        # Captured immediately after the GL file is parsed — before non-GL files
        # write vendor names / employee names / POS categories into the accounts
        # table via _map_accounts. Reading the pool after all files are parsed
        # would contaminate it with non-GL values and let the AccountMapper treat
        # "Sysco Corporation" as a valid GL account target.
        gl_pool: list[str] = []

        per_file_data: list[tuple[str, list[dict], str, pd.DataFrame, bool, str]] = []
        for i, key in enumerate(sorted_keys):
            label = key.split("/")[-1]
            is_gl = _is_gl_label(label)
            file_type = "general_ledger" if is_gl else _detect_file_type(label)
            try:
                preview_rows, source_column, raw_df, sidecar = _unpack_parse(
                    parser.parse_file_silently(
                        storage_key=key,
                        company_id=company_id,
                        period=period,
                        run_id=run_id,
                        file_type=file_type,
                    )
                )
                per_file_data.append(
                    (
                        label,
                        preview_rows,
                        source_column,
                        raw_df,
                        is_gl,
                        file_type,
                        sidecar,
                    )
                )
                # Capture the GL pool right after the GL file is parsed so it
                # contains only chart-of-accounts names, not source-file values.
                if is_gl and not gl_pool:
                    gl_pool = list(accounts_repo.list_for_company(company_id).keys())
                logger.info(
                    "multi_file_parsed_with_mapping",
                    extra={
                        "run_id": run_id,
                        "file": label,
                        "file_type": file_type,
                        "accounts": len(preview_rows),
                        "index": i + 1,
                        "total": len(sorted_keys),
                        "trace_id": get_trace_id(),
                    },
                )
            except MappingAmbiguous:
                _fail_if_not_terminal(
                    run_id,
                    (
                        messages.CONTROL_CONTRACT_SCHEMA
                        if file_type == "contracts"
                        else messages.MAPPING_FAILED
                    ),
                )
                return
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

        # Fall back to GAAP defaults when no GL file was included in the upload.
        if not gl_pool:
            gl_pool = list(DEFAULT_GL_CATEGORIES)

        # Run AccountMapper for persistable / reviewable non-GL files.
        # Payroll GL names stay identity-mapped. Payroll roles and file totals
        # pause for confirmation and are never sent to Haiku.
        file_keys = {}
        for entry, key in zip(per_file_data, sorted_keys):
            file_keys[entry[0]] = key

        stored_index = index_stored(
            get_source_mappings_repo().list_for_company(company_id)
        )
        auto_decisions: dict[str, str] = {}
        all_draft_items = []

        for (
            label,
            preview_rows,
            source_column,
            detailed,
            is_gl,
            file_type,
            _sidecar,
        ) in (
            (e[0], e[1], e[2], e[3], e[4], e[5], e[6] if len(e) > 6 else None)
            for e in per_file_data
        ):
            if is_gl:
                continue
            unique_values = sorted(
                {row["account"] for row in preview_rows if row.get("account")}
            )
            source_amount = round(
                sum(float(row.get("amount") or 0) for row in preview_rows), 2
            )
            if should_file_total_after_parse(
                file_type,
                unique_values,
                gl_pool,
                validated_file_total=detailed.attrs.get("file_total_candidate") is True,
            ):
                suggested = (
                    proposed_contracts_gl(gl_pool) if file_type == "contracts" else None
                )
                all_draft_items.append(
                    MappingDraftItem(
                        source_pattern=FILE_TOTAL_PATTERN,
                        source_file=label,
                        file_type=file_type,
                        suggested_gl_account=suggested,
                        confident=bool(suggested),
                        mapping_mode="file_total",
                        amount_scope=source_column or "amount",
                        source_amount=source_amount,
                        period=period,
                    )
                )
                continue
            if is_payroll(file_type):
                if unique_values and all(v in gl_pool for v in unique_values):
                    auto_decisions.update(auto_map_payroll(unique_values))
                    logger.info(
                        "payroll_identity_mapped",
                        extra={
                            "run_id": run_id,
                            "file": label,
                            "lines": len(unique_values),
                            "trace_id": get_trace_id(),
                        },
                    )
                    continue
                for value in unique_values:
                    all_draft_items.append(
                        MappingDraftItem(
                            source_pattern=value,
                            source_file=label,
                            file_type=file_type,
                            suggested_gl_account=None,
                            confident=False,
                            mapping_mode="row",
                            amount_scope=source_column or "amount",
                            period=period,
                        )
                    )
                continue
            _, draft = mapper.build_draft(
                unique_values=unique_values,
                file_type=file_type,
                source_file=label,
                gl_pool=gl_pool,
            )
            annotated = annotate_draft_items(draft.items, stored_index)
            all_draft_items.extend(annotated)
            auto_decisions.update(remembered_decisions(annotated))

        aggregate_draft = MappingDraft(items=all_draft_items, gl_account_pool=gl_pool)

        if not all_draft_items and not auto_decisions:
            # All files are GL — skip mapping, consolidate directly.
            _run_consolidation(
                run_id,
                company_id,
                period,
                per_file_data,
                runs_repo,
                storage_keys=sorted_keys,
            )
            return

        parse_preview = {
            "mapping_draft": aggregate_draft.model_dump(mode="json"),
            "file_keys": file_keys,
            "is_multi_file": True,
            "auto_decisions": auto_decisions,
        }
        runs_repo.set_parse_preview(run_id, parse_preview)
        runs_repo.set_file_count(run_id, len(sorted_keys))

        if not needs_user_review(all_draft_items):
            applying_status = RunStateMachine.transition(
                RunStatus.PARSING, RunStatus.APPLYING_MAPPING
            )
            runs_repo.update_status(
                run_id,
                applying_status,
                extra={
                    "step": 2,
                    "step_label": "Applying saved mappings...",
                    "progress_pct": 55,
                },
            )
            apply_mapping_and_consolidate(
                run_id=run_id,
                company_id=company_id,
                period=period,
                user_decisions=auto_decisions,
            )
            return

        await_map_status = RunStateMachine.transition(
            RunStatus.PARSING, RunStatus.AWAITING_MAPPING_CONFIRMATION
        )
        runs_repo.update_status(
            run_id,
            await_map_status,
            extra={
                "step": 2,
                "step_label": "Review vendor and expense names...",
                "progress_pct": 50,
            },
        )
        logger.info(
            "mapping_draft_ready",
            extra={
                "run_id": run_id,
                "draft_items": len(all_draft_items),
                "files": len(sorted_keys),
                "trace_id": get_trace_id(),
            },
        )

    except Exception as exc:
        logger.error(
            "run_multi_file_parser_with_mapping unhandled exception",
            extra={"run_id": run_id, "error": str(exc), "trace_id": get_trace_id()},
            exc_info=True,
        )
        _fail_if_not_terminal(run_id, messages.INTERNAL_ERROR)


def apply_mapping_and_consolidate(
    run_id: str,
    company_id: str,
    period: date,
    user_decisions: dict[str, str],
) -> None:
    """Phase B: apply user-approved mappings, re-parse files, consolidate.

    Re-downloads each file from Storage (double-parse approach — files remain
    in Storage until COMPLETE per existing architecture). Applies user_decisions
    as account_name_map in parse_file_silently for non-GL files, then runs the
    full consolidation pipeline and transitions to AWAITING_CONFIRMATION.

    user_decisions: {source_pattern: gl_account_name}
    """
    import pandas as pd

    from backend.agents.consolidator import _is_gl_label

    try:
        parser = ParserAgent(
            file_storage=get_file_storage(),
            llm_client=get_llm_client(),
            accounts_repo=get_accounts_repo(),
            runs_repo=get_runs_repo(),
        )
        runs_repo = get_runs_repo()

        # Validate state. The confirm-mappings endpoint already transitioned to
        # APPLYING_MAPPING before firing this background task, so any duplicate
        # invocation (caused by the frontend re-triggering before Phase B completes)
        # will find a non-matching status and exit immediately.
        run = runs_repo.get_by_id(run_id)
        current_status = run.get("status")
        if current_status != RunStatus.APPLYING_MAPPING.value:
            logger.error(
                "apply_mapping wrong state — likely a duplicate invocation",
                extra={"run_id": run_id, "status": current_status},
            )
            return

        parse_preview = run.get("parse_preview") or {}
        file_keys: dict[str, str] = parse_preview.get("file_keys", {})
        auto_decisions: dict[str, str] = parse_preview.get("auto_decisions") or {}
        merged_decisions = {**auto_decisions, **(user_decisions or {})}
        file_total_decisions: dict[str, str] = dict(
            parse_preview.get("file_total_decisions") or {}
        )

        if not file_keys:
            logger.error(
                "apply_mapping no file_keys in parse_preview", extra={"run_id": run_id}
            )
            _fail_if_not_terminal(run_id, messages.INTERNAL_ERROR)
            return

        # Re-parse each file applying user decisions for non-GL files.
        per_file_data: list[tuple[str, list[dict], str, pd.DataFrame, bool, str]] = []
        for label, storage_key in file_keys.items():
            is_gl = _is_gl_label(label)
            file_type = "general_ledger" if is_gl else _detect_file_type(label)
            file_total_account = None if is_gl else file_total_decisions.get(label)
            account_name_map = (
                None if is_gl or file_total_account else (merged_decisions or None)
            )
            try:
                preview_rows, source_column, raw_df, sidecar = _unpack_parse(
                    parser.parse_file_silently(
                        storage_key=storage_key,
                        company_id=company_id,
                        period=period,
                        run_id=run_id,
                        account_name_map=account_name_map,
                        file_type=file_type,
                        file_total_account=file_total_account,
                    )
                )
                per_file_data.append(
                    (
                        label,
                        preview_rows,
                        source_column,
                        raw_df,
                        is_gl,
                        file_type,
                        sidecar,
                    )
                )
                logger.info(
                    "apply_mapping_parsed",
                    extra={
                        "run_id": run_id,
                        "file": label,
                        "is_gl": is_gl,
                        "trace_id": get_trace_id(),
                    },
                )
            except Exception as exc:
                logger.error(
                    "apply_mapping parse error",
                    extra={"run_id": run_id, "file": label, "error": str(exc)},
                )
                _fail_if_not_terminal(run_id, messages.PARSE_FAILED)
                return

        storage_keys_ordered = list(file_keys.values())
        _run_consolidation(
            run_id,
            company_id,
            period,
            per_file_data,
            runs_repo,
            storage_keys=storage_keys_ordered,
            from_status=RunStatus.APPLYING_MAPPING,
        )

    except Exception as exc:
        logger.error(
            "apply_mapping_and_consolidate unhandled exception",
            extra={"run_id": run_id, "error": str(exc), "trace_id": get_trace_id()},
            exc_info=True,
        )
        _fail_if_not_terminal(run_id, messages.INTERNAL_ERROR)


def _run_consolidation(
    run_id: str,
    company_id: str,
    period: date,
    per_file_data: list,
    runs_repo,
    storage_keys: list[str],
    from_status: RunStatus = RunStatus.PARSING,
) -> None:
    """Shared consolidation logic for both Phase A (all-GL) and Phase B.

    Builds source_dfs, runs consolidate(), computes hints, writes parse_preview,
    transitions to AWAITING_CONFIRMATION.
    """
    import pandas as pd

    from backend.tools.hint_computer import compute_hints

    runs_repo.update_status(
        run_id,
        from_status,
        extra={"step_label": "Consolidating files...", "progress_pct": 60},
    )

    source_dfs: list[tuple[str, pd.DataFrame]] = []
    source_raw_dfs: dict[str, pd.DataFrame] = {}
    for label, preview_rows, _, raw_df, *_ in per_file_data:
        source_dfs.append((label, pd.DataFrame(preview_rows)))
        source_raw_dfs[label] = raw_df

    consolidated_df, recon_items = consolidate(source_dfs)

    for item in recon_items:
        item.hints = compute_hints(
            item=item,
            consolidated_df=consolidated_df,
            period=period,
            source_raw_dfs=source_raw_dfs,
        )

    _attach_batch_matches(recon_items, per_file_data, period, run_id)
    _attach_roster_counts(recon_items, per_file_data, period, run_id)

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

    try:
        existing_preview = runs_repo.get_by_id(run_id).get("parse_preview") or {}
    except Exception:
        existing_preview = {}

    gl_amounts: dict[str, float] = {}
    amount_scopes: dict[str, str] = {}
    empty_files: list[str] = []
    mapping_modes: dict[str, str] = {}
    file_total = dict(existing_preview.get("file_total_decisions") or {})
    per_file_rows: dict[str, list] = {}
    source_files: list[str] = []
    from backend.agents.consolidator import _is_gl_label as is_gl_name

    for entry in per_file_data:
        label = entry[0]
        preview_rows = entry[1]
        source_column = entry[2]
        is_gl = bool(entry[4]) if len(entry) > 4 else is_gl_name(label)
        source_files.append(label)
        per_file_rows[label] = list(preview_rows or [])
        amount_scopes[label] = str(source_column or "amount")
        if not preview_rows:
            empty_files.append(label)
        if is_gl or is_gl_name(label):
            for row in preview_rows or []:
                name = str(row.get("account") or "").strip()
                if name:
                    gl_amounts[name] = float(row.get("amount") or 0)
        elif label in file_total:
            mapping_modes[label] = "file_total"
        else:
            mapping_modes[label] = "row"

    parse_preview = {
        "rows": rows,
        "source_column": "Consolidated",
        "drops": {},
        "source_breakdown_by_account": source_breakdown_by_account,
        "reconciliations": reconciliations_payload,
        "is_multi_file": True,
        "file_total_decisions": file_total,
        "control_source_files": source_files,
        "control_per_file_rows": per_file_rows,
        "control_gl_amounts": gl_amounts,
        "control_amount_scopes": amount_scopes,
        "control_empty_files": empty_files,
        "control_mapping_modes": mapping_modes,
        "control_mapping_pending": [],
        "control_period": period.isoformat(),
    }

    runs_repo.set_parse_preview(run_id, parse_preview)
    runs_repo.set_file_count(run_id, len(storage_keys))

    await_status = RunStateMachine.transition(
        from_status, RunStatus.AWAITING_CONFIRMATION
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
