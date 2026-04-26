from __future__ import annotations

import time
from datetime import date, datetime

# Module-level accounts cache: {company_id: (result_dict, fetched_at_epoch)}
# Avoids N identical Supabase round-trips when parsing N files in a single run.
# Invalidated on any write (upsert/bulk_upsert). TTL = 120 s as a safety net.
_accounts_cache: dict[str, tuple[dict[str, str], float]] = {}
_ACCOUNTS_CACHE_TTL = 120.0
from decimal import Decimal
from typing import Callable, TypeVar

from supabase import Client

from backend.domain.contracts import MappingOutput
from backend.domain.entities import Anomaly, MonthlyEntry, Report
from backend.domain.errors import (
    DuplicateEntryError,
    RLSForbiddenError,
    TransientIOError,
)
from backend.domain.run_state_machine import RunStatus
from backend.logger import get_logger

logger = get_logger(__name__)

T = TypeVar("T")

# Connection-class failure markers — httpx / httpcore raise these when the
# TCP stream is dropped mid-request, which happens on Supabase's edge when
# a single HTTP/2 connection is thrashed by rapid sequential calls.
_RETRYABLE_MARKERS = (
    "remote protocol error",
    "server disconnected",
    "connection refused",
    "connection reset",
    "read timeout",
    "connect timeout",
)


def _is_retryable(exc: Exception) -> bool:
    msg = str(exc).lower()
    return any(m in msg for m in _RETRYABLE_MARKERS)


def _with_retry(
    thunk: Callable[[], T],
    max_attempts: int = 2,
    base_delay: float = 0.5,
) -> T:
    """Execute *thunk* with at most one retry on connection-class failures.

    Per CLAUDE.md §Retry: "Fail-fast with at most one retry, and only on
    connection-class errors". Non-retryable errors (unique violations,
    RLS denials, 4xx) propagate unchanged after the first attempt.

    `thunk` rebuilds its query each time rather than reusing a query
    builder, because PostgREST builders are stateful.
    """
    last_exc: Exception | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            return thunk()
        except Exception as exc:
            last_exc = exc
            if not _is_retryable(exc):
                raise
            if attempt >= max_attempts:
                raise
            logger.info(
                "supabase_retry",
                extra={
                    "event": "supabase_retry",
                    "attempt": attempt,
                    "error": str(exc)[:200],
                },
            )
            time.sleep(base_delay * attempt)
    assert last_exc is not None
    raise last_exc


def _pg_error_code(exc: Exception) -> str | None:
    msg = str(exc)
    if "23505" in msg:
        return "23505"  # unique_violation
    if "42501" in msg or "new row violates" in msg or "permission denied" in msg:
        return "42501"  # insufficient_privilege / RLS
    return None


def _wrap_db(exc: Exception) -> Exception:
    code = _pg_error_code(exc)
    if code == "23505":
        return DuplicateEntryError(str(exc))
    if code == "42501":
        return RLSForbiddenError(str(exc))
    return TransientIOError(str(exc))


# ---------------------------------------------------------------------------
# Entries
# ---------------------------------------------------------------------------


class SupabaseEntriesRepo:
    def __init__(self, client: Client) -> None:
        self._db = client

    def list_history(
        self,
        company_id: str,
        period: date,
        lookback_months: int = 6,
    ) -> list[MonthlyEntry]:
        # Fast existence check before fetching up to 600 rows.
        # On first runs (no history) this saves one heavy SELECT.
        try:
            exists_resp = (
                self._db.table("monthly_entries")
                .select("id")
                .eq("company_id", company_id)
                .lt("period", str(period))
                .limit(1)
                .execute()
            )
        except Exception as exc:
            raise _wrap_db(exc) from exc

        if not exists_resp.data:
            return []

        try:
            resp = (
                self._db.table("monthly_entries")
                .select("*")
                .eq("company_id", company_id)
                .lt("period", str(period))
                .order("period", desc=True)
                .limit(lookback_months * 100)
                .execute()
            )
        except Exception as exc:
            raise _wrap_db(exc) from exc

        return [_row_to_entry(r) for r in (resp.data or [])]

    def list_for_period(self, company_id: str, period: date) -> list[MonthlyEntry]:
        try:
            resp = (
                self._db.table("monthly_entries")
                .select("*")
                .eq("company_id", company_id)
                .eq("period", str(period))
                .execute()
            )
        except Exception as exc:
            raise _wrap_db(exc) from exc

        return [_row_to_entry(r) for r in (resp.data or [])]

    def list_for_year(
        self, company_id: str, start_date: date, end_date: date
    ) -> list[MonthlyEntry]:
        """Fetch all entries for a company within a date range (year)."""
        try:
            resp = (
                self._db.table("monthly_entries")
                .select("*")
                .eq("company_id", company_id)
                .gte("period", str(start_date))
                .lte("period", str(end_date))
                .order("period", desc=True)
                .order("created_at", desc=True)
                .execute()
            )
        except Exception as exc:
            raise _wrap_db(exc) from exc

        return [_row_to_entry(r) for r in (resp.data or [])]

    def count_distinct_periods(self, company_id: str) -> int:
        try:
            resp = (
                self._db.table("monthly_entries")
                .select("period")
                .eq("company_id", company_id)
                .execute()
            )
        except Exception as exc:
            raise _wrap_db(exc) from exc
        periods = {r["period"] for r in (resp.data or []) if r.get("period")}
        return len(periods)

    def replace_period(
        self,
        company_id: str,
        period: date,
        entries: list[MonthlyEntry],
    ) -> None:
        try:
            self._db.table("monthly_entries").delete().eq("company_id", company_id).eq(
                "period", str(period)
            ).execute()

            if entries:
                rows = [_entry_to_row(e) for e in entries]
                self._db.table("monthly_entries").insert(rows).execute()
        except DuplicateEntryError:
            raise
        except Exception as exc:
            raise _wrap_db(exc) from exc


# ---------------------------------------------------------------------------
# Anomalies
# ---------------------------------------------------------------------------


class SupabaseAnomaliesRepo:
    def __init__(self, client: Client) -> None:
        self._db = client

    def list_for_period(self, company_id: str, period: date) -> list[Anomaly]:
        try:
            resp = (
                self._db.table("anomalies")
                .select("*")
                .eq("company_id", company_id)
                .eq("period", str(period))
                .execute()
            )
        except Exception as exc:
            raise _wrap_db(exc) from exc
        return [_row_to_anomaly(r) for r in (resp.data or [])]

    def write_many(self, anomalies: list[Anomaly]) -> None:
        if not anomalies:
            return
        try:
            rows = [_anomaly_to_row(a) for a in anomalies]
            self._db.table("anomalies").insert(rows).execute()
        except Exception as exc:
            raise _wrap_db(exc) from exc


# ---------------------------------------------------------------------------
# Reports
# ---------------------------------------------------------------------------


class SupabaseReportsRepo:
    def __init__(self, client: Client) -> None:
        self._db = client

    def get(self, company_id: str, period: date) -> Report | None:
        try:
            resp = (
                self._db.table("reports")
                .select("*")
                .eq("company_id", company_id)
                .eq("period", str(period))
                .limit(1)
                .execute()
            )
        except Exception as exc:
            raise _wrap_db(exc) from exc
        if not resp.data:
            return None
        return _row_to_report(resp.data[0])

    def write(self, report: Report) -> Report:
        try:
            row = _report_to_row(report)
            resp = self._db.table("reports").insert(row).execute()
        except Exception as exc:
            raise _wrap_db(exc) from exc
        return _row_to_report(resp.data[0])

    def upgrade_summary(self, company_id: str, period: date, new_summary: str) -> None:
        """Atomically overwrite summary and set opus_upgraded=TRUE."""
        try:
            _with_retry(
                lambda: self._db.table("reports")
                .update({"summary": new_summary, "opus_upgraded": True})
                .eq("company_id", company_id)
                .eq("period", str(period))
                .execute()
            )
        except Exception as exc:
            raise _wrap_db(exc) from exc

    def mark_mail_sent(self, report_id: str) -> None:
        try:
            self._db.table("reports").update(
                {"mail_sent": True, "mail_sent_at": datetime.utcnow().isoformat()}
            ).eq("id", report_id).execute()
        except Exception as exc:
            raise _wrap_db(exc) from exc

    def list_all(self, company_id: str, limit: int = 12) -> list[Report]:
        try:
            resp = (
                self._db.table("reports")
                .select("*")
                .eq("company_id", company_id)
                .order("period", desc=True)
                .limit(limit)
                .execute()
            )
        except Exception as exc:
            raise _wrap_db(exc) from exc
        return [_row_to_report(r) for r in (resp.data or [])]


# ---------------------------------------------------------------------------
# Runs
# ---------------------------------------------------------------------------


class SupabaseRunsRepo:
    def __init__(self, client: Client) -> None:
        self._db = client

    def get_by_id(self, run_id: str) -> dict:
        try:
            resp = (
                self._db.table("runs").select("*").eq("id", run_id).limit(1).execute()
            )
        except Exception as exc:
            raise _wrap_db(exc) from exc
        if not resp.data:
            raise RLSForbiddenError(f"Run {run_id} not found or not accessible")
        return resp.data[0]

    def create(self, company_id: str, period: date, file_count: int = 1) -> dict:
        try:
            resp = (
                self._db.table("runs")
                .insert(
                    {
                        "company_id": company_id,
                        "period": str(period),
                        "status": "pending",
                        "step": 0,
                        "total_steps": 4,
                        "progress_pct": 0,
                        "file_count": file_count,
                    }
                )
                .execute()
            )
        except Exception as exc:
            raise _wrap_db(exc) from exc
        return resp.data[0]

    def set_file_count(self, run_id: str, file_count: int) -> None:
        body = {
            "file_count": file_count,
            "updated_at": datetime.utcnow().isoformat(),
        }
        try:
            _with_retry(
                lambda: self._db.table("runs").update(body).eq("id", run_id).execute()
            )
        except Exception as exc:
            raise _wrap_db(exc) from exc

    def update_status(
        self,
        run_id: str,
        status: RunStatus,
        extra: dict | None = None,
    ) -> None:
        patch: dict = {
            "status": status.value,
            "updated_at": datetime.utcnow().isoformat(),
        }
        if extra:
            patch.update(extra)
        try:
            _with_retry(
                lambda: self._db.table("runs").update(patch).eq("id", run_id).execute()
            )
        except Exception as exc:
            raise _wrap_db(exc) from exc

    def set_low_confidence_columns(
        self,
        run_id: str,
        columns: list[MappingOutput],
    ) -> None:
        payload = [c.model_dump() for c in columns]
        body = {
            "low_confidence_columns": payload,
            "updated_at": datetime.utcnow().isoformat(),
        }
        try:
            _with_retry(
                lambda: self._db.table("runs").update(body).eq("id", run_id).execute()
            )
        except Exception as exc:
            raise _wrap_db(exc) from exc

    def set_pandas_summary(self, run_id: str, summary: dict) -> None:
        body = {
            "pandas_summary": summary,
            "updated_at": datetime.utcnow().isoformat(),
        }
        try:
            _with_retry(
                lambda: self._db.table("runs").update(body).eq("id", run_id).execute()
            )
        except Exception as exc:
            raise _wrap_db(exc) from exc

    def set_opus_status(self, run_id: str, status: str) -> None:
        body = {"opus_status": status, "updated_at": datetime.utcnow().isoformat()}
        try:
            _with_retry(
                lambda: self._db.table("runs").update(body).eq("id", run_id).execute()
            )
        except Exception as exc:
            raise _wrap_db(exc) from exc

    def get_latest_run_id_for_period(self, company_id: str, period: date) -> str | None:
        """Return the id of the most recently created run for (company_id, period)."""
        try:
            resp = (
                self._db.table("runs")
                .select("id")
                .eq("company_id", company_id)
                .eq("period", str(period))
                .order("created_at", desc=True)
                .limit(1)
                .execute()
            )
        except Exception as exc:
            raise _wrap_db(exc) from exc
        return resp.data[0]["id"] if resp.data else None

    def get_prior_pandas_summaries(
        self, company_id: str, before_period: date, limit: int = 3
    ) -> list[dict]:
        """Return pandas_summary JSONB for the N most recent completed runs before the given period."""
        try:
            resp = (
                self._db.table("runs")
                .select("period, pandas_summary")
                .eq("company_id", company_id)
                .eq("status", "complete")
                .lt("period", str(before_period))
                .not_.is_("pandas_summary", "null")
                .order("period", desc=True)
                .limit(limit)
                .execute()
            )
        except Exception as exc:
            raise _wrap_db(exc) from exc
        return resp.data or []

    def set_storage_key(self, run_id: str, storage_key: str) -> None:
        body = {
            "storage_key": storage_key,
            "updated_at": datetime.utcnow().isoformat(),
        }
        try:
            _with_retry(
                lambda: self._db.table("runs").update(body).eq("id", run_id).execute()
            )
        except Exception as exc:
            raise _wrap_db(exc) from exc

    def set_parse_preview(self, run_id: str, preview: dict) -> None:
        body = {
            "parse_preview": preview,
            "updated_at": datetime.utcnow().isoformat(),
        }
        try:
            _with_retry(
                lambda: self._db.table("runs").update(body).eq("id", run_id).execute()
            )
        except Exception as exc:
            raise _wrap_db(exc) from exc

    def set_discovery_plan(
        self,
        run_id: str,
        plan: dict,
        approval_mode: str | None = None,
    ) -> None:
        """Persist plan JSONB; write approval_mode only when provided.

        Leaving approval_mode untouched on the DISCOVERING-time first write
        keeps the 'still awaiting user review' signal intact — the column
        stays NULL until auto-advance sets 'auto' or confirm-discovery
        route sets 'manual'.
        """
        payload: dict = {
            "discovery_plan": plan,
            "updated_at": datetime.utcnow().isoformat(),
        }
        if approval_mode is not None:
            payload["discovery_approval_mode"] = approval_mode
        try:
            _with_retry(
                lambda: self._db.table("runs")
                .update(payload)
                .eq("id", run_id)
                .execute()
            )
        except Exception as exc:
            raise _wrap_db(exc) from exc


# ---------------------------------------------------------------------------
# Companies
# ---------------------------------------------------------------------------


class SupabaseCompaniesRepo:
    def __init__(self, client: Client) -> None:
        self._db = client

    def get_by_owner(self, user_id: str) -> dict:
        try:
            resp = (
                self._db.table("companies")
                .select("*")
                .eq("owner_id", user_id)
                .limit(1)
                .execute()
            )
        except Exception as exc:
            raise _wrap_db(exc) from exc
        if not resp.data:
            raise RLSForbiddenError(f"No company found for user {user_id}")
        return resp.data[0]

    def create(
        self,
        owner_id: str,
        name: str,
        sector: str | None,
        currency: str,
    ) -> dict:
        try:
            resp = (
                self._db.table("companies")
                .insert(
                    {
                        "owner_id": owner_id,
                        "name": name,
                        "sector": sector,
                        "currency": currency,
                    }
                )
                .execute()
            )
        except Exception as exc:
            raise _wrap_db(exc) from exc
        return resp.data[0]


# ---------------------------------------------------------------------------
# Accounts
# ---------------------------------------------------------------------------


class SupabaseAccountsRepo:
    def __init__(self, client: Client) -> None:
        self._db = client

    def list_for_company(self, company_id: str) -> dict[str, str]:
        cached = _accounts_cache.get(company_id)
        if cached and (time.time() - cached[1]) < _ACCOUNTS_CACHE_TTL:
            return cached[0]
        try:
            resp = (
                self._db.table("accounts")
                .select("name, account_categories(name)")
                .eq("company_id", company_id)
                .eq("is_active", True)
                .execute()
            )
        except Exception as exc:
            raise _wrap_db(exc) from exc
        result: dict[str, str] = {}
        for row in resp.data or []:
            cat = row.get("account_categories") or {}
            result[row["name"]] = cat.get("name", "OTHER")
        _accounts_cache[company_id] = (result, time.time())
        return result

    def upsert_mapping(self, company_id: str, column: str, category: str) -> None:
        """Check if account exists; update category if so, create if not."""
        _accounts_cache.pop(company_id, None)
        try:
            # Check existence first
            exist_resp = (
                self._db.table("accounts")
                .select("id")
                .eq("company_id", company_id)
                .eq("name", column)
                .limit(1)
                .execute()
            )
            # Resolve category_id
            cat_resp = (
                self._db.table("account_categories")
                .select("id")
                .eq("name", category)
                .limit(1)
                .execute()
            )
            if not cat_resp.data:
                # Fallback to OTHER
                cat_resp = (
                    self._db.table("account_categories")
                    .select("id")
                    .eq("name", "OTHER")
                    .limit(1)
                    .execute()
                )
            if not cat_resp.data:
                logger.warning(
                    "unknown category for upsert and OTHER not found",
                    extra={"category": category},
                )
                return
            category_id = cat_resp.data[0]["id"]

            if exist_resp.data:
                # Update existing row's category
                self._db.table("accounts").update({"category_id": category_id}).eq(
                    "id", exist_resp.data[0]["id"]
                ).execute()
            else:
                # Insert new row
                self._db.table("accounts").insert(
                    {
                        "company_id": company_id,
                        "name": column,
                        "category_id": category_id,
                        "created_by": "user",
                    }
                ).execute()
        except Exception as exc:
            raise _wrap_db(exc) from exc

    def bulk_upsert_mappings(
        self,
        company_id: str,
        mappings: list[MappingOutput],
    ) -> None:
        """Insert new mappings in a single batch; leave existing accounts alone.

        Three round-trips regardless of batch size:
          1. SELECT category_id by name  (one query, covers all mappings)
          2. SELECT existing account names  (one query with .in_)
          3. INSERT new rows  (one batched insert)

        Replaces the previous per-mapping upsert_mapping loop at
        parser.py:_map_accounts which did 3*N round-trips and saturated
        Supabase's HTTP/2 connection on P&L files with 20+ accounts.

        Existing accounts are NOT re-categorised — their stored category is
        advisory for the account table; the authoritative mapping for the
        current run already lives in parse_preview['rows'] and gets written
        to monthly_entries via /runs/{id}/confirm.
        """
        if not mappings:
            return

        _accounts_cache.pop(company_id, None)
        try:
            # 1. Category name → id map (cached per call, not per row).
            cat_resp = _with_retry(
                lambda: self._db.table("account_categories")
                .select("id, name")
                .execute()
            )
            cat_id_by_name: dict[str, int] = {
                r["name"]: r["id"] for r in (cat_resp.data or [])
            }
            other_id = cat_id_by_name.get("OTHER")

            # 2. Which of these account names already exist for this company?
            names = [m.column for m in mappings]
            existing_resp = _with_retry(
                lambda: self._db.table("accounts")
                .select("id, name")
                .eq("company_id", company_id)
                .in_("name", names)
                .execute()
            )
            existing_names: set[str] = {r["name"] for r in (existing_resp.data or [])}

            # 3. Build INSERT rows for new accounts only.
            rows: list[dict] = []
            skipped_unknown_cat = 0
            for m in mappings:
                if m.column in existing_names:
                    continue
                cid = cat_id_by_name.get(m.category) or other_id
                if cid is None:
                    skipped_unknown_cat += 1
                    continue
                rows.append(
                    {
                        "company_id": company_id,
                        "name": m.column,
                        "category_id": cid,
                        "created_by": "user",
                    }
                )

            if skipped_unknown_cat:
                logger.warning(
                    "bulk_upsert_mappings skipped rows with unknown category",
                    extra={"count": skipped_unknown_cat},
                )

            if rows:
                _with_retry(lambda: self._db.table("accounts").insert(rows).execute())
                logger.info(
                    "bulk_upsert_mappings complete",
                    extra={
                        "event": "bulk_upsert_mappings",
                        "inserted": len(rows),
                        "already_existed": len(existing_names),
                        "total_requested": len(mappings),
                    },
                )
        except (TransientIOError, DuplicateEntryError, RLSForbiddenError):
            raise
        except Exception as exc:
            raise _wrap_db(exc) from exc

    def get_or_create(self, company_id: str, name: str, category: str) -> str:
        """Return account UUID, creating the row if it does not exist."""
        try:
            # 1. Check if account already exists
            exist_resp = (
                self._db.table("accounts")
                .select("id")
                .eq("company_id", company_id)
                .eq("name", name)
                .limit(1)
                .execute()
            )
            if exist_resp.data:
                return exist_resp.data[0]["id"]

            # 2. Resolve category_id
            cat_resp = (
                self._db.table("account_categories")
                .select("id")
                .eq("name", category)
                .limit(1)
                .execute()
            )
            if not cat_resp.data:
                # Fallback to OTHER
                cat_resp = (
                    self._db.table("account_categories")
                    .select("id")
                    .eq("name", "OTHER")
                    .limit(1)
                    .execute()
                )
            if not cat_resp.data:
                raise TransientIOError(
                    f"account_categories table missing both '{category}' and 'OTHER'"
                )
            category_id = cat_resp.data[0]["id"]

            # 3. Insert new account
            insert_resp = (
                self._db.table("accounts")
                .insert(
                    {
                        "company_id": company_id,
                        "name": name,
                        "category_id": category_id,
                        "created_by": "agent",
                    }
                )
                .execute()
            )
            return insert_resp.data[0]["id"]
        except (TransientIOError, DuplicateEntryError, RLSForbiddenError):
            raise
        except Exception as exc:
            raise _wrap_db(exc) from exc

    def batch_get_or_create(
        self,
        company_id: str,
        items: list[tuple[str, str]],
    ) -> dict[str, str]:
        """Resolve N (account_name, category) pairs in 3 round-trips.

        Round-trip 1: SELECT all account_categories (id, name)
        Round-trip 2: SELECT existing accounts WHERE name IN (...)
        Round-trip 3: INSERT new accounts only (skipped when all exist)
        Returns {account_name: account_id} for every item.
        """
        if not items:
            return {}

        try:
            # 1. Category name → id (covers all items in one query)
            cat_resp = _with_retry(
                lambda: self._db.table("account_categories")
                .select("id, name")
                .execute()
            )
            cat_id_by_name: dict[str, str] = {
                r["name"]: r["id"] for r in (cat_resp.data or [])
            }
            other_id = cat_id_by_name.get("OTHER")

            # 2. Which accounts already exist for this company?
            names = [name for name, _ in items]
            existing_resp = _with_retry(
                lambda: self._db.table("accounts")
                .select("id, name")
                .eq("company_id", company_id)
                .in_("name", names)
                .execute()
            )
            result: dict[str, str] = {
                r["name"]: r["id"] for r in (existing_resp.data or [])
            }

            # 3. Insert only the missing ones
            new_rows: list[dict] = []
            for name, category in items:
                if name in result:
                    continue
                cid = cat_id_by_name.get(category) or other_id
                if cid is None:
                    raise TransientIOError(
                        f"account_categories missing '{category}' and 'OTHER'"
                    )
                new_rows.append(
                    {
                        "company_id": company_id,
                        "name": name,
                        "category_id": cid,
                        "created_by": "agent",
                    }
                )

            if new_rows:
                ins_resp = _with_retry(
                    lambda: self._db.table("accounts").insert(new_rows).execute()
                )
                for r in ins_resp.data or []:
                    result[r["name"]] = r["id"]

            return result
        except (TransientIOError, DuplicateEntryError, RLSForbiddenError):
            raise
        except Exception as exc:
            raise _wrap_db(exc) from exc

    def get_accounts_by_id(self, company_id: str) -> dict[str, dict]:
        """Return {account_id: {"name": str, "category": str}} for all active accounts."""
        try:
            resp = (
                self._db.table("accounts")
                .select("id, name, account_categories(name)")
                .eq("company_id", company_id)
                .eq("is_active", True)
                .execute()
            )
        except Exception as exc:
            raise _wrap_db(exc) from exc

        result: dict[str, dict] = {}
        for row in resp.data or []:
            cat = row.get("account_categories") or {}
            result[row["id"]] = {
                "name": row["name"],
                "category": cat.get("name", "OTHER"),
            }
        return result


# ---------------------------------------------------------------------------
# Row converters (private)
# ---------------------------------------------------------------------------


def _row_to_entry(r: dict) -> MonthlyEntry:
    return MonthlyEntry(
        id=r["id"],
        company_id=r["company_id"],
        account_id=r["account_id"],
        period=(
            date.fromisoformat(r["period"])
            if isinstance(r["period"], str)
            else r["period"]
        ),
        actual_amount=Decimal(str(r["actual_amount"])),
        source_file=r.get("source_file"),
        source_column=r.get("source_column"),
        agent_notes=r.get("agent_notes"),
        source_breakdown=r.get("source_breakdown"),
        created_at=r.get("created_at"),
    )


def _entry_to_row(e: MonthlyEntry) -> dict:
    return {
        "id": e.id,
        "company_id": e.company_id,
        "account_id": e.account_id,
        "period": str(e.period),
        "actual_amount": str(e.actual_amount),
        "source_file": e.source_file,
        "source_column": e.source_column,
        "agent_notes": e.agent_notes,
        "source_breakdown": e.source_breakdown,
    }


def _row_to_anomaly(r: dict) -> Anomaly:
    return Anomaly(
        id=r["id"],
        company_id=r["company_id"],
        account_id=r["account_id"],
        period=(
            date.fromisoformat(r["period"])
            if isinstance(r["period"], str)
            else r["period"]
        ),
        anomaly_type=r["anomaly_type"],
        severity=r["severity"],
        description=r["description"],
        variance_pct=(
            Decimal(str(r["variance_pct"]))
            if r.get("variance_pct") is not None
            else None
        ),
        status=r.get("status", "open"),
        created_at=r.get("created_at"),
    )


def _anomaly_to_row(a: Anomaly) -> dict:
    return {
        "id": a.id,
        "company_id": a.company_id,
        "account_id": a.account_id,
        "period": str(a.period),
        "anomaly_type": a.anomaly_type,
        "severity": a.severity,
        "description": a.description,
        "variance_pct": str(a.variance_pct) if a.variance_pct is not None else None,
        "status": a.status,
    }


def _row_to_report(r: dict) -> Report:
    return Report(
        id=r["id"],
        company_id=r["company_id"],
        period=(
            date.fromisoformat(r["period"])
            if isinstance(r["period"], str)
            else r["period"]
        ),
        summary=r["summary"],
        anomaly_count=r.get("anomaly_count", 0),
        error_count=r.get("error_count", 0),
        mail_sent=r.get("mail_sent", False),
        mail_sent_at=r.get("mail_sent_at"),
        reconciliations=r.get("reconciliations"),
        opus_upgraded=r.get("opus_upgraded", False) or False,
        created_at=r.get("created_at"),
    )


def _report_to_row(r: Report) -> dict:
    row: dict = {
        "id": r.id,
        "company_id": r.company_id,
        "period": str(r.period),
        "summary": r.summary,
        "anomaly_count": r.anomaly_count,
        "error_count": r.error_count,
    }
    if r.reconciliations is not None:
        row["reconciliations"] = r.reconciliations
    return row
