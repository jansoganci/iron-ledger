from __future__ import annotations


class TransientIOError(Exception):
    """Adapter exhausted retries on a network/5xx failure."""


class DuplicateEntryError(Exception):
    """Unique-constraint violation on monthly_entries(company_id, account_id, period)."""


class RLSForbiddenError(Exception):
    """RLS denied the row — user does not own the requested resource."""


class GuardrailError(Exception):
    """Interpreter produced numbers not in PandasSummary after 2 attempts."""


class InvalidRunTransition(Exception):
    """RunStateMachine.transition() called with an illegal state move."""


class FileHasNoValidColumns(Exception):
    """PII sanitizer stripped all columns — nothing left to process."""


class MappingAmbiguous(Exception):
    """Haiku returned <80% confidence on one or more columns."""


class DiscoveryFailed(Exception):
    """Discovery could not produce a valid plan after semantic retry."""


class DiscoveryLowConfidence(Exception):
    """Plan confidence < 0.80 — run halts at awaiting_confirmation.

    Carries the plan so the caller can persist it before halting.
    """

    def __init__(self, plan, message: str = "") -> None:
        super().__init__(message or "Discovery confidence below threshold")
        self.plan = plan
