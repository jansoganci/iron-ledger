import asyncio
import uuid
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import List
from uuid import UUID

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Body,
    Depends,
    File,
    Form,
    HTTPException,
    Request,
    Response,
)
from fastapi.responses import JSONResponse
from fastapi import UploadFile
from pydantic import BaseModel, EmailStr

from backend import messages
from backend.agents.opus_upgrade import run_opus_upgrade
from backend.agents.orchestrator import (
    apply_mapping_and_consolidate,
    run_comparison_and_report,
    run_multi_file_parser_until_preview,
    run_multi_file_parser_with_mapping,
    run_parser_after_discovery_approval,
    run_parser_until_preview,
)
from backend.api.auth import get_cached_company, get_company_id, get_current_user
from backend.api.deps import (
    get_account_mapper,
    get_accounts_repo,
    get_anomalies_repo,
    get_companies_repo,
    get_entries_repo,
    get_file_storage,
    get_reports_repo,
    get_runs_repo,
)
from backend.api.rate_limit import limiter
from backend.domain.contracts import DiscoveryPlan
from backend.domain.entities import MonthlyEntry
from backend.domain.errors import (
    DuplicateEntryError,
    RLSForbiddenError,
    TransientIOError,
)
from backend.domain.run_state_machine import RunStateMachine, RunStatus
from backend.logger import get_logger
from backend.tools.file_reader import SUPPORTED_EXTENSIONS

# Categories accepted by POST /runs/{run_id}/mapping/confirm.
# "SKIP" is a frontend-only sentinel — never written to the database.
VALID_CATEGORIES = {
    "REVENUE",
    "COGS",
    "OPEX",
    "G&A",
    "R&D",
    "OTHER_INCOME",
    "OTHER",
}

logger = get_logger(__name__)
router = APIRouter()

# In-memory progress tracking for quarterly reports (MVP — Redis post-MVP)
_quarterly_jobs: dict[str, dict] = {}


# ------------------------------------------------------------------ #
# Request / response models                                            #
# ------------------------------------------------------------------ #


class MailSendRequest(BaseModel):
    report_id: UUID
    to_email: str


class MappingConfirmItem(BaseModel):
    column: str
    category: str


class MappingConfirmRequest(BaseModel):
    mappings: list[MappingConfirmItem]


class ConfirmOverride(BaseModel):
    account: str
    category: str | None = None
    amount: float | None = None


class ConfirmRequest(BaseModel):
    overrides: list[ConfirmOverride] = []


class ConfirmDiscoveryRequest(BaseModel):
    # V1 sends empty body ({}). V2 (post-MVP) will send plan_override for
    # in-modal edits to the DiscoveryPlan. Endpoint accepts both shapes today.
    plan_override: DiscoveryPlan | None = None


class CreateCompanyRequest(BaseModel):
    name: str
    sector: str | None = None


# ------------------------------------------------------------------ #
# Helpers                                                              #
# ------------------------------------------------------------------ #


_REVENUE_LIKE = {"REVENUE", "OTHER_INCOME"}
_EXPENSE_LIKE = {"COGS", "OPEX", "G&A", "R&D"}


def _fmt_ts(val):
    """Serialize a timestamp for JSON responses.

    Handles three cases: None, already-formatted ISO string (optional Z
    suffix normalized), or a datetime-like object exposing .isoformat().
    Module-level so both get_report and list_reports can share it.
    """
    if val is None:
        return None
    if isinstance(val, str):
        return val if val.endswith("Z") else f"{val}Z"
    try:
        return val.isoformat() + "Z"
    except AttributeError:
        return str(val)


def _direction(variance_pct: float | None, category: str) -> str:
    """Backend-only direction rule — no frontend derivation.

    Rule (Day 4 decision I — OTHER → neutral):
      - No history (variance_pct is None): neutral
      - OTHER category: neutral
      - REVENUE / OTHER_INCOME: ↑ favorable, ↓ unfavorable
      - COGS / OPEX / G&A / R&D: ↑ unfavorable, ↓ favorable
      - Unknown category: neutral (defensive — shouldn't happen post-seed)
    """
    if variance_pct is None:
        return "neutral"
    if category in _REVENUE_LIKE:
        return "favorable" if variance_pct >= 0 else "unfavorable"
    if category in _EXPENSE_LIKE:
        return "favorable" if variance_pct < 0 else "unfavorable"
    return "neutral"


def _map_low_confidence(columns: list) -> list:
    """C2: map stored {column, category, confidence} to {column, agent_guess, confidence}."""
    result = []
    for c in columns:
        if isinstance(c, dict):
            result.append(
                {
                    "column": c.get("column", ""),
                    "agent_guess": c.get("category", c.get("agent_guess", "")),
                    "confidence": c.get("confidence", 0.0),
                }
            )
    return result


# ------------------------------------------------------------------ #
# Endpoints                                                            #
# ------------------------------------------------------------------ #


@router.get("/health")
async def health():
    return {"status": "ok"}


@router.post("/upload")
@limiter.limit("5/minute;20/hour")
async def upload(
    request: Request,
    background_tasks: BackgroundTasks,
    files: List[UploadFile] = File(...),
    period: str = Form(...),
    user_id: str = Depends(get_current_user),
    company_id: str = Depends(get_company_id),
):
    try:
        period_date = date.fromisoformat(period)
    except ValueError:
        raise HTTPException(
            status_code=422,
            detail=messages.INVALID_PERIOD.format(period=period),
        )

    for f in files:
        suffix = (
            "." + f.filename.rsplit(".", 1)[-1].lower() if "." in f.filename else ""
        )
        if suffix not in SUPPORTED_EXTENSIONS:
            raise HTTPException(
                status_code=422,
                detail=messages.UNSUPPORTED_FORMAT.format(filename=f.filename),
            )

    storage = get_file_storage()
    runs_repo = get_runs_repo()

    run = runs_repo.create(company_id=company_id, period=period_date)
    run_id = run["id"]

    storage_keys: list[str] = []
    for f in files:
        data = await f.read()
        try:
            key = storage.upload(
                user_id=user_id,
                period=period,
                filename=f.filename,
                data=data,
            )
            storage_keys.append(key)
        except TransientIOError as exc:
            logger.error(
                "upload failed after retries",
                extra={"run_id": run_id, "file_name": f.filename, "error": str(exc)},
            )
            new_status = RunStateMachine.transition(
                RunStatus(run["status"]), RunStatus.UPLOAD_FAILED
            )
            runs_repo.update_status(
                run_id,
                new_status,
                extra={"error_message": messages.UPLOAD_FAILED},
            )
            raise HTTPException(status_code=503, detail=messages.UPLOAD_FAILED) from exc

    logger.info(
        "upload complete",
        extra={"run_id": run_id, "files": len(storage_keys), "company_id": company_id},
    )

    # Persist the first storage key on the run row so POST /runs/{run_id}/retry
    # can reschedule the pipeline without forcing a re-upload (Day 4 decision E).
    # Multi-file retry is post-MVP; today we reuse the first file only.
    if storage_keys:
        try:
            runs_repo.set_storage_key(run_id, storage_keys[0])
        except Exception as exc:
            logger.warning(
                "failed to persist storage_key on run",
                extra={"run_id": run_id, "error": str(exc)},
            )

    if len(storage_keys) == 1:
        background_tasks.add_task(
            run_parser_until_preview,
            run_id=run_id,
            storage_key=storage_keys[0],
            company_id=company_id,
            period=period_date,
        )
    else:
        background_tasks.add_task(
            run_multi_file_parser_with_mapping,
            run_id=run_id,
            storage_keys=storage_keys,
            company_id=company_id,
            period=period_date,
        )

    return {
        "run_id": run_id,
        "status": "processing",
        "files_received": len(files),
        "message": f"Files uploaded. Use /runs/{run_id}/status to poll progress.",
    }


@router.get("/runs/{run_id}/status")
@limiter.limit("120/minute")
async def run_status(
    request: Request,
    run_id: str,
    company_id: str = Depends(get_company_id),
):
    try:
        run = get_runs_repo().get_by_id(run_id)
    except RLSForbiddenError as exc:
        raise HTTPException(status_code=403, detail=messages.FORBIDDEN) from exc

    response: dict = {
        "run_id": run["id"],
        "status": run["status"],
        "step": run.get("step", 0),
        "total_steps": run.get("total_steps", 5),
        "progress_pct": run.get("progress_pct", 0),
        "step_label": run.get("step_label", ""),
        "error_message": run.get("error_message"),
        "report_id": run.get("report_id"),
        "raw_data_url": run.get("raw_data_url"),
        "opus_status": run.get("opus_status", "pending"),
        "low_confidence_columns": _map_low_confidence(
            run.get("low_confidence_columns") or []
        ),
        "parse_preview": run.get("parse_preview"),
    }
    if run["status"] == RunStatus.AWAITING_MAPPING_CONFIRMATION.value:
        pp = run.get("parse_preview") or {}
        response["mapping_draft"] = pp.get("mapping_draft")
    if run["status"] == RunStatus.AWAITING_DISCOVERY_CONFIRMATION.value:
        response["discovery_plan"] = run.get("discovery_plan")
    return response


@router.get("/runs/{run_id}/raw")
@limiter.limit("60/minute")
async def run_raw(
    request: Request,
    run_id: str,
    user_id: str = Depends(get_current_user),
    company_id: str = Depends(get_company_id),
):
    try:
        run = get_runs_repo().get_by_id(run_id)
    except RLSForbiddenError as exc:
        raise HTTPException(status_code=403, detail=messages.FORBIDDEN) from exc

    if run["status"] != RunStatus.GUARDRAIL_FAILED.value:
        raise HTTPException(status_code=404, detail=messages.NOT_FOUND)

    try:
        company = get_companies_repo().get_by_owner(user_id)
        company_name = company.get("name", "Unknown")
    except Exception:
        company_name = "Unknown"

    period = run.get("period", "unknown")
    run_id_short = run_id[:8]
    filename = f"raw_{period}_{run_id_short}.txt"

    from datetime import datetime

    banner = (
        f"=== IronLedger Raw Data — UNVERIFIED ===\n"
        f"Run ID: {run_id}\n"
        f"Company: {company_name}\n"
        f"Period: {period}\n"
        f"Generated: {datetime.utcnow().isoformat()}Z\n\n"
        f"This data was NOT verified by the numeric guardrail.\n"
        f"The automated report could not be produced. See /report for verified reports only.\n"
        f"===\n\n"
    )

    lines = [banner]
    pandas_summary = run.get("pandas_summary")
    if pandas_summary and isinstance(pandas_summary.get("accounts"), dict):
        accounts = pandas_summary["accounts"]
        for name in sorted(accounts):
            acc = accounts[name]
            variance = acc.get("variance_pct", 0.0)
            sign = "+" if variance >= 0 else ""
            lines.append(
                f"{name} ({acc.get('category', 'OTHER')}): "
                f"current={float(acc.get('current', 0)):,.2f} | "
                f"hist_avg={float(acc.get('historical_avg', 0)):,.2f} | "
                f"variance={sign}{variance:.1f}% | "
                f"severity={acc.get('severity', 'n/a').upper()}\n"
            )
    else:
        # Fallback: entries-only dump (pandas_summary not yet stored for this run)
        entries = get_entries_repo().list_for_period(company_id, period)
        accounts_map = get_accounts_repo().get_accounts_by_id(company_id)
        for entry in sorted(
            entries, key=lambda e: accounts_map.get(e.account_id, {}).get("name", "")
        ):
            info = accounts_map.get(
                entry.account_id, {"name": entry.account_id, "category": "OTHER"}
            )
            lines.append(
                f"{info['name']} ({info['category']}): {float(entry.actual_amount):,.2f}\n"
            )

    content = "".join(lines)
    return Response(
        content=content,
        media_type="text/plain; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/report/{company_id}/{period}")
@limiter.limit("60/minute")
async def get_report(
    request: Request,
    company_id: str,
    period: str,
    jwt_company_id: str = Depends(get_company_id),
):
    # Cross-check: URL company_id must match JWT-resolved company_id
    if company_id != jwt_company_id:
        raise HTTPException(status_code=403, detail=messages.FORBIDDEN)

    try:
        period_date = date.fromisoformat(period)
    except ValueError:
        raise HTTPException(
            status_code=422,
            detail=messages.INVALID_PERIOD.format(period=period),
        )

    report_raw, anomalies_raw, accounts_raw, entries_raw = await asyncio.gather(
        asyncio.to_thread(get_reports_repo().get, company_id, period_date),
        asyncio.to_thread(
            get_anomalies_repo().list_for_period, company_id, period_date
        ),
        asyncio.to_thread(get_accounts_repo().get_accounts_by_id, company_id),
        asyncio.to_thread(get_entries_repo().list_for_period, company_id, period_date),
        return_exceptions=True,
    )

    if isinstance(report_raw, BaseException):
        raise HTTPException(status_code=503, detail=messages.INTERNAL_ERROR)
    if report_raw is None:
        raise HTTPException(status_code=404, detail=messages.NOT_FOUND)

    report = report_raw
    # Enrichment queries degrade gracefully — report text always displays
    anomalies = [] if isinstance(anomalies_raw, BaseException) else anomalies_raw
    accounts_map = {} if isinstance(accounts_raw, BaseException) else accounts_raw
    entries = [] if isinstance(entries_raw, BaseException) else entries_raw
    current_by_account: dict[str, float] = {
        e.account_id: float(e.actual_amount) for e in entries
    }
    # Provenance map: account_id → {source_file (filename only), source_column}.
    # Powers AnomalyCard hover tooltip "drone_mar_2026.xlsx — column 'Amount'".
    provenance_by_account: dict[str, dict] = {
        e.account_id: {
            "source_file": Path(e.source_file).name if e.source_file else None,
            "source_column": e.source_column,
        }
        for e in entries
    }

    anomaly_list = []
    for a in sorted(
        anomalies, key=lambda x: {"high": 0, "medium": 1, "low": 2}.get(x.severity, 3)
    ):
        info = accounts_map.get(
            a.account_id, {"name": a.account_id, "category": "OTHER"}
        )
        current = current_by_account.get(a.account_id, 0.0)
        variance_pct = float(a.variance_pct) if a.variance_pct is not None else None
        provenance = provenance_by_account.get(
            a.account_id, {"source_file": None, "source_column": None}
        )

        # Reconstruct historical_avg from current + variance_pct
        if variance_pct is not None and (1 + variance_pct / 100) != 0:
            historical_avg = current / (1 + variance_pct / 100)
        else:
            historical_avg = 0.0

        anomaly_list.append(
            {
                "account": info["name"],
                "category": info["category"],
                "severity": a.severity,
                "direction": _direction(variance_pct, info["category"]),
                "current": current,
                "historical_avg": round(historical_avg, 2),
                "variance_pct": (
                    round(variance_pct, 1) if variance_pct is not None else None
                ),
                "description": a.description,
                "source_file": provenance["source_file"],
                "source_column": provenance["source_column"],
            }
        )

    # Staleness: true if any monthly_entry for this (company, period) was written
    # after the report was generated — i.e. user re-uploaded the source file.
    entry_timestamps = [e.created_at for e in entries if e.created_at is not None]
    is_stale = bool(
        report.created_at
        and entry_timestamps
        and max(entry_timestamps) > report.created_at
    )

    # P&L financials — computed from already-fetched entries + accounts_map.
    # No extra DB queries: both collections come from the asyncio.gather above.
    _REVENUE_CATS = {"REVENUE", "OTHER_INCOME"}
    _COGS_CATS = {"COGS"}
    _OPEX_CATS = {"OPEX", "G&A", "R&D"}
    try:
        _rev = sum(
            float(e.actual_amount)
            for e in entries
            if accounts_map.get(e.account_id, {}).get("category") in _REVENUE_CATS
        )
        _cogs = sum(
            float(e.actual_amount)
            for e in entries
            if accounts_map.get(e.account_id, {}).get("category") in _COGS_CATS
        )
        _opex = sum(
            float(e.actual_amount)
            for e in entries
            if accounts_map.get(e.account_id, {}).get("category") in _OPEX_CATS
        )
        _gp = _rev - _cogs
        _ni = _gp - _opex
        financials = {
            "revenue": round(_rev, 2),
            "cogs": round(_cogs, 2),
            "gross_profit": round(_gp, 2),
            "gross_margin_pct": round(_gp / _rev * 100, 1) if _rev else 0.0,
            "opex": round(_opex, 2),
            "net_income": round(_ni, 2),
            "net_margin_pct": round(_ni / _rev * 100, 1) if _rev else 0.0,
        }
    except Exception:
        financials = None

    return {
        "report_id": report.id,
        "company_id": report.company_id,
        "period": str(report.period),
        "generated_at": _fmt_ts(report.created_at),
        "summary": report.summary,
        "anomaly_count": report.anomaly_count,
        "error_count": report.error_count,
        "is_stale": is_stale,
        "opus_upgraded": report.opus_upgraded,
        "anomalies": anomaly_list,
        "reconciliations": report.reconciliations or [],
        "financials": financials,
    }


@router.get("/report/{company_id}/{period}/export.xlsx")
@limiter.limit("60/minute")
async def export_report_xlsx(
    request: Request,
    company_id: str,
    period: str,
    jwt_company_id: str = Depends(get_company_id),
):
    """Download the close package as a 3-sheet Excel workbook."""
    from backend.tools.excel_export import build_close_package

    if company_id != jwt_company_id:
        raise HTTPException(status_code=403, detail=messages.FORBIDDEN)

    try:
        period_date = date.fromisoformat(period)
    except ValueError:
        raise HTTPException(
            status_code=422,
            detail=messages.INVALID_PERIOD.format(period=period),
        )

    report = get_reports_repo().get(company_id, period_date)
    if report is None:
        raise HTTPException(status_code=404, detail=messages.NOT_FOUND)

    entries = get_entries_repo().list_for_period(company_id, period_date)
    accounts_map = get_accounts_repo().get_accounts_by_id(company_id)

    company_row = get_companies_repo().get_by_owner(jwt_company_id)
    company_name = company_row.get("name", "Company")

    entry_dicts = [
        {
            "account": accounts_map.get(e.account_id, {}).get("name", e.account_id),
            "category": accounts_map.get(e.account_id, {}).get("category", "OTHER"),
            "amount": float(e.actual_amount),
            "source_file": e.source_file,
            "source_breakdown": e.source_breakdown,
        }
        for e in entries
    ]

    xlsx_bytes = build_close_package(
        entries=entry_dicts,
        reconciliations=report.reconciliations,
        period=period_date,
        company_name=company_name,
    )

    filename = f"ironledger_{period}_close_package.xlsx"
    return Response(
        content=xlsx_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/anomalies/{company_id}/{period}")
@limiter.limit("60/minute")
async def get_anomalies(
    request: Request,
    company_id: str,
    period: str,
    jwt_company_id: str = Depends(get_company_id),
):
    if company_id != jwt_company_id:
        raise HTTPException(status_code=403, detail=messages.FORBIDDEN)

    try:
        period_date = date.fromisoformat(period)
    except ValueError:
        raise HTTPException(
            status_code=422,
            detail=messages.INVALID_PERIOD.format(period=period),
        )

    anomalies_raw, accounts_raw, entries_raw = await asyncio.gather(
        asyncio.to_thread(
            get_anomalies_repo().list_for_period, company_id, period_date
        ),
        asyncio.to_thread(get_accounts_repo().get_accounts_by_id, company_id),
        asyncio.to_thread(get_entries_repo().list_for_period, company_id, period_date),
        return_exceptions=True,
    )
    anomalies = [] if isinstance(anomalies_raw, BaseException) else anomalies_raw
    accounts_map = {} if isinstance(accounts_raw, BaseException) else accounts_raw
    entries = [] if isinstance(entries_raw, BaseException) else entries_raw
    provenance_by_account: dict[str, dict] = {
        e.account_id: {
            "source_file": Path(e.source_file).name if e.source_file else None,
            "source_column": e.source_column,
        }
        for e in entries
    }

    anomaly_list = []
    for a in anomalies:
        info = accounts_map.get(
            a.account_id, {"name": a.account_id, "category": "OTHER"}
        )
        variance_pct = float(a.variance_pct) if a.variance_pct is not None else None
        provenance = provenance_by_account.get(
            a.account_id, {"source_file": None, "source_column": None}
        )
        anomaly_list.append(
            {
                "id": a.id,
                "account": info["name"],
                "severity": a.severity,
                "variance_pct": variance_pct,
                "status": a.status,
                "direction": _direction(variance_pct, info["category"]),
                "source_file": provenance["source_file"],
                "source_column": provenance["source_column"],
            }
        )

    return {
        "company_id": company_id,
        "period": period,
        "anomalies": anomaly_list,
    }


@router.post("/mail/send")
@limiter.limit("10/hour")
async def mail_send(
    request: Request,
    body: MailSendRequest,
    company_id: str = Depends(get_company_id),
):
    # Day 5 will wire Resend. Scaffold only.
    return {"status": "scaffolded", "message": "Day 5 will wire Resend"}


# ------------------------------------------------------------------ #
# Day 4 additions — retry, mapping confirm, has-history               #
# ------------------------------------------------------------------ #


@router.post("/runs/{run_id}/retry")
@limiter.limit("5/minute;20/hour")
async def run_retry(
    request: Request,
    run_id: str,
    background_tasks: BackgroundTasks,
    company_id: str = Depends(get_company_id),
):
    """Re-trigger the pipeline against the storage_key of a guardrail_failed run.

    Creates a new runs row with fresh run_id; the failed run is left untouched
    for audit. No re-upload — file stays in Storage per guardrail_failed rules.
    """
    runs_repo = get_runs_repo()
    try:
        old_run = runs_repo.get_by_id(run_id)
    except RLSForbiddenError as exc:
        raise HTTPException(status_code=403, detail=messages.FORBIDDEN) from exc

    if old_run.get("company_id") != company_id:
        raise HTTPException(status_code=403, detail=messages.FORBIDDEN)

    if old_run.get("status") != RunStatus.GUARDRAIL_FAILED.value:
        raise HTTPException(
            status_code=422,
            detail="This run cannot be retried. Only guardrail-failed runs "
            "support Retry Analysis.",
        )

    storage_key = old_run.get("storage_key")
    if not storage_key:
        raise HTTPException(
            status_code=422,
            detail="This run has no stored file to retry. Please upload again.",
        )

    period_value = old_run.get("period")
    try:
        period_date = (
            date.fromisoformat(period_value)
            if isinstance(period_value, str)
            else period_value
        )
    except (ValueError, TypeError) as exc:
        raise HTTPException(
            status_code=422,
            detail=messages.INVALID_PERIOD.format(period=period_value),
        ) from exc

    # Create fresh run row; inherit storage_key for downstream retries if this one also fails
    new_run = runs_repo.create(company_id=company_id, period=period_date)
    new_run_id = new_run["id"]
    try:
        runs_repo.set_storage_key(new_run_id, storage_key)
    except Exception as exc:
        logger.warning(
            "failed to persist storage_key on retry run",
            extra={"run_id": new_run_id, "error": str(exc)},
        )

    logger.info(
        "retry started",
        extra={
            "old_run_id": run_id,
            "new_run_id": new_run_id,
            "storage_key": storage_key,
            "company_id": company_id,
        },
    )

    background_tasks.add_task(
        run_parser_until_preview,
        run_id=new_run_id,
        storage_key=storage_key,
        company_id=company_id,
        period=period_date,
    )

    return {
        "run_id": new_run_id,
        "status": "processing",
        "message": f"Retry started. Use /runs/{new_run_id}/status to poll progress.",
    }


@router.post("/runs/{run_id}/mapping/confirm")
@limiter.limit("30/minute")
async def confirm_mapping(
    request: Request,
    run_id: str,
    body: MappingConfirmRequest,
    company_id: str = Depends(get_company_id),
):
    """Persist user-confirmed column → category mappings to the accounts table.

    The current run's report is not regenerated — confirmed mappings only affect
    future uploads. `SKIP` is a frontend-only sentinel: those rows are dropped
    from the persisted set and counted separately.
    """
    runs_repo = get_runs_repo()
    try:
        run = runs_repo.get_by_id(run_id)
    except RLSForbiddenError as exc:
        raise HTTPException(status_code=403, detail=messages.FORBIDDEN) from exc

    if run.get("company_id") != company_id:
        raise HTTPException(status_code=403, detail=messages.FORBIDDEN)

    accounts_repo = get_accounts_repo()
    persisted = 0
    skipped = 0

    for item in body.mappings:
        if item.category == "SKIP":
            skipped += 1
            continue
        if item.category not in VALID_CATEGORIES:
            raise HTTPException(
                status_code=422,
                detail=f"Category '{item.category}' is not a valid US GAAP category.",
            )
        accounts_repo.upsert_mapping(company_id, item.column, item.category)
        persisted += 1

    logger.info(
        "mapping confirmed",
        extra={
            "run_id": run_id,
            "company_id": company_id,
            "persisted_count": persisted,
            "skipped_count": skipped,
        },
    )

    return {
        "status": "confirmed",
        "persisted_count": persisted,
        "skipped_count": skipped,
    }


@router.post("/runs/{run_id}/confirm")
@limiter.limit("30/minute")
async def confirm_run(
    request: Request,
    run_id: str,
    body: ConfirmRequest,
    background_tasks: BackgroundTasks,
    company_id: str = Depends(get_company_id),
):
    """Write confirmed preview data to DB, then kick off comparison + report.

    Called after the user reviews the ParsePreviewPanel and clicks
    "Confirm & Analyze". The run transitions from AWAITING_CONFIRMATION
    to COMPARING; the pipeline resumes in a BackgroundTask.
    """
    runs_repo = get_runs_repo()
    try:
        run = runs_repo.get_by_id(run_id)
    except RLSForbiddenError as exc:
        raise HTTPException(status_code=403, detail=messages.FORBIDDEN) from exc

    if run.get("company_id") != company_id:
        raise HTTPException(status_code=403, detail=messages.FORBIDDEN)

    if run.get("status") != RunStatus.AWAITING_CONFIRMATION.value:
        raise HTTPException(
            status_code=422,
            detail="This run is not waiting for confirmation.",
        )

    parse_preview = run.get("parse_preview")
    if not parse_preview or not parse_preview.get("rows"):
        raise HTTPException(
            status_code=422,
            detail="No preview data found for this run. Please upload again.",
        )

    period_value = run.get("period")
    try:
        period_date = (
            date.fromisoformat(period_value)
            if isinstance(period_value, str)
            else period_value
        )
    except (ValueError, TypeError) as exc:
        raise HTTPException(
            status_code=422,
            detail=messages.INVALID_PERIOD.format(period=period_value),
        ) from exc

    storage_key = run.get("storage_key") or ""
    source_column = parse_preview.get("source_column", "amount")
    rows = parse_preview["rows"]
    source_breakdown_by_account: dict = (
        parse_preview.get("source_breakdown_by_account") or {}
    )

    # Validate overrides before touching the DB
    for o in body.overrides:
        if (
            o.category is not None
            and o.category not in VALID_CATEGORIES
            and o.category != "SKIP"
        ):
            raise HTTPException(
                status_code=422,
                detail=f"Category '{o.category}' is not a valid US GAAP category.",
            )
        if o.amount is not None and (
            not isinstance(o.amount, (int, float)) or o.amount != o.amount
        ):
            raise HTTPException(
                status_code=422,
                detail=f"Invalid amount for account '{o.account}'.",
            )

    category_overrides = {
        o.account: o.category for o in body.overrides if o.category is not None
    }
    amount_overrides = {
        o.account: o.amount for o in body.overrides if o.amount is not None
    }

    accounts_repo = get_accounts_repo()
    entries_repo = get_entries_repo()

    # Collect all (name, category) pairs upfront, excluding SKIPs.
    # batch_get_or_create resolves them in 3 round-trips instead of N.
    items = [
        (row["account"], category_overrides.get(row["account"], row["category"]))
        for row in rows
        if category_overrides.get(row["account"], row["category"]) != "SKIP"
    ]
    try:
        account_id_by_name = accounts_repo.batch_get_or_create(company_id, items)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=messages.INTERNAL_ERROR) from exc

    entries: list[MonthlyEntry] = []
    for row in rows:
        account_name = row["account"]
        category = category_overrides.get(account_name, row["category"])
        if category == "SKIP":
            continue
        amount = amount_overrides.get(account_name, row["amount"])
        entries.append(
            MonthlyEntry(
                id=str(uuid.uuid4()),
                company_id=company_id,
                account_id=account_id_by_name[account_name],
                period=period_date,
                actual_amount=Decimal(str(amount)),
                source_file=storage_key,
                source_column=source_column,
                source_breakdown=source_breakdown_by_account.get(account_name),
            )
        )

    try:
        entries_repo.replace_period(company_id, period_date, entries)
    except DuplicateEntryError as exc:
        raise HTTPException(status_code=409, detail=messages.DUPLICATE_ENTRY) from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail=messages.INTERNAL_ERROR) from exc

    new_status = RunStateMachine.transition(
        RunStatus.AWAITING_CONFIRMATION, RunStatus.COMPARING
    )
    runs_repo.update_status(
        run_id,
        new_status,
        extra={
            "step": 4,
            "step_label": "Comparing to history...",
            "progress_pct": 75,
        },
    )

    logger.info(
        "run confirmed",
        extra={
            "run_id": run_id,
            "company_id": company_id,
            "entries_written": len(entries),
            "overrides_applied": len(body.overrides),
        },
    )

    background_tasks.add_task(
        run_comparison_and_report,
        run_id=run_id,
        company_id=company_id,
        period=period_date,
        storage_key=storage_key,
    )
    background_tasks.add_task(
        run_opus_upgrade,
        run_id=run_id,
        company_id=company_id,
        period=period_date,
    )

    return {"status": "confirmed", "run_id": run_id, "entries_written": len(entries)}


# ------------------------------------------------------------------ #
# AccountMapper: confirm-mappings                                    #
# ------------------------------------------------------------------ #


class ConfirmMappingsRequest(BaseModel):
    decisions: dict[str, str]
    # {source_pattern: gl_account_name} — flat, no per-file-type nesting


@router.post("/runs/{run_id}/confirm-mappings")
@limiter.limit("20/minute")
async def confirm_mappings(
    request: Request,
    run_id: str,
    body: ConfirmMappingsRequest,
    background_tasks: BackgroundTasks,
    user_id: str = Depends(get_current_user),
    company_id: str = Depends(get_company_id),
):
    """Accept user-approved account mappings and resume the pipeline (Phase B)."""
    if not body.decisions:
        raise HTTPException(status_code=400, detail="decisions must not be empty")

    runs_repo = get_runs_repo()
    try:
        run = runs_repo.get_by_id(run_id)
    except RLSForbiddenError as exc:
        raise HTTPException(status_code=403, detail=messages.FORBIDDEN) from exc

    # State guard
    if run.get("status") != RunStatus.AWAITING_MAPPING_CONFIRMATION.value:
        raise HTTPException(
            status_code=409,
            detail=f"Run is not awaiting mapping confirmation (status: {run.get('status')})",
        )

    # Validate all submitted gl_accounts are in the saved pool
    pp = run.get("parse_preview") or {}
    draft = pp.get("mapping_draft") or {}
    pool: list[str] = draft.get("gl_account_pool", [])
    bad = [gl for gl in body.decisions.values() if gl and gl not in pool]
    if bad:
        raise HTTPException(
            status_code=400,
            detail=f"{messages.MAPPING_INVALID_GL_ACCOUNT} Unknown: {bad}",
        )

    # Resolve period from the run row
    period_raw = run.get("period")
    try:
        period_date = date.fromisoformat(str(period_raw)[:10])
    except (ValueError, TypeError) as exc:
        raise HTTPException(
            status_code=422, detail="Could not determine run period"
        ) from exc

    # Synchronously transition to APPLYING_MAPPING before firing the background task.
    # This prevents re-entry: any subsequent confirm-mappings call will see a non-
    # AWAITING_MAPPING_CONFIRMATION status and get 409 immediately — even if Phase B
    # is still running. Without this, the 20-second Phase B re-parse window allows
    # the UI polling loop to re-trigger MappingReview and submit duplicate requests.
    applying_status = RunStateMachine.transition(
        RunStatus.AWAITING_MAPPING_CONFIRMATION, RunStatus.APPLYING_MAPPING
    )
    runs_repo.update_status(
        run_id,
        applying_status,
        extra={"step_label": "Applying mappings…", "progress_pct": 55},
    )

    background_tasks.add_task(
        apply_mapping_and_consolidate,
        run_id=run_id,
        company_id=company_id,
        period=period_date,
        user_decisions=body.decisions,
    )

    return {"status": "applying_mappings", "run_id": run_id}


@router.post("/runs/{run_id}/confirm-discovery")
@limiter.limit("30/minute")
async def confirm_discovery(
    request: Request,
    run_id: str,
    body: ConfirmDiscoveryRequest,
    background_tasks: BackgroundTasks,
    company_id: str = Depends(get_company_id),
):
    """User approved the Discovery plan. Resume pipeline from MAPPING onward.

    V1 body is empty ({}). V2 will supply plan_override for in-modal edits —
    the endpoint accepts both shapes today so the frontend contract is stable.
    """
    runs_repo = get_runs_repo()
    try:
        run = runs_repo.get_by_id(run_id)
    except RLSForbiddenError as exc:
        raise HTTPException(status_code=403, detail=messages.FORBIDDEN) from exc

    if run.get("company_id") != company_id:
        raise HTTPException(status_code=403, detail=messages.FORBIDDEN)

    if run.get("status") != RunStatus.AWAITING_DISCOVERY_CONFIRMATION.value:
        raise HTTPException(
            status_code=422,
            detail="This run is not waiting for discovery confirmation.",
        )

    # Persist override if supplied; otherwise keep stored plan as-is.
    # Either way, flip approval_mode to 'manual'.
    if body.plan_override is not None:
        plan_dict = body.plan_override.model_dump(mode="json")
        # Preserve the stored `_preview` (sanitized sample snippet) across an
        # edit so the UI still has context after the user clicks Confirm.
        stored = run.get("discovery_plan") or {}
        if "_preview" in stored:
            plan_dict["_preview"] = stored["_preview"]
        runs_repo.set_discovery_plan(run_id, plan_dict, approval_mode="manual")
    else:
        # No edit: just mark approval_mode. No need to rewrite the plan JSONB.
        # update_status merges `extra` into the UPDATE patch.
        pass

    new_status = RunStateMachine.transition(
        RunStatus.AWAITING_DISCOVERY_CONFIRMATION, RunStatus.MAPPING
    )
    status_extra: dict = {
        "step": 2,
        "step_label": "Mapping accounts...",
        "progress_pct": 40,
    }
    if body.plan_override is None:
        # Flip approval_mode atomically with the status transition
        status_extra["discovery_approval_mode"] = "manual"
    runs_repo.update_status(run_id, new_status, extra=status_extra)

    period_value = run.get("period")
    try:
        period_date = (
            date.fromisoformat(period_value)
            if isinstance(period_value, str)
            else period_value
        )
    except (ValueError, TypeError) as exc:
        raise HTTPException(
            status_code=422,
            detail=messages.INVALID_PERIOD.format(period=period_value),
        ) from exc

    storage_key = run.get("storage_key") or ""
    background_tasks.add_task(
        run_parser_after_discovery_approval,
        run_id=run_id,
        company_id=company_id,
        period=period_date,
        storage_key=storage_key,
    )

    logger.info(
        "discovery_plan_approved",
        extra={
            "run_id": run_id,
            "company_id": company_id,
            "approval_mode": "manual",
            "edit_supplied": body.plan_override is not None,
        },
    )

    return {"status": "confirmed", "run_id": run_id}


@router.post("/runs/{run_id}/reject-discovery")
@limiter.limit("30/minute")
async def reject_discovery(
    request: Request,
    run_id: str,
    company_id: str = Depends(get_company_id),
):
    """User rejected the Discovery plan. Terminal failure; re-upload from UI.

    Storage file stays (R-015 accepted leak). Post-MVP: TTL sweep.
    """
    runs_repo = get_runs_repo()
    try:
        run = runs_repo.get_by_id(run_id)
    except RLSForbiddenError as exc:
        raise HTTPException(status_code=403, detail=messages.FORBIDDEN) from exc

    if run.get("company_id") != company_id:
        raise HTTPException(status_code=403, detail=messages.FORBIDDEN)

    if run.get("status") != RunStatus.AWAITING_DISCOVERY_CONFIRMATION.value:
        raise HTTPException(
            status_code=422,
            detail="This run is not waiting for discovery confirmation.",
        )

    failed_status = RunStateMachine.transition(
        RunStatus.AWAITING_DISCOVERY_CONFIRMATION, RunStatus.PARSING_FAILED
    )
    runs_repo.update_status(
        run_id,
        failed_status,
        extra={"error_message": messages.DISCOVERY_REJECTED},
    )

    logger.info(
        "discovery_plan_rejected",
        extra={"run_id": run_id, "company_id": company_id},
    )

    return {"status": "rejected", "run_id": run_id}


@router.get("/companies/me")
@limiter.limit("60/minute")
async def get_my_company(
    request: Request,
    company: dict = Depends(get_cached_company),
):
    """Return the authenticated user's company profile."""
    return {
        "id": company["id"],
        "name": company.get("name", ""),
        "sector": company.get("sector"),
        "currency": company.get("currency", "USD"),
    }


@router.get("/companies/me/has-history")
@limiter.limit("60/minute")
async def has_history(
    request: Request,
    company_id: str = Depends(get_company_id),
):
    """Tell the frontend whether to render EmptyState.

    `has_history` is False iff the authenticated user's company has zero
    monthly_entries rows. `periods_loaded` is the count of distinct periods.
    """
    periods_loaded = get_entries_repo().count_distinct_periods(company_id)
    return {
        "has_history": periods_loaded > 0,
        "periods_loaded": periods_loaded,
    }


@router.post("/companies", status_code=201)
@limiter.limit("5/hour")
async def create_company(
    request: Request,
    body: CreateCompanyRequest,
    user_id: str = Depends(get_current_user),
):
    """Create the company record for a newly registered user.

    Idempotent: if a company already exists for this user, returns it with
    status 200 rather than creating a duplicate. This handles the case where
    the user submitted the form but the onboarding_done metadata write failed
    and they are re-running onboarding.

    Does NOT use get_company_id — the user has no company yet when this fires.
    """
    companies_repo = get_companies_repo()

    try:
        existing = companies_repo.get_by_owner(user_id)
        logger.info(
            "company_already_exists",
            extra={"user_id": user_id, "company_id": existing["id"]},
        )
        return JSONResponse(
            status_code=200,
            content={
                "id": existing["id"],
                "name": existing.get("name", ""),
                "sector": existing.get("sector"),
                "currency": existing.get("currency", "USD"),
            },
        )
    except RLSForbiddenError:
        pass

    try:
        company = companies_repo.create(
            owner_id=user_id,
            name=body.name,
            sector=body.sector,
            currency="USD",
        )
    except Exception as exc:
        logger.error(
            "company_create_failed",
            extra={"user_id": user_id, "error": str(exc)},
        )
        raise HTTPException(
            status_code=503, detail=messages.COMPANY_CREATE_FAILED
        ) from exc

    logger.info(
        "company_created",
        extra={"user_id": user_id, "company_id": company["id"]},
    )
    return {
        "id": company["id"],
        "name": company.get("name", ""),
        "sector": company.get("sector"),
        "currency": company.get("currency", "USD"),
    }


@router.get("/reports")
@limiter.limit("60/minute")
async def list_reports(
    request: Request,
    limit: int = 12,
    company_id: str = Depends(get_company_id),
):
    """List verified reports for the authenticated user's company.

    Powers the Dashboard HistoryList and is the foundation for a future
    /reports page. Ordered by period DESC, capped at 50 to protect the
    payload size. `limit` query param is clamped to [1, 50].
    """
    capped = max(1, min(limit, 50))
    reports = get_reports_repo().list_all(company_id, capped)

    return {
        "reports": [
            {
                "report_id": r.id,
                "period": str(r.period),
                "generated_at": _fmt_ts(r.created_at),
                "anomaly_count": r.anomaly_count,
                "error_count": r.error_count,
                "report_type": r.report_type,
                "quarter": r.quarter,
                "year": r.year,
                "is_stale": r.is_stale,
            }
            for r in reports
        ],
    }


@router.get("/data")
@limiter.limit("60/minute")
async def get_data(
    request: Request,
    year: int,
    company_id: str = Depends(get_company_id),
):
    """Fetch all monthly_entries for a given year with account metadata.

    Powers the Data viewer table. Returns full year (12 periods) in one call
    to minimize API requests; frontend filters by month client-side.
    """
    entries_repo = get_entries_repo()
    accounts_repo = get_accounts_repo()

    start_date = date(year, 1, 1)
    end_date = date(year, 12, 31)

    all_entries = entries_repo.list_for_year(company_id, start_date, end_date)
    accounts_map = accounts_repo.get_accounts_by_id(company_id)

    entries_list = []
    total_amount = Decimal("0.00")

    for entry in all_entries:
        account_info = accounts_map.get(
            entry.account_id, {"name": "Unknown", "category": "OTHER"}
        )

        amount = float(entry.actual_amount)
        total_amount += entry.actual_amount

        entries_list.append(
            {
                "period": str(entry.period),
                "account": account_info["name"],
                "category": account_info["category"],
                "amount": amount,
                "variance_pct": None,
                "source_file": (
                    Path(entry.source_file).name if entry.source_file else None
                ),
                "source_column": entry.source_column,
            }
        )

    return {
        "year": year,
        "total_amount": float(total_amount),
        "account_count": len(entries_list),
        "entries": entries_list,
    }


# ------------------------------------------------------------------ #
# Quarterly Report Endpoints                                          #
# ------------------------------------------------------------------ #


def run_quarterly_background(
    job_id: str,
    company_id: str,
    year: int,
    quarter: int,
):
    """Background task for quarterly report generation with progress tracking."""
    from backend.agents.quarterly import QuarterlyAgent
    from backend.api.deps import (
        get_anomalies_repo,
        get_llm_client,
        get_reports_repo,
        get_runs_repo,
    )

    def update_progress(progress_pct: int, step_label: str):
        """Update progress in the in-memory jobs dict."""
        if job_id in _quarterly_jobs:
            _quarterly_jobs[job_id]["progress_pct"] = progress_pct
            _quarterly_jobs[job_id]["step_label"] = step_label

    try:
        agent = QuarterlyAgent(
            runs_repo=get_runs_repo(),
            anomalies_repo=get_anomalies_repo(),
            llm_client=get_llm_client(),
            reports_repo=get_reports_repo(),
        )

        result = agent.run(
            company_id=company_id,
            year=year,
            quarter=quarter,
            progress_callback=update_progress,
        )

        if result["status"] == "complete":
            _quarterly_jobs[job_id]["status"] = "complete"
            _quarterly_jobs[job_id]["result"] = result["result"]
            _quarterly_jobs[job_id]["progress_pct"] = 100
        else:
            _quarterly_jobs[job_id]["status"] = "failed"
            _quarterly_jobs[job_id]["error"] = {
                "error_type": result["error_type"],
                "message": result["message"],
            }

    except Exception as exc:
        logger.error(
            "quarterly background task unhandled exception",
            extra={
                "job_id": job_id,
                "year": year,
                "quarter": quarter,
                "error": str(exc),
            },
            exc_info=True,
        )
        _quarterly_jobs[job_id]["status"] = "failed"
        _quarterly_jobs[job_id]["error"] = {
            "error_type": "internal",
            "message": "Something went wrong. Please try again or contact support.",
        }


@router.post("/report/{company_id}/quarterly/{year}/{quarter}/generate")
@limiter.limit("10/hour")
async def generate_quarterly_report(
    request: Request,
    background_tasks: BackgroundTasks,
    year: int,
    quarter: int,
    company_id: str = Depends(get_company_id),
):
    """Generate a quarterly report for the given year and quarter.

    Validates that company_id from JWT matches path param, then kicks off
    a background task and returns immediately with a job_id for polling.

    Returns 400 synchronously if <2 completed months exist for the quarter.
    """
    # Validate quarter
    if quarter not in (1, 2, 3, 4):
        raise HTTPException(status_code=400, detail="Quarter must be 1, 2, 3, or 4")

    # Synchronous month-count check — must happen before the background task fires
    # so the caller gets HTTP 400 immediately, not a job that fails on first poll.
    base_month = (quarter - 1) * 3 + 1
    quarter_months = [date(year, base_month + i, 1) for i in range(3)]
    runs_repo = get_runs_repo()
    available_count = 0
    for period in quarter_months:
        run_id = runs_repo.get_latest_run_id_for_period(company_id, period)
        if run_id:
            run = runs_repo.get_by_id(run_id)
            if run.get("status") == "complete" and run.get("pandas_summary"):
                available_count += 1
    if available_count < 2:
        return JSONResponse(
            status_code=400,
            content={
                "error_type": "empty_data",
                "message": "At least 2 months of data required to generate a quarterly summary.",
            },
        )

    # Generate job_id
    job_id = str(uuid.uuid4())

    # Initialize progress in in-memory dict
    _quarterly_jobs[job_id] = {
        "status": "running",
        "progress_pct": 0,
        "step_label": "Starting...",
        "result": None,
        "error": None,
    }

    # Fire background task
    background_tasks.add_task(
        run_quarterly_background,
        job_id,
        company_id,
        year,
        quarter,
    )

    logger.info(
        "quarterly_report_job_created",
        extra={
            "job_id": job_id,
            "company_id": company_id,
            "year": year,
            "quarter": quarter,
        },
    )

    return {
        "job_id": job_id,
        "status": "running",
        "progress_pct": 0,
    }


@router.get("/report/{company_id}/quarterly/{year}/{quarter}/status/{job_id}")
@limiter.limit("120/minute")
async def get_quarterly_status(
    request: Request,
    job_id: str,
    year: int,
    quarter: int,
    company_id: str = Depends(get_company_id),
):
    """Poll the status of a quarterly report generation job.

    Returns current progress or final result when complete.
    """
    if job_id not in _quarterly_jobs:
        raise HTTPException(status_code=404, detail="Job not found")

    job_data = _quarterly_jobs[job_id]

    response = {
        "status": job_data["status"],
        "progress_pct": job_data.get("progress_pct", 0),
        "step_label": job_data.get("step_label", ""),
    }

    if job_data["status"] == "complete":
        response["result"] = job_data["result"]
    elif job_data["status"] == "failed":
        response["error"] = job_data["error"]

    return response


@router.get("/report/{company_id}/quarterly/{year}/{quarter}")
@limiter.limit("60/minute")
async def get_quarterly_report(
    request: Request,
    year: int,
    quarter: int,
    company_id: str = Depends(get_company_id),
):
    """Fetch a persisted quarterly report from the database.

    Returns 404 if not yet generated. The frontend should then show
    the "Generate" button rather than polling for status.
    """
    if quarter not in (1, 2, 3, 4):
        raise HTTPException(status_code=400, detail="Quarter must be 1, 2, 3, or 4")

    reports_repo = get_reports_repo()
    report = reports_repo.get_quarterly(company_id, year, quarter)

    if not report:
        raise HTTPException(status_code=404, detail="Quarterly report not found")

    # Return the full quarterly data
    result = report.quarterly_data or {}

    return {
        "report_id": report.id,
        "year": year,
        "quarter": quarter,
        "is_stale": report.is_stale,
        "generated_at": (
            report.created_at
            if isinstance(report.created_at, str)
            else report.created_at.isoformat() if report.created_at else None
        ),
        "result": result,
    }


@router.delete("/report/{company_id}/quarterly/{year}/{quarter}")
@limiter.limit("60/minute")
async def delete_quarterly_report(
    request: Request,
    year: int,
    quarter: int,
    company_id: str = Depends(get_company_id),
):
    """Delete a persisted quarterly report. Idempotent — returns 200 even if no row exists.

    Frontend calls this before POST /generate when regenerating, so that
    write_quarterly always does a clean INSERT (no UPSERT).
    """
    if quarter not in (1, 2, 3, 4):
        raise HTTPException(status_code=400, detail="Quarter must be 1, 2, 3, or 4")

    reports_repo = get_reports_repo()
    reports_repo.delete_quarterly(company_id, year, quarter)
    return {"deleted": True}
