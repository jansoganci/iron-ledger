from __future__ import annotations

from datetime import date
from typing import Protocol, runtime_checkable

from pydantic import BaseModel

from backend.domain.contracts import MappingOutput, SendResult
from backend.domain.entities import Anomaly, MonthlyEntry, Report
from backend.domain.run_state_machine import RunStatus


@runtime_checkable
class LLMClient(Protocol):
    def call(
        self,
        prompt: str,
        model: str,
        context: dict,
        schema: type[BaseModel],
    ) -> BaseModel: ...

    # `prompt` is a filename relative to backend/prompts/
    # Returns a validated instance of `schema`
    # Raises TransientIOError after network retries exhausted


@runtime_checkable
class FileStorage(Protocol):
    def upload(
        self,
        user_id: str,
        period: str,
        filename: str,
        data: bytes,
    ) -> str: ...

    # Returns the storage_key: financial-uploads/{user_id}/{period}/{filename}
    # Raises TransientIOError after 3 retries (0.5s/1.5s/4s + jitter)

    def download(self, storage_key: str) -> bytes: ...

    def delete(self, storage_key: str) -> None: ...


@runtime_checkable
class EmailSender(Protocol):
    def send(self, to: str, subject: str, html: str, text: str) -> SendResult: ...


@runtime_checkable
class EntriesRepo(Protocol):
    def list_history(
        self,
        company_id: str,
        period: date,
        lookback_months: int = 6,
    ) -> list[MonthlyEntry]: ...

    def list_for_period(self, company_id: str, period: date) -> list[MonthlyEntry]: ...

    def replace_period(
        self,
        company_id: str,
        period: date,
        entries: list[MonthlyEntry],
    ) -> None: ...

    # Atomic DELETE-then-INSERT.
    # Raises DuplicateEntryError on unique-constraint violation (never retried).

    def count_distinct_periods(self, company_id: str) -> int: ...

    # Used by GET /companies/me/has-history to decide whether to render EmptyState.
    # Returns 0 when no rows exist for the company.


@runtime_checkable
class AnomaliesRepo(Protocol):
    def list_for_period(self, company_id: str, period: date) -> list[Anomaly]: ...

    def write_many(self, anomalies: list[Anomaly]) -> None: ...


@runtime_checkable
class ReportsRepo(Protocol):
    def get(self, company_id: str, period: date) -> Report | None: ...

    def write(self, report: Report) -> Report: ...

    def mark_mail_sent(self, report_id: str) -> None: ...

    def list_all(self, company_id: str, limit: int = 12) -> list[Report]: ...

    # Powers GET /reports and the Dashboard HistoryList.
    # Ordered by period DESC. `limit` is capped at 50 by the route.


@runtime_checkable
class RunsRepo(Protocol):
    def get_by_id(self, run_id: str) -> dict: ...

    def create(self, company_id: str, period: date) -> dict: ...

    def update_status(
        self,
        run_id: str,
        status: RunStatus,
        extra: dict | None = None,
    ) -> None: ...

    # `extra` may contain: step, step_label, progress_pct, error_message,
    # report_id, raw_data_url. Absent keys are not modified.

    def set_low_confidence_columns(
        self,
        run_id: str,
        columns: list[MappingOutput],
    ) -> None: ...

    def set_pandas_summary(self, run_id: str, summary: dict) -> None: ...

    def set_storage_key(self, run_id: str, storage_key: str) -> None: ...

    def set_parse_preview(self, run_id: str, preview: dict) -> None: ...

    # Populated by POST /upload after the file lands in Storage.
    # Read by POST /runs/{run_id}/retry to re-run the pipeline against
    # the existing file (no re-upload required).

    def set_discovery_plan(
        self,
        run_id: str,
        plan: dict,
        approval_mode: str | None = None,
    ) -> None: ...

    # `plan` is DiscoveryPlan.model_dump() — may carry an extra `_preview`
    # key (DB-only, stripped by Pydantic on read). `approval_mode` is one of
    # "auto" | "manual" | None. When None, the approval_mode column is left
    # untouched (plan is still pending user review).


@runtime_checkable
class CompaniesRepo(Protocol):
    def get_by_owner(self, user_id: str) -> dict: ...

    # Returns the single company owned by this user.
    # Raises RLSForbiddenError if no row matches.

    def create(
        self,
        owner_id: str,
        name: str,
        sector: str | None,
        currency: str,
    ) -> dict: ...

    # Inserts a new company row and returns the full dict.
    # Raises DuplicateEntryError on unique-constraint violation.


@runtime_checkable
class AccountsRepo(Protocol):
    def list_for_company(self, company_id: str) -> dict[str, str]: ...

    # Returns {column_header: category_name} map for auto-mapping next upload.

    def upsert_mapping(self, company_id: str, column: str, category: str) -> None: ...

    def bulk_upsert_mappings(
        self,
        company_id: str,
        mappings: list[MappingOutput],
    ) -> None: ...

    # Collapses ~3N round-trips down to 3 total: one to fetch category IDs,
    # one to fetch existing account names, one to batch-INSERT the new ones.
    # Existing accounts are left alone (first-write-wins — their stored
    # category_id is advisory, not authoritative for the current run).

    def get_or_create(self, company_id: str, name: str, category: str) -> str: ...

    # Returns the account UUID. Creates if not exists with correct category_id.

    def batch_get_or_create(
        self,
        company_id: str,
        items: list[tuple[str, str]],
    ) -> dict[str, str]: ...

    # items: [(account_name, category), ...]
    # Returns {account_name: account_id} for every item.
    # 3 round-trips regardless of len(items).

    def get_accounts_by_id(self, company_id: str) -> dict[str, dict]: ...

    # Returns {account_id: {"name": str, "category": str}}
    # Used by comparison agent to join account info onto monthly_entries rows.
