from __future__ import annotations

from backend.domain.contracts import SendResult
from backend.logger import get_logger

logger = get_logger(__name__)


class ResendEmailSender:
    """EmailSender port backed by Resend. Fully wired on Day 5."""

    def __init__(self, api_key: str, from_email: str) -> None:
        self._api_key = api_key
        self._from_email = from_email

    def send(self, to: str, subject: str, html: str, text: str) -> SendResult:
        # Day 5 stub — wired fully in Day 5.
        logger.warning(
            "ResendEmailSender.send called but not yet wired", extra={"to": to}
        )
        return SendResult(status="failed", message_id="")
