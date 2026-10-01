"""Close / reopen a period (Dil 3). Thin: no business logic beyond the guards.

company_id comes from the signed-in user, never from the client. Closing is a
person's sign-off on a finished monthly report; "Numbers verified" is not a
close and nothing here closes a month on its own.
"""

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict

from backend import messages
from backend.api.auth import get_company_id, get_current_user
from backend.api.deps import get_period_closes_repo, get_reports_repo
from backend.api.rate_limit import limiter
from backend.domain.errors import DuplicateEntryError, TransientIOError
from backend.logger import get_logger

logger = get_logger(__name__)
router = APIRouter()


class ConfirmBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    confirm: bool = False


def _parse_period(period: str) -> date:
    try:
        parsed = date.fromisoformat(period)
    except ValueError as exc:
        raise HTTPException(
            status_code=422, detail=messages.INVALID_PERIOD.format(period=period)
        ) from exc
    if parsed.day != 1:
        raise HTTPException(
            status_code=422, detail=messages.INVALID_PERIOD.format(period=period)
        )
    return parsed


def _public(row: dict | None, user_id: str, log: list[dict]) -> dict:
    close = None
    if row is not None:
        close = {
            "closed_at": row.get("closed_at"),
            "closed_by_email": row.get("closed_by_email"),
            "closed_by_you": row.get("closed_by") == user_id,
        }
    return {"closed": row is not None, "close": close, "log": log}


def _state(company_id: str, period: date, user_id: str) -> dict:
    repo = get_period_closes_repo()
    try:
        return _public(
            repo.get_active(company_id, period),
            user_id,
            repo.list_log(company_id, period),
        )
    except TransientIOError as exc:
        raise HTTPException(status_code=503, detail=messages.INTERNAL_ERROR) from exc


@router.get("/periods/{period}/close")
@limiter.limit("60/minute")
async def get_close_state(
    request: Request,
    period: str,
    user_id: str = Depends(get_current_user),
    company_id: str = Depends(get_company_id),
):
    return _state(company_id, _parse_period(period), user_id)


@router.post("/periods/{period}/close")
@limiter.limit("20/hour")
async def close_period(
    request: Request,
    period: str,
    body: ConfirmBody,
    user_id: str = Depends(get_current_user),
    company_id: str = Depends(get_company_id),
):
    period_date = _parse_period(period)
    if not body.confirm:
        raise HTTPException(
            status_code=422, detail=messages.PERIOD_CLOSE_CONFIRM_REQUIRED
        )
    try:
        report = get_reports_repo().get(company_id, period_date)
    except TransientIOError as exc:
        raise HTTPException(status_code=503, detail=messages.INTERNAL_ERROR) from exc
    if report is None:
        raise HTTPException(status_code=409, detail=messages.PERIOD_CLOSE_NEEDS_REPORT)
    try:
        get_period_closes_repo().close(company_id, period_date, user_id)
    except DuplicateEntryError as exc:
        raise HTTPException(
            status_code=409, detail=messages.PERIOD_ALREADY_CLOSED
        ) from exc
    except TransientIOError as exc:
        raise HTTPException(
            status_code=503, detail=messages.PERIOD_CLOSE_FAILED
        ) from exc
    logger.info(
        "period closed",
        extra={"company_id": company_id, "period": str(period_date)},
    )
    return _state(company_id, period_date, user_id)


@router.post("/periods/{period}/reopen")
@limiter.limit("20/hour")
async def reopen_period(
    request: Request,
    period: str,
    body: ConfirmBody,
    user_id: str = Depends(get_current_user),
    company_id: str = Depends(get_company_id),
):
    period_date = _parse_period(period)
    if not body.confirm:
        raise HTTPException(
            status_code=422, detail=messages.PERIOD_REOPEN_CONFIRM_REQUIRED
        )
    try:
        row = get_period_closes_repo().reopen(company_id, period_date, user_id)
    except TransientIOError as exc:
        raise HTTPException(
            status_code=503, detail=messages.PERIOD_CLOSE_FAILED
        ) from exc
    if row is None:
        raise HTTPException(status_code=409, detail=messages.PERIOD_NOT_CLOSED)
    logger.info(
        "period reopened",
        extra={"company_id": company_id, "period": str(period_date)},
    )
    return _state(company_id, period_date, user_id)
