"""Unit tests for guardrail.py — Track 4 tolerance changes."""

from __future__ import annotations

import pytest

from backend.tools.guardrail import _tolerance_for, verify_guardrail


# ---------------------------------------------------------------------------
# _tolerance_for
# ---------------------------------------------------------------------------


def test_tolerance_for_small_value_uses_dollar_floor() -> None:
    # 1% of $200 = $2 — below the $1,000 floor, so tolerance must be $1,000
    assert _tolerance_for(200.0) == 1_000.0


def test_tolerance_for_large_value_uses_percentage() -> None:
    # 1% of $500,000 = $5,000 — above the $1,000 floor
    assert _tolerance_for(500_000.0) == 5_000.0


def test_tolerance_for_boundary_value() -> None:
    # 1% of $100,000 = $1,000 — exactly at the boundary, should be $1,000
    assert _tolerance_for(100_000.0) == 1_000.0


def test_tolerance_for_negative_value_uses_absolute() -> None:
    # Tolerance should be symmetric — negative sign must not affect result
    assert _tolerance_for(-500_000.0) == 5_000.0


# ---------------------------------------------------------------------------
# verify_guardrail — small amounts (dollar-floor behaviour)
# ---------------------------------------------------------------------------


def test_small_value_within_dollar_floor_passes() -> None:
    # Claude writes 500, pandas says 487 — delta $13 < $1,000 floor → pass
    passed, msg = verify_guardrail(
        {"numbers_used": [500.0]},
        {"revenue": 487.0},
    )
    assert passed is True


def test_small_value_outside_dollar_floor_fails() -> None:
    # Claude writes 500, pandas says 1_600 — delta $1,100 > $1,000 floor → fail
    passed, _ = verify_guardrail(
        {"numbers_used": [500.0]},
        {"revenue": 1_600.0},
    )
    assert passed is False


# ---------------------------------------------------------------------------
# verify_guardrail — large amounts (percentage behaviour)
# ---------------------------------------------------------------------------


def test_large_value_within_one_pct_passes() -> None:
    # Claude writes 4_800_000, pandas says 4_760_000 — delta $40,000 < 1% of 4.76M ($47,600) → pass
    passed, _ = verify_guardrail(
        {"numbers_used": [4_800_000.0]},
        {"revenue": 4_760_000.0},
    )
    assert passed is True


def test_large_value_beyond_one_pct_fails() -> None:
    # Claude writes 4_800_000, pandas says 4_700_000 — delta $100,000 > 1% of 4.7M ($47,000) → fail
    passed, _ = verify_guardrail(
        {"numbers_used": [4_800_000.0]},
        {"revenue": 4_700_000.0},
    )
    assert passed is False


# ---------------------------------------------------------------------------
# verify_guardrail — success path
# ---------------------------------------------------------------------------


def test_all_numbers_matched_returns_success_tuple() -> None:
    passed, msg = verify_guardrail(
        {"numbers_used": [100_000.0, 200_000.0]},
        {"a": 100_000.0, "b": 200_000.0},
    )
    assert passed is True
    assert msg == "Success"


def test_empty_numbers_used_always_passes() -> None:
    passed, msg = verify_guardrail(
        {"numbers_used": []},
        {"revenue": 1_000_000.0},
    )
    assert passed is True


def test_mismatch_returns_false_with_message() -> None:
    passed, msg = verify_guardrail(
        {"numbers_used": [999_999.0]},
        {"revenue": 1.0},
    )
    assert passed is False
    assert "Mismatch" in msg
