from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from backend import messages
from backend.api.auth import (
    get_cached_company,
    get_company_id,
    get_current_user,
    invalidate_company_cache,
)
from backend.api.deps import get_companies_repo, get_entries_repo
from backend.api.rate_limit import limiter
from backend.domain.errors import RLSForbiddenError
from backend.logger import get_logger

logger = get_logger(__name__)
router = APIRouter()


class CreateCompanyRequest(BaseModel):
    name: str
    sector: str | None = None
    monthly_revenue_band: Literal["under_100k", "100k_250k", "250k_500k", "500k_plus"]


class UpdateCompanyRequest(BaseModel):
    monthly_revenue_band: Literal["under_100k", "100k_250k", "250k_500k", "500k_plus"]


def _company_public(company: dict) -> dict:
    return {
        "id": company["id"],
        "name": company.get("name", ""),
        "sector": company.get("sector"),
        "currency": company.get("currency", "USD"),
        "monthly_revenue_band": company.get("monthly_revenue_band"),
    }


@router.get("/companies/me")
@limiter.limit("60/minute")
async def get_my_company(
    request: Request,
    company: dict = Depends(get_cached_company),
):
    """Return the authenticated user's company profile."""
    return _company_public(company)


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
            content=_company_public(existing),
        )
    except RLSForbiddenError:
        pass

    try:
        company = companies_repo.create(
            owner_id=user_id,
            name=body.name,
            sector=body.sector,
            currency="USD",
            monthly_revenue_band=body.monthly_revenue_band,
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
    return _company_public(company)


@router.patch("/companies/me")
@limiter.limit("5/hour")
async def update_my_company(
    request: Request,
    body: UpdateCompanyRequest,
    user_id: str = Depends(get_current_user),
    company: dict = Depends(get_cached_company),
):
    """Update typical monthly revenue band. The only writer for an existing row."""
    try:
        updated = get_companies_repo().update(
            company["id"],
            monthly_revenue_band=body.monthly_revenue_band,
        )
    except RLSForbiddenError as exc:
        raise HTTPException(status_code=403, detail=messages.FORBIDDEN) from exc
    except Exception as exc:
        logger.error(
            "company_update_failed",
            extra={"user_id": user_id, "error": str(exc)},
        )
        raise HTTPException(
            status_code=503, detail=messages.COMPANY_UPDATE_FAILED
        ) from exc

    invalidate_company_cache(user_id)
    return _company_public(updated)
