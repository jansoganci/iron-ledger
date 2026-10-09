"""Which upload folders are old enough to delete. No I/O, no clock.

Uploads live at "{user_id}/{period}/{filename}", so every run for one
company and month shares a folder. A folder is stale only when the newest
run for that company and month has not moved for `RETENTION`. Anything we
cannot read (bad key, missing timestamp) is kept.
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

RETENTION = timedelta(days=7)

_PERIOD = re.compile(r"^\d{4}-\d{2}-\d{2}$")


@dataclass(frozen=True)
class SweepFolder:
    company_id: str
    period: str
    folder: str


def folder_for_key(storage_key: str | None, period: str) -> str | None:
    """Folder "{user_id}/{period}" for a well-formed key of that period, else None."""
    parts = str(storage_key or "").split("/")
    if len(parts) != 3 or not all(parts):
        return None
    user_id, key_period, _ = parts
    try:
        uuid.UUID(user_id)
        date.fromisoformat(key_period)
    except ValueError:
        return None
    if not _PERIOD.match(key_period) or key_period != str(period):
        return None
    return f"{user_id}/{key_period}"


def parse_timestamp(value: object) -> datetime | None:
    """Supabase TIMESTAMP (naive UTC) or ISO string with offset → aware UTC."""
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def last_activity(row: dict | None) -> datetime | None:
    """Latest of created_at / updated_at; None when neither is readable."""
    if not row:
        return None
    stamps = [parse_timestamp(row.get(k)) for k in ("created_at", "updated_at")]
    known = [s for s in stamps if s is not None]
    return max(known) if known else None


def is_stale(activity: datetime | None, now: datetime) -> bool:
    return activity is not None and now - activity > RETENTION


def folders_to_sweep(rows: list[dict], now: datetime) -> list[SweepFolder]:
    """Folders whose newest run for the company and month is past retention."""
    newest: dict[tuple[str, str], datetime | None] = {}
    folders: dict[tuple[str, str], set[str]] = {}
    for row in rows:
        company_id = str(row.get("company_id") or "")
        period = str(row.get("period") or "")
        if not company_id or not period:
            continue
        group = (company_id, period)
        activity = last_activity(row)
        if group not in newest:
            newest[group] = activity
        elif newest[group] is not None:
            newest[group] = None if activity is None else max(newest[group], activity)
        folder = folder_for_key(row.get("storage_key"), period)
        if folder:
            folders.setdefault(group, set()).add(folder)

    in_use = {
        folder
        for group, names in folders.items()
        if not is_stale(newest.get(group), now)
        for folder in names
    }
    result: list[SweepFolder] = []
    for group, names in sorted(folders.items()):
        if not is_stale(newest.get(group), now):
            continue
        for folder in sorted(names - in_use):
            result.append(SweepFolder(group[0], group[1], folder))
    return result
