from __future__ import annotations

import random
import time

import httpx
from supabase import Client

from backend.domain.errors import TransientIOError
from backend.logger import get_logger

logger = get_logger(__name__)

_BUCKET = "financial-uploads"
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
                        "content-type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
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
        return self._client.storage.from_(_BUCKET).download(storage_key)

    def delete(self, storage_key: str) -> None:
        self._client.storage.from_(_BUCKET).remove([storage_key])
