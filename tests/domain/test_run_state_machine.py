"""State machine tests for AWAITING_MAPPING_CONFIRMATION transitions."""

from __future__ import annotations

import pytest

from backend.domain.errors import InvalidRunTransition
from backend.domain.run_state_machine import RunStateMachine, RunStatus


def test_parsing_to_awaiting_mapping_confirmation_valid() -> None:
    result = RunStateMachine.transition(
        RunStatus.PARSING, RunStatus.AWAITING_MAPPING_CONFIRMATION
    )
    assert result == RunStatus.AWAITING_MAPPING_CONFIRMATION


def test_awaiting_mapping_confirmation_to_comparing_raises() -> None:
    with pytest.raises(InvalidRunTransition):
        RunStateMachine.transition(
            RunStatus.AWAITING_MAPPING_CONFIRMATION, RunStatus.COMPARING
        )
