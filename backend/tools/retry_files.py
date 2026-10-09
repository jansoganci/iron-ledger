"""Which stored files a Retry may re-run. No I/O.

A multi-file analysis stores every storage key in parse_preview["storage_keys"].
Retry reads that list. A list is accepted only when every key sits in this
user's folder for the run's period, so a damaged record cannot point at
another company's file. Older multi-file runs have no list; they are refused
instead of silently re-running the first file alone.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class RetryFiles:
    """keys is empty when refusal is set. refusal is "reupload" or "no_file"."""

    keys: tuple[str, ...] = ()
    refusal: str | None = None


def _owned(key: object, user_id: str, period: date) -> bool:
    parts = str(key).split("/")
    if len(parts) != 3 or not all(parts) or ".." in parts:
        return False
    return parts[0] == user_id and parts[1] == period.isoformat()


def files_for_retry(run: dict, user_id: str, period: date) -> RetryFiles:
    preview = run.get("parse_preview")
    preview = preview if isinstance(preview, dict) else {}
    if "storage_keys" in preview:
        stored = preview["storage_keys"]
        if (
            isinstance(stored, list)
            and stored
            and all(_owned(key, user_id, period) for key in stored)
        ):
            return RetryFiles(keys=tuple(stored))
        return RetryFiles(refusal="reupload")

    count = run.get("file_count")
    try:
        many = int(count) > 1
    except (TypeError, ValueError):
        many = False
    if many:
        return RetryFiles(refusal="reupload")

    key = run.get("storage_key")
    if not isinstance(key, str) or not key:
        return RetryFiles(refusal="no_file")
    return RetryFiles(keys=(key,))
