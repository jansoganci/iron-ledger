"""Period lock guard. A closed month is read-only until it is reopened.

Fails closed: if the lock cannot be read, the write is refused (503) rather
than allowed through.
"""

from __future__ import annotations

from datetime import date

from fastapi import HTTPException

from backend import messages
from backend.api.deps import get_period_closes_repo
from backend.domain.errors import TransientIOError


def ensure_period_open(company_id: str, period: date) -> None:
    try:
        active = get_period_closes_repo().get_active(company_id, period)
    except TransientIOError as exc:
        raise HTTPException(status_code=503, detail=messages.INTERNAL_ERROR) from exc
    if active is not None:
        raise HTTPException(status_code=409, detail=messages.PERIOD_CLOSED)


def is_period_closed(company_id: str, period: date) -> bool:
    """Non-raising variant for background tasks. Unreadable lock counts as closed."""
    try:
        return get_period_closes_repo().get_active(company_id, period) is not None
    except TransientIOError:
        return True
