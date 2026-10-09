"""Delete upload folders abandoned for longer than the retention window.

Complete runs already delete their first file. This sweep removes what is
left: guardrail_failed files once Retry has gone quiet, other failed or
abandoned runs, and the extra files of multi-file uploads. Logs carry counts
and ids only, never filenames or file contents.
"""

from __future__ import annotations

from datetime import date, datetime, timezone

from backend.domain.ports import FileStorage, RunsRepo
from backend.logger import get_logger
from backend.tools.storage_sweep_rule import folders_to_sweep, is_stale, last_activity

logger = get_logger(__name__)


def sweep_abandoned_uploads(
    runs_repo: RunsRepo,
    storage: FileStorage,
    now: datetime | None = None,
) -> dict[str, int]:
    now = now or datetime.now(timezone.utc)
    candidates = folders_to_sweep(runs_repo.list_runs_with_storage_key(), now)
    counts = {
        "candidates": len(candidates),
        "folders_deleted": 0,
        "files_deleted": 0,
        "skipped_recent": 0,
        "failed": 0,
    }
    for candidate in candidates:
        try:
            # Second read: a new upload may have started since the list.
            latest = runs_repo.latest_run_activity(
                candidate.company_id, date.fromisoformat(candidate.period)
            )
            if not is_stale(last_activity(latest), now):
                counts["skipped_recent"] += 1
                continue
            keys = storage.list_folder(candidate.folder)
            if not keys:
                continue
            storage.delete_many(keys)
            counts["folders_deleted"] += 1
            counts["files_deleted"] += len(keys)
        except Exception as exc:
            counts["failed"] += 1
            logger.warning(
                "storage_sweep_folder_failed",
                extra={
                    "company_id": candidate.company_id,
                    "period": candidate.period,
                    "error_type": type(exc).__name__,
                },
            )
    logger.info("storage_sweep_complete", extra={"event": "storage_sweep", **counts})
    return counts
