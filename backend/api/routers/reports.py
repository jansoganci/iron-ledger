import asyncio
from datetime import date
from decimal import Decimal
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request, Response

from backend import messages
from backend.api.auth import get_cached_company, get_company_id
from backend.api.deps import (
    get_accounts_repo,
    get_anomalies_repo,
    get_entries_repo,
    get_reports_repo,
)
from backend.api.rate_limit import limiter
from backend.tools.tie_out_summary import build_tie_out_summary, group_for_item

router = APIRouter()

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

    source_files = [Path(e.source_file).name for e in entries if e.source_file]
    recon_items = list(report.reconciliations or [])
    tie_out_summary = build_tie_out_summary(source_files, recon_items)
    reconciliations = []
    for item in recon_items:
        if not isinstance(item, dict):
            continue
        row = dict(item)
        row["tie_out_group"] = group_for_item(row)
        reconciliations.append(row)

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
        "reconciliations": reconciliations,
        "financials": financials,
        "tie_out_summary": tie_out_summary,
    }


@router.get("/report/{company_id}/{period}/export.xlsx")
@limiter.limit("60/minute")
async def export_report_xlsx(
    request: Request,
    company_id: str,
    period: str,
    jwt_company_id: str = Depends(get_company_id),
    company: dict = Depends(get_cached_company),
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

    # get_by_owner takes an OWNER id. This passed jwt_company_id — a company
    # id — so the lookup matched nothing and raised RLSForbiddenError, which
    # surfaced as a 403 on every export for every user. `get_cached_company`
    # resolves the company from the authenticated user and shares the cache
    # with get_company_id, so this is also one fewer round trip.
    company_name = company.get("name", "Company")

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

    filename = f"monthproof_{period}_close_package.xlsx"
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
