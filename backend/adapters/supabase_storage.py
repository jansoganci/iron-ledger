from __future__ import annotations

import random
import time

import httpx
from storage3.utils import StorageException
from supabase import Client

from backend.domain.errors import StoredFileMissing, TransientIOError
from backend.logger import get_logger

logger = get_logger(__name__)

_BUCKET = "financial-uploads"
_LIST_PAGE = 100
_BACKOFF = (0.5, 1.5, 4.0)
_JITTER = 0.20  # ±20%


def _jitter(seconds: float) -> float:
    return seconds * (1 + random.uniform(-_JITTER, _JITTER))


class SupabaseFileStorage:
    def __init__(self, client: Client) -> None:
        self._client = client

    def _storage_key(self, user_id: str, period: str, filename: str) -> str:
        return f"{user_id}/{period}/{filename}"

    def upload(
        self,
        user_id: str,
        period: str,
        filename: str,
        data: bytes,
    ) -> str:
        key = self._storage_key(user_id, period, filename)
        last_exc: Exception | None = None

        for attempt, backoff in enumerate(_BACKOFF):
            try:
                self._client.storage.from_(_BUCKET).upload(
                    key,
                    data,
                    file_options={
                        "content-type": (
                            "application/vnd.openxmlformats-officedocument"
                            ".spreadsheetml.sheet"
                        ),
                        "upsert": "true",
                    },
                )
                logger.info(
                    "storage upload succeeded",
                    extra={"storage_key": key, "attempt": attempt + 1},
                )
                return key
            except (httpx.ConnectError, httpx.ReadTimeout) as exc:
                last_exc = exc
                logger.warning(
                    "storage upload transient error, retrying",
                    extra={
                        "storage_key": key,
                        "attempt": attempt + 1,
                        "error": str(exc),
                    },
                )
                if attempt < len(_BACKOFF) - 1:
                    time.sleep(_jitter(backoff))
            except Exception as exc:
                # Non-retryable (4xx, auth, quota) — surface immediately.
                logger.error(
                    "storage upload non-retryable error",
                    extra={"storage_key": key, "error": str(exc)},
                )
                raise TransientIOError(str(exc)) from exc

        raise TransientIOError(
            f"Storage upload failed after {len(_BACKOFF)} attempts: {last_exc}"
        )

    def download(self, storage_key: str) -> bytes:
        try:
            return self._client.storage.from_(_BUCKET).download(storage_key)
        except StorageException as exc:
            if _is_not_found(exc):
                raise StoredFileMissing(storage_key) from exc
            raise

    def delete(self, storage_key: str) -> None:
        self._client.storage.from_(_BUCKET).remove([storage_key])

    def list_folder(self, folder: str) -> list[str]:
        prefix = folder.strip("/")
        if not prefix:
            raise ValueError("refusing to list the bucket root")
        bucket = self._client.storage.from_(_BUCKET)
        keys: list[str] = []
        offset = 0
        while True:
            page = bucket.list(prefix, {"limit": _LIST_PAGE, "offset": offset})
            for entry in page or []:
                # Sub-folders come back with id None; only files are swept.
                if entry.get("id") and entry.get("name"):
                    keys.append(f"{prefix}/{entry['name']}")
            if not page or len(page) < _LIST_PAGE:
                return keys
            offset += _LIST_PAGE

    def delete_many(self, storage_keys: list[str]) -> None:
        bucket = self._client.storage.from_(_BUCKET)
        for start in range(0, len(storage_keys), _LIST_PAGE):
            end = start + _LIST_PAGE
            bucket.remove(storage_keys[start:end])


def _is_not_found(exc: StorageException) -> bool:
    payload = exc.args[0] if exc.args and isinstance(exc.args[0], dict) else {}
    if str(payload.get("statusCode")) == "404":
        return True
    error = str(payload.get("error") or "").lower().replace(" ", "_")
    return error == "not_found"
