from __future__ import annotations

"""Consent flag for replacing a verified monthly report.

Stored on the run's parse_preview JSONB under a reserved key so we do not
need a new column (no SQL in this slice). Parser writes to parse_preview
later; the runs adapter re-attaches this key when that happens.
"""

REGENERATE_PREVIEW_KEY = "_regenerate"


def run_wants_regenerate(run: dict | None) -> bool:
    if not isinstance(run, dict):
        return False
    preview = run.get("parse_preview")
    return bool(
        isinstance(preview, dict) and preview.get(REGENERATE_PREVIEW_KEY) is True
    )


def attach_regenerate_flag(preview: dict | None, *, regenerate: bool) -> dict:
    payload = dict(preview or {})
    if regenerate:
        payload[REGENERATE_PREVIEW_KEY] = True
    else:
        payload.pop(REGENERATE_PREVIEW_KEY, None)
    return payload


def strip_regenerate_flag(preview: dict | None) -> dict | None:
    if not isinstance(preview, dict):
        return preview
    payload = dict(preview)
    payload.pop(REGENERATE_PREVIEW_KEY, None)
    return payload
