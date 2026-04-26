from __future__ import annotations

import tempfile
from datetime import date
from pathlib import Path

import pandas as pd

from backend import messages
from backend.agents.discovery import DiscoveryAgent
from backend.domain.contracts import (
    DiscoveryPlan,
    MappingOutput,
    MappingResponse,
    ParserOutput,
)
from backend.domain.errors import (
    DiscoveryFailed,
    DiscoveryLowConfidence,
    FileHasNoValidColumns,
    MappingAmbiguous,
    TransientIOError,
)
from backend.domain.ports import (
    AccountsRepo,
    FileStorage,
    LLMClient,
    RunsRepo,
)
from backend.domain.run_state_machine import RunStateMachine, RunStatus
from backend.logger import get_logger
from backend.tools import file_reader, normalizer, pii_sanitizer, validator

logger = get_logger(__name__)

MAPPING_MODEL = "claude-haiku-4-5-20251001"

_HIGH_CONFIDENCE_THRESHOLD = 0.80


class ParserAgent:
    def __init__(
        self,
        file_storage: FileStorage,
        llm_client: LLMClient,
        accounts_repo: AccountsRepo,
        runs_repo: RunsRepo,
        discovery_agent: DiscoveryAgent | None = None,
    ) -> None:
        self._storage = file_storage
        self._llm = llm_client
        self._accounts = accounts_repo
        self._runs = runs_repo
        # Auto-construct DiscoveryAgent from the LLM client unless caller injects one.
        self._discovery = discovery_agent or DiscoveryAgent(llm_client)

    def run(
        self,
        run_id: str,
        company_id: str,
        storage_key: str,
        period: date,
    ) -> ParserOutput:
        """End-to-end parser entry. Delegates to discover() + resume_from_plan().

        On high-confidence Discovery: runs end-to-end, returns ParserOutput.
        On low-confidence Discovery: discover() persists plan + _preview and
        raises DiscoveryLowConfidence; caller (orchestrator) transitions
        state to AWAITING_DISCOVERY_CONFIRMATION. Raises propagate up.
        """
        plan = self.discover(run_id, company_id, storage_key, period)
        return self.resume_from_plan(run_id, company_id, storage_key, period, plan)

    # ------------------------------------------------------------------ #
    # Phase A — Discovery                                                #
    # ------------------------------------------------------------------ #

    def discover(
        self,
        run_id: str,
        company_id: str,
        storage_key: str,
        period: date,
    ) -> DiscoveryPlan:
        """Download → sample → sanitize_sample → DiscoveryAgent → persist plan.

        High confidence (>= 0.80):
          - Persists plan + _preview to runs.discovery_plan with
            approval_mode='auto'.
          - Transitions DISCOVERING → MAPPING.
          - Returns the plan.

        Low confidence (< 0.80):
          - Persists plan + _preview with approval_mode left NULL.
          - Re-raises DiscoveryLowConfidence for the orchestrator to
            transition to AWAITING_DISCOVERY_CONFIRMATION.

        Hard failure:
          - Transitions to PARSING_FAILED, raises.
        """
        # pending → parsing
        run = self._runs.get_by_id(run_id)
        new_status = RunStateMachine.transition(run["status"], RunStatus.PARSING)
        self._runs.update_status(
            run_id,
            new_status,
            extra={"step": 1, "step_label": "Reading files...", "progress_pct": 20},
        )

        # Read the first 100x10 cells for Discovery's sample
        try:
            sample = self._read_sample(storage_key)
        except Exception:
            self._fail(run_id, RunStatus.PARSING, messages.PARSE_FAILED)
            raise

        # Value-level PII redaction BEFORE any Claude call (R-006).
        sample = pii_sanitizer.sanitize_sample(sample, run_id=run_id)

        # parsing → discovering
        disc_status = RunStateMachine.transition(
            RunStatus.PARSING, RunStatus.DISCOVERING
        )
        self._runs.update_status(
            run_id,
            disc_status,
            extra={
                "step": 2,
                "step_label": messages.DISCOVERING_STEP_LABEL,
                "progress_pct": 30,
            },
        )

        try:
            plan = self._discovery.discover(run_id, sample)
        except DiscoveryLowConfidence as exc:
            # Persist plan + _preview BEFORE re-raising (9a orchestrator contract).
            # approval_mode stays NULL — user hasn't approved yet.
            plan_dict = exc.plan.model_dump(mode="json")
            plan_dict["_preview"] = pii_sanitizer.build_preview_snippet(sample)
            try:
                self._runs.set_discovery_plan(run_id, plan_dict)
            except Exception as inner:
                logger.warning(
                    "failed to persist low-confidence plan",
                    extra={"run_id": run_id, "error": str(inner)},
                )
            raise
        except DiscoveryFailed:
            self._fail(run_id, RunStatus.DISCOVERING, messages.PARSE_FAILED)
            raise
        except Exception:
            self._fail(run_id, RunStatus.DISCOVERING, messages.PARSE_FAILED)
            raise

        # High-confidence auto-approve path
        plan_dict = plan.model_dump(mode="json")
        plan_dict["_preview"] = pii_sanitizer.build_preview_snippet(sample)
        try:
            self._runs.set_discovery_plan(run_id, plan_dict, approval_mode="auto")
        except Exception as inner:
            logger.warning(
                "failed to persist auto-approved plan",
                extra={"run_id": run_id, "error": str(inner)},
            )

        # Update: discovery complete
        try:
            self._runs.update_status(
                run_id,
                RunStatus.DISCOVERING,
                extra={"progress_pct": 35},
            )
        except Exception:
            pass

        # discovering → mapping
        map_status = RunStateMachine.transition(
            RunStatus.DISCOVERING, RunStatus.MAPPING
        )
        self._runs.update_status(
            run_id,
            map_status,
            extra={"step": 3, "step_label": "Mapping accounts...", "progress_pct": 38},
        )

        return plan

    # ------------------------------------------------------------------ #
    # Phase B — Resume from approved plan                                #
    # ------------------------------------------------------------------ #

    def resume_from_plan(
        self,
        run_id: str,
        company_id: str,
        storage_key: str,
        period: date,
        plan: DiscoveryPlan,
    ) -> ParserOutput:
        """Apply approved plan: re-download → sanitize → normalize → validate →
        map → preview → AWAITING_CONFIRMATION.

        Assumes the run is in MAPPING status on entry. Both the auto-advance
        path (discover() → resume_from_plan inline) and the user-approval
        path (confirm-discovery → orchestrator.run_parser_after_discovery_approval
        → resume_from_plan) arrive here with MAPPING already set.
        """
        # Re-download the full file. Storage persists per R-015 until COMPLETE.
        try:
            df_raw = self._read_full(storage_key)
        except Exception:
            self._fail(run_id, RunStatus.MAPPING, messages.PARSE_FAILED)
            raise

        # Column-level PII blacklist (still required post-Discovery).
        try:
            df_raw = pii_sanitizer.sanitize(df_raw, run_id=run_id)
        except FileHasNoValidColumns:
            self._fail(run_id, RunStatus.MAPPING, messages.FILE_HAS_NO_VALID_COLUMNS)
            raise

        # Update: sanitization complete, normalizing data
        try:
            self._runs.update_status(
                run_id,
                RunStatus.MAPPING,
                extra={"progress_pct": 42},
            )
        except Exception:
            pass

        # Deterministic normalization via the DiscoveryPlan. Returns a
        # (DataFrame, NormalizerDropReport) pair — the report surfaces
        # rows dropped by amount-coercion or the subtotal safety net.
        try:
            df_normalized, drop_report = normalizer.apply_plan(df_raw, plan, period)
        except Exception:
            self._fail(run_id, RunStatus.MAPPING, messages.PARSE_FAILED)
            raise

        # Update: normalization complete, validating
        try:
            self._runs.update_status(
                run_id,
                RunStatus.MAPPING,
                extra={"progress_pct": 45},
            )
        except Exception:
            pass

        # Golden Schema validation.
        try:
            df_validated = validator.validate(df_normalized)
        except Exception:
            self._fail(run_id, RunStatus.MAPPING, messages.PARSE_FAILED)
            raise

        # Capture verbatim header that was mapped to "amount" for provenance.
        source_column = self._extract_source_column(plan)

        # Update: validation complete, mapping accounts
        try:
            self._runs.update_status(
                run_id,
                RunStatus.MAPPING,
                extra={"progress_pct": 48},
            )
        except Exception:
            pass

        # Enriched account mapping (parent_category / account_code / department).
        try:
            mapped_columns, low_confidence_columns = self._map_accounts(
                run_id, company_id, df_validated
            )
        except MappingAmbiguous:
            self._fail(run_id, RunStatus.MAPPING, messages.MAPPING_FAILED)
            raise
        except Exception:
            self._fail(run_id, RunStatus.MAPPING, messages.PARSE_FAILED)
            raise

        # Update: mapping complete, building preview
        try:
            self._runs.update_status(
                run_id,
                RunStatus.MAPPING,
                extra={"progress_pct": 52},
            )
        except Exception:
            pass

        # Aggregated preview — one row per account.
        account_totals: dict[str, float] = (
            df_validated.groupby("account")["amount"].sum().to_dict()
        )
        preview_rows = [
            {
                "account": name,
                "amount": float(account_totals[name]),
                "category": mapped_columns.get(name, {}).get("category", "OTHER"),
                "confidence": mapped_columns.get(name, {}).get("confidence", 0.0),
            }
            for name in sorted(account_totals.keys())
        ]
        parse_preview = {
            "rows": preview_rows,
            "source_column": source_column,
            "drops": drop_report.model_dump(),
        }

        try:
            self._runs.set_parse_preview(run_id, parse_preview)
        except Exception as exc:
            logger.warning(
                "set_parse_preview failed",
                extra={"run_id": run_id, "error": str(exc)},
            )

        # mapping → awaiting_confirmation (existing commit gate for monthly_entries)
        await_status = RunStateMachine.transition(
            RunStatus.MAPPING, RunStatus.AWAITING_CONFIRMATION
        )
        self._runs.update_status(
            run_id,
            await_status,
            extra={
                "step": 3,
                "step_label": "Waiting for your review...",
                "progress_pct": 50,
            },
        )

        return ParserOutput(
            run_id=run_id,
            rows_parsed=len(preview_rows),
            mapped_columns=mapped_columns,
            metadata_rows_skipped=len(plan.skip_row_indices),
            pandera_errors=[],
            warnings=[],
            low_confidence_columns=[m.model_dump() for m in low_confidence_columns],
        )

    # ------------------------------------------------------------------ #
    # File I/O helpers                                                   #
    # ------------------------------------------------------------------ #

    def _read_sample(self, storage_key: str) -> list[dict]:
        """Download and return the 100x10 raw-cell sample for Discovery."""
        raw_bytes = self._storage.download(storage_key)
        suffix = Path(storage_key).suffix or ".xlsx"
        tmp_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
                tmp.write(raw_bytes)
                tmp_path = Path(tmp.name)
            return file_reader.read_raw_cells(tmp_path)
        finally:
            if tmp_path and tmp_path.exists():
                tmp_path.unlink(missing_ok=True)

    def _read_full(self, storage_key: str) -> pd.DataFrame:
        """Download and return the full DataFrame for Normalizer."""
        raw_bytes = self._storage.download(storage_key)
        suffix = Path(storage_key).suffix or ".xlsx"
        tmp_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
                tmp.write(raw_bytes)
                tmp_path = Path(tmp.name)
            return file_reader.read_file(tmp_path)
        finally:
            if tmp_path and tmp_path.exists():
                tmp_path.unlink(missing_ok=True)

    @staticmethod
    def _extract_source_column(plan: DiscoveryPlan) -> str:
        for src, tgt in plan.column_mapping.items():
            if tgt == "amount":
                return str(src)
        return "amount"

    # ------------------------------------------------------------------ #
    # Account mapping (enriched input shape)                             #
    # ------------------------------------------------------------------ #

    def _map_accounts(
        self,
        run_id: str,
        company_id: str,
        df: pd.DataFrame,
    ) -> tuple[dict[str, dict], list[MappingOutput]]:
        """Build per-account context with hierarchy fields, then call Haiku."""
        grouped = df.groupby("account", dropna=False)

        def _first_nonnull(series: pd.Series) -> str | None:
            s = series.dropna()
            return str(s.iloc[0]) if not s.empty else None

        account_info: dict[str, dict] = {}
        for account_name, group in grouped:
            name_str = str(account_name)
            account_info[name_str] = {
                "name": name_str,
                "total": float(group["amount"].sum()),
                "parent_category": _first_nonnull(
                    group["parent_category"]
                    if "parent_category" in group.columns
                    else pd.Series([], dtype=object)
                ),
                "account_code": _first_nonnull(
                    group["account_code"]
                    if "account_code" in group.columns
                    else pd.Series([], dtype=object)
                ),
                "department": _first_nonnull(
                    group["department"]
                    if "department" in group.columns
                    else pd.Series([], dtype=object)
                ),
            }

        known: dict[str, str] = self._accounts.list_for_company(company_id)

        # Accounts needing Haiku mapping — list-of-dicts per new prompt schema.
        unknown_accounts = [
            info for name, info in account_info.items() if name not in known
        ]

        high_conf: list[MappingOutput] = []
        low_conf: list[MappingOutput] = []

        if unknown_accounts:
            context = {
                "accounts": unknown_accounts,
                "known_mappings": known,
            }
            try:
                response: MappingResponse = self._llm.call(
                    prompt="mapping_prompt.txt",
                    model=MAPPING_MODEL,
                    context=context,
                    schema=MappingResponse,
                )
            except TransientIOError:
                raise MappingAmbiguous("LLM call failed during account mapping")

            for m in response.mappings:
                if m.confidence >= _HIGH_CONFIDENCE_THRESHOLD:
                    high_conf.append(m)
                else:
                    low_conf.append(m)

            # Single bulk call — 3 round-trips total regardless of batch size.
            # Previous per-row upsert loop saturated Supabase's HTTP/2
            # connection on 20+ accounts and caused RemoteProtocolError on
            # shared-stream tenants.
            if high_conf:
                self._accounts.bulk_upsert_mappings(company_id, high_conf)

            if low_conf:
                self._runs.set_low_confidence_columns(run_id, low_conf)

        mapped_columns: dict[str, dict] = {}

        for account_name, category in known.items():
            if account_name in account_info:
                mapped_columns[account_name] = {"category": category, "confidence": 1.0}

        for m in high_conf:
            mapped_columns[m.column] = {
                "category": m.category,
                "confidence": m.confidence,
            }

        for m in low_conf:
            mapped_columns[m.column] = {
                "category": "OTHER",
                "confidence": m.confidence,
            }

        for account_name in account_info:
            if account_name not in mapped_columns:
                mapped_columns[account_name] = {"category": "OTHER", "confidence": 0.0}

        return mapped_columns, low_conf

    # ------------------------------------------------------------------ #
    # Multi-file helper (no state transitions)                          #
    # ------------------------------------------------------------------ #

    def parse_file_silently(
        self,
        storage_key: str,
        company_id: str,
        period: date,
        run_id: str,
        account_name_map: dict[str, str] | None = None,
    ) -> tuple[list[dict], str, pd.DataFrame]:
        """Download, discover, normalize, validate, map — without state transitions.

        Returns (preview_rows, source_column, df_detailed) where:
          - preview_rows: [{account, category, amount}] aggregated per account
          - source_column: verbatim header mapped to "amount" for provenance
          - df_detailed: per-row validated DataFrame with [account, category, amount, date]
            used by hint_computer.py for period-boundary and cross-account checks.

        Low-confidence Discovery plans are auto-approved — user reviews the
        consolidated output, not per-file plans.
        """
        sample = self._read_sample(storage_key)
        sample = pii_sanitizer.sanitize_sample(sample, run_id=run_id)

        try:
            plan = self._discovery.discover(run_id, sample)
        except DiscoveryLowConfidence as exc:
            plan = exc.plan  # auto-approve: user reviews consolidated result
        except (DiscoveryFailed, Exception):
            raise

        df_raw = self._read_full(storage_key)
        try:
            df_raw = pii_sanitizer.sanitize(df_raw, run_id=run_id)
        except FileHasNoValidColumns:
            raise

        df_normalized, _ = normalizer.apply_plan(df_raw, plan, period)
        df_validated = validator.validate(df_normalized)

        # Apply AccountMapper decisions before category mapping and groupby (B2 fix).
        # Must run here so GL account names are in place before _map_accounts aggregates.
        if account_name_map:
            df_validated["account"] = df_validated["account"].map(
                lambda x: account_name_map.get(str(x).strip(), x)
            )

        source_column = self._extract_source_column(plan)

        mapped_columns, _ = self._map_accounts(run_id, company_id, df_validated)

        account_totals: dict[str, float] = (
            df_validated.groupby("account")["amount"].sum().to_dict()
        )
        preview_rows = [
            {
                "account": name,
                "amount": float(account_totals[name]),
                "category": mapped_columns.get(name, {}).get("category", "OTHER"),
            }
            for name in sorted(account_totals.keys())
        ]

        # Add category column to detailed DataFrame for hint_computer.
        df_detailed = df_validated.copy()
        df_detailed["category"] = df_detailed["account"].map(
            lambda a: mapped_columns.get(str(a), {}).get("category", "OTHER")
        )

        return preview_rows, source_column, df_detailed

    # ------------------------------------------------------------------ #
    # Failure helper                                                     #
    # ------------------------------------------------------------------ #

    def _fail(
        self,
        run_id: str,
        current_status: RunStatus,
        error_message: str,
    ) -> None:
        """Transition to parsing_failed, swallowing any errors from the update itself."""
        try:
            failed_status = RunStateMachine.transition(
                current_status, RunStatus.PARSING_FAILED
            )
            self._runs.update_status(
                run_id,
                failed_status,
                extra={"error_message": error_message},
            )
        except Exception as inner:
            logger.error(
                "failed to update run to parsing_failed",
                extra={"run_id": run_id, "inner_error": str(inner)},
            )
