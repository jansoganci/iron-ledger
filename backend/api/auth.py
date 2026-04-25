from __future__ import annotations

import time

import httpx
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from backend import messages
from backend.domain.errors import RLSForbiddenError
from backend.logger import get_logger
from backend.settings import get_settings

logger = get_logger(__name__)
_bearer = HTTPBearer()

# Two-layer TTL cache — pure Python dicts, zero infrastructure.
# Safe for single-process uvicorn; each worker caches independently in multi-worker.
_token_cache: dict[str, tuple[str, float]] = {}  # token → (user_id, expires_at)
_company_cache: dict[str, tuple[dict, float]] = (
    {}
)  # user_id → (company_dict, expires_at)
_TOKEN_TTL = 30.0  # seconds — conservative window for token revocation
_COMPANY_TTL = 300.0  # seconds — company row is immutable within a session


async def _validate_jwt(token: str) -> str:
    """Call Supabase /auth/v1/user with the user's JWT. Returns user_id.

    Async so it does not block the event loop.
    Works with both HS256 and ES256 — no local key management needed.
    """
    s = get_settings()
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{s.supabase_url}/auth/v1/user",
                headers={
                    "Authorization": f"Bearer {token}",
                    "apikey": s.supabase_anon_key,
                },
                timeout=10.0,
            )
    except httpx.RequestError as exc:
        logger.warning("supabase auth unreachable", extra={"error": str(exc)})
        raise HTTPException(status_code=401, detail=messages.UNAUTHORIZED) from exc

    if resp.status_code != 200:
        logger.warning(
            "jwt rejected by supabase",
            extra={"status": resp.status_code},
        )
        raise HTTPException(status_code=401, detail=messages.UNAUTHORIZED)

    return resp.json()["id"]


async def get_current_user(
    creds: HTTPAuthorizationCredentials = Depends(_bearer),
) -> str:
    """Validate Supabase JWT and return user_id. Result cached for _TOKEN_TTL seconds."""
    token = creds.credentials
    entry = _token_cache.get(token)
    if entry and entry[1] > time.monotonic():
        return entry[0]

    user_id = await _validate_jwt(token)
    _token_cache[token] = (user_id, time.monotonic() + _TOKEN_TTL)
    return user_id


async def get_company_id(user_id: str = Depends(get_current_user)) -> str:
    """Resolve company_id from user_id via companies.owner_id. Result cached for _COMPANY_TTL seconds.

    Never accepts company_id from the client.
    """
    entry = _company_cache.get(user_id)
    if entry and entry[1] > time.monotonic():
        return entry[0]["id"]

    from backend.api.deps import get_companies_repo

    repo = get_companies_repo()
    try:
        company = repo.get_by_owner(user_id)
    except RLSForbiddenError as exc:
        raise HTTPException(status_code=403, detail=messages.FORBIDDEN) from exc

    _company_cache[user_id] = (company, time.monotonic() + _COMPANY_TTL)
    return company["id"]


async def get_cached_company(user_id: str = Depends(get_current_user)) -> dict:
    """Return the full company dict for the authenticated user. Result cached for _COMPANY_TTL seconds.

    Shares _company_cache with get_company_id — one DB call warms both.
    """
    entry = _company_cache.get(user_id)
    if entry and entry[1] > time.monotonic():
        return entry[0]

    from backend.api.deps import get_companies_repo

    repo = get_companies_repo()
    try:
        company = repo.get_by_owner(user_id)
    except RLSForbiddenError as exc:
        raise HTTPException(status_code=403, detail=messages.FORBIDDEN) from exc

    _company_cache[user_id] = (company, time.monotonic() + _COMPANY_TTL)
    return company
