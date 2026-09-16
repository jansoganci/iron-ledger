from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

from backend import messages
from backend.api.auth import get_company_id
from backend.api.deps import get_accounts_repo, get_source_mappings_repo
from backend.api.rate_limit import limiter
from backend.domain.contracts import DEFAULT_GL_CATEGORIES
from backend.domain.entities import SourceAccountMapping
from backend.domain.errors import RLSForbiddenError
from backend.logger import get_logger

logger = get_logger(__name__)
router = APIRouter()


class UpdateSourceMappingRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    gl_account: str = Field(min_length=1, max_length=200)


def _public_mapping(row: SourceAccountMapping) -> dict:
    updated = row.updated_at
    if isinstance(updated, datetime):
        updated_at = updated.isoformat()
    else:
        updated_at = str(updated) if updated else None
    return {
        "id": row.id,
        "file_type": row.file_type,
        "source_pattern": row.source_pattern,
        "gl_account": row.gl_account,
        "updated_at": updated_at,
    }


@router.get("/source-mappings")
@limiter.limit("60/minute")
async def list_source_mappings(
    request: Request,
    company_id: str = Depends(get_company_id),
):
    """List saved vendor and expense names for the authenticated company."""
    mappings = get_source_mappings_repo().list_for_company(company_id)
    accounts = get_accounts_repo().list_for_company(company_id)
    pool = sorted(accounts.keys()) if accounts else list(DEFAULT_GL_CATEGORIES)
    return {
        "mappings": [_public_mapping(row) for row in mappings],
        "gl_account_pool": pool,
    }


@router.patch("/source-mappings/{mapping_id}")
@limiter.limit("30/minute")
async def update_source_mapping(
    request: Request,
    mapping_id: str,
    body: UpdateSourceMappingRequest,
    company_id: str = Depends(get_company_id),
):
    gl_account = body.gl_account.strip()
    if not gl_account:
        raise HTTPException(status_code=400, detail=messages.MAPPING_GL_REQUIRED)
    try:
        updated = get_source_mappings_repo().update(
            company_id, mapping_id, gl_account
        )
    except RLSForbiddenError as exc:
        raise HTTPException(status_code=403, detail=messages.FORBIDDEN) from exc
    if updated is None:
        raise HTTPException(status_code=404, detail=messages.MAPPING_NOT_FOUND)
    logger.info(
        "source_mapping_updated",
        extra={"mapping_id": mapping_id, "event": "source_mapping_updated"},
    )
    return _public_mapping(updated)


@router.delete("/source-mappings/{mapping_id}")
@limiter.limit("30/minute")
async def delete_source_mapping(
    request: Request,
    mapping_id: str,
    company_id: str = Depends(get_company_id),
):
    try:
        deleted = get_source_mappings_repo().delete(company_id, mapping_id)
    except RLSForbiddenError as exc:
        raise HTTPException(status_code=403, detail=messages.FORBIDDEN) from exc
    if not deleted:
        raise HTTPException(status_code=404, detail=messages.MAPPING_NOT_FOUND)
    logger.info(
        "source_mapping_deleted",
        extra={"mapping_id": mapping_id, "event": "source_mapping_deleted"},
    )
    return {"status": "deleted", "id": mapping_id}
