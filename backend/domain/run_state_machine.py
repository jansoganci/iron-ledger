from __future__ import annotations

from enum import Enum

from backend.domain.errors import InvalidRunTransition


class RunStatus(str, Enum):
    PENDING = "pending"
    PARSING = "parsing"
    DISCOVERING = "discovering"
    AWAITING_DISCOVERY_CONFIRMATION = "awaiting_discovery_confirmation"
    MAPPING = "mapping"
    AWAITING_MAPPING_CONFIRMATION = "awaiting_mapping_confirmation"
    APPLYING_MAPPING = "applying_mapping"
    AWAITING_CONFIRMATION = "awaiting_confirmation"
    COMPARING = "comparing"
    GENERATING = "generating"
    COMPLETE = "complete"
    UPLOAD_FAILED = "upload_failed"
    PARSING_FAILED = "parsing_failed"
    GUARDRAIL_FAILED = "guardrail_failed"


# Terminal states have empty allowed-next sets.
# PARSING → MAPPING was removed: Discovery is now mandatory on every run.
# Any stale caller will raise InvalidRunTransition (deliberate — fail loud).
_ALLOWED: dict[RunStatus, frozenset[RunStatus]] = {
    RunStatus.PENDING: frozenset({RunStatus.PARSING, RunStatus.UPLOAD_FAILED}),
    RunStatus.PARSING: frozenset(
        {
            RunStatus.DISCOVERING,
            RunStatus.AWAITING_MAPPING_CONFIRMATION,
            RunStatus.AWAITING_CONFIRMATION,
            RunStatus.PARSING_FAILED,
        }
    ),
    RunStatus.AWAITING_MAPPING_CONFIRMATION: frozenset(
        {RunStatus.APPLYING_MAPPING, RunStatus.PARSING_FAILED}
    ),
    RunStatus.APPLYING_MAPPING: frozenset(
        {RunStatus.AWAITING_CONFIRMATION, RunStatus.PARSING_FAILED}
    ),
    RunStatus.DISCOVERING: frozenset(
        {
            RunStatus.MAPPING,
            RunStatus.AWAITING_DISCOVERY_CONFIRMATION,
            RunStatus.PARSING_FAILED,
        }
    ),
    RunStatus.AWAITING_DISCOVERY_CONFIRMATION: frozenset(
        {RunStatus.MAPPING, RunStatus.PARSING_FAILED}
    ),
    RunStatus.MAPPING: frozenset(
        {RunStatus.AWAITING_CONFIRMATION, RunStatus.PARSING_FAILED}
    ),
    RunStatus.AWAITING_CONFIRMATION: frozenset(
        {RunStatus.COMPARING, RunStatus.PARSING_FAILED}
    ),
    RunStatus.COMPARING: frozenset({RunStatus.GENERATING, RunStatus.PARSING_FAILED}),
    RunStatus.GENERATING: frozenset({RunStatus.COMPLETE, RunStatus.GUARDRAIL_FAILED}),
    RunStatus.COMPLETE: frozenset(),
    RunStatus.UPLOAD_FAILED: frozenset(),
    RunStatus.PARSING_FAILED: frozenset(),
    RunStatus.GUARDRAIL_FAILED: frozenset(),
}


class RunStateMachine:
    @staticmethod
    def transition(current: RunStatus | str, new: RunStatus | str) -> RunStatus:
        current = RunStatus(current)
        new = RunStatus(new)
        if new not in _ALLOWED.get(current, frozenset()):
            raise InvalidRunTransition(
                f"Cannot transition run from '{current}' to '{new}'"
            )
        return new
