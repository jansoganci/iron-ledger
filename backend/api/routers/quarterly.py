import uuid
from datetime import date

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from fastapi.responses import JSONResponse

from backend.api.auth import get_company_id
from backend.api.deps import get_reports_repo, get_runs_repo
from backend.api.rate_limit import limiter
from backend.logger import get_logger

logger = get_logger(__name__)
router = APIRouter()

# In-memory progress tracking for quarterly reports (MVP — Redis post-MVP)
_quarterly_jobs: dict[str, dict] = {}


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
