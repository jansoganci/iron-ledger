"""Unit tests for guardrail.py.

Two paths are under test:

* **strict=True** — the corrected guardrail. Unit-aware reference pools, money
  at cent precision, percentages at 0.05pp, zero references retained, plus the
  Stage 1 narrative consistency check. This is what the Interpreter uses.
* **strict=False (legacy)** — the old max(1% , $1,000) single-pool behaviour,
  retained ONLY for callers not yet migrated (quarterly.py, opus_upgrade.py).
  Its tests are kept so the un-migrated path stays pinned, and are named so no
  one mistakes them for the intended behaviour of new call sites.
"""

from __future__ import annotations

import pytest

from backend.tools import guardrail as guardrail_module
from backend.tools.guardrail import (
    _tolerance_for,
    check_narrative_consistency,
    money_tolerance,
    parse_narrative_numbers,
    pct_tolerance,
    verify_guardrail,
)


# ---------------------------------------------------------------------------
# LEGACY path — pinned for quarterly.py / opus_upgrade.py only.
# Do not treat these as the desired behaviour; see module docstring.
# ---------------------------------------------------------------------------


def test_legacy_tolerance_for_small_value_uses_dollar_floor() -> None:
    assert _tolerance_for(200.0) == 1_000.0


def test_legacy_tolerance_for_large_value_uses_percentage() -> None:
    assert _tolerance_for(500_000.0) == 5_000.0


def test_legacy_tolerance_for_boundary_value() -> None:
    assert _tolerance_for(100_000.0) == 1_000.0


def test_legacy_tolerance_for_negative_value_uses_absolute() -> None:
    assert _tolerance_for(-500_000.0) == 5_000.0


def test_legacy_path_still_accepts_dollar_floor_drift() -> None:
    """Documents the known looseness of the un-migrated path."""
    passed, _ = verify_guardrail({"numbers_used": [500.0]}, {"revenue": 487.0})
    assert passed is True


# ---------------------------------------------------------------------------
# STRICT tolerance — money
# ---------------------------------------------------------------------------


def test_money_tolerance_is_cent_precision_for_small_values() -> None:
    assert money_tolerance(200.0) == 0.01
    assert money_tolerance(-200.0) == 0.01


def test_money_tolerance_relative_term_binds_only_on_large_values() -> None:
    # 1e-6 x 1,000,000 = 1.00, which exceeds the $0.01 floor
    assert money_tolerance(1_000_000.0) == pytest.approx(1.0)


def test_strict_rejects_rounding_that_legacy_allowed() -> None:
    # Claude writes 500.00, pandas says 487.00. The prompt forbids rounding;
    # legacy accepted it, strict does not.
    passed, msg = verify_guardrail(
        {"numbers_used": [500.0]}, {"revenue": 487.0}, strict=True
    )
    assert passed is False
    assert "Mismatch" in msg


def test_strict_accepts_verbatim_copy() -> None:
    passed, msg = verify_guardrail(
        {"numbers_used": [487.0, 1_490.0]},
        {"a": 487.0, "b": 1_490.0},
        strict=True,
    )
    assert passed is True
    assert msg == "Success"


def test_strict_accepts_cent_level_float_noise() -> None:
    passed, _ = verify_guardrail(
        {"numbers_used": [1_234.57]}, {"a": 1_234.5678}, strict=True
    )
    assert passed is True


def test_strict_rejects_large_value_drift_legacy_allowed() -> None:
    # $40,000 drift on $4.76M passed under the 1% rule.
    passed, _ = verify_guardrail(
        {"numbers_used": [4_800_000.0]}, {"revenue": 4_760_000.0}, strict=True
    )
    assert passed is False


# ---------------------------------------------------------------------------
# STRICT tolerance — percentages and unit separation
# ---------------------------------------------------------------------------


def test_pct_tolerance_is_five_hundredths_of_a_point() -> None:
    assert pct_tolerance(61.07) == 0.05


def test_strict_accepts_one_decimal_rendering_of_a_percentage() -> None:
    # 61.07 -> "61.1%" is a 0.03pp delta, inside the 0.05pp allowance.
    passed, _ = verify_guardrail(
        {"numbers_used": [61.1]},
        {"accounts": {"Travel": {"variance_pct": 61.07}}},
        strict=True,
    )
    assert passed is True


def test_strict_rejects_a_fabricated_percentage() -> None:
    passed, _ = verify_guardrail(
        {"numbers_used": [72.0]},
        {"accounts": {"Travel": {"variance_pct": 61.07}}},
        strict=True,
    )
    assert passed is False


def test_percentage_reference_does_not_create_a_dollar_pass_band() -> None:
    """The core regression: a variance_pct must not whitelist dollar values.

    Under the old max(1%, $1,000) rule a variance_pct of 14.47 accepted any
    claimed value from -985 to 1014.
    """
    summary = {"accounts": {"Salaries": {"variance_pct": 14.47}}}
    for invented in (999.0, 750.0, 500.0, 45.0):
        passed, _ = verify_guardrail({"numbers_used": [invented]}, summary, strict=True)
        assert passed is False, f"{invented} should not match a percentage"

    # And the same values sail through the legacy path — this is the bug.
    for invented in (999.0, 750.0, 500.0, 45.0):
        passed, _ = verify_guardrail({"numbers_used": [invented]}, summary)
        assert passed is True


def test_money_reference_does_not_widen_percentage_matching() -> None:
    # A $2,400.00 money reference must not validate a claimed 2,400.03 percent
    # value via the percentage tolerance path.
    summary = {"accounts": {"Travel": {"current": 2_400.0}}}
    passed, _ = verify_guardrail({"numbers_used": [2_400.03]}, summary, strict=True)
    assert passed is False


# ---------------------------------------------------------------------------
# STRICT — zero handling
# ---------------------------------------------------------------------------


def test_strict_accepts_zero_against_a_real_zero_reference() -> None:
    passed, _ = verify_guardrail(
        {"numbers_used": [0.0]},
        {"accounts": {"Fees": {"current": 0.0, "historical_avg": 600.0}}},
        strict=True,
    )
    assert passed is True


def test_strict_rejects_zero_when_no_zero_reference_exists() -> None:
    passed, _ = verify_guardrail(
        {"numbers_used": [0.0]}, {"a": 10_000.0, "b": 500.0}, strict=True
    )
    assert passed is False


# ---------------------------------------------------------------------------
# Narrative token parser
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "text,money,pcts",
    [
        ("Travel is 61.07% above average of 1,490.00.", [1_490.0], [61.07]),
        ("G&A is -34.00% below average.", [], [-34.0]),
        ("4 items were within normal range.", [], []),
        ("the period closed on 2026-03-31.", [], []),
        ("Bank Charges of $95 and software at $890.50.", [95.0, 890.5], []),
        ("We found $999,999 missing.", [999_999.0], []),
        ("shows a 0.00 fee and a 600.00 payout.", [0.0, 600.0], []),
        ("6-period average of 38,000.00.", [38_000.0], []),
        ("Account 4500 had 250.00 booked.", [250.0], []),
    ],
)
def test_parse_narrative_numbers(text, money, pcts) -> None:
    got_money, got_pct = parse_narrative_numbers(text)
    assert got_money == money
    assert got_pct == pcts


def test_parser_ignores_dates_ordinals_and_counts() -> None:
    """Regression: a naive every-token parser produced six false positives."""
    text = (
        "March 2026 close. Travel is 61.07% above its 3-period average of "
        "1,490.00, at 2,400.00. 4 items were within normal range. The period "
        "closed on 2026-03-31."
    )
    money, pcts = parse_narrative_numbers(text)
    assert money == [1_490.0, 2_400.0]
    assert pcts == [61.07]


# ---------------------------------------------------------------------------
# Stage 1 — narrative consistency (WARN-ONLY this release)
# ---------------------------------------------------------------------------
#
# Replaces the former test_empty_numbers_used_always_passes, which pinned the
# bypass as intended behaviour. Empty numbers_used no longer means "always
# passes" unconditionally: it passes only when the narrative contains no
# numbers, and an unlisted narrative number is now detected and logged.


def test_empty_numbers_used_passes_when_narrative_has_no_numbers() -> None:
    passed, msg = verify_guardrail(
        {"numbers_used": [], "narrative": "Nothing unusual this month."},
        {"revenue": 1_000_000.0},
        strict=True,
    )
    assert passed is True
    assert msg == "Success"


def test_empty_numbers_used_with_narrative_number_is_detected() -> None:
    """The audit's $999,999 bypass is now detected."""
    claude_json = {
        "numbers_used": [],
        "narrative": "We found $999,999 missing.",
    }
    violations = check_narrative_consistency(claude_json)
    assert len(violations) == 1
    assert violations[0]["value"] == 999_999.0
    assert violations[0]["unit"] == "money"
    assert "999,999" in violations[0]["excerpt"]


def test_narrative_violation_is_warn_only_by_default() -> None:
    """Decision 3: measure the violation rate before enforcing."""
    assert guardrail_module.ENFORCE_NARRATIVE_CONSISTENCY is False
    passed, _ = verify_guardrail(
        {"numbers_used": [], "narrative": "We found $999,999 missing."},
        {"revenue": 1_000_000.0},
        strict=True,
    )
    assert passed is True


def test_narrative_violation_fails_when_enforcement_is_enabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Flipping the named flag turns Stage 1 into a hard failure."""
    monkeypatch.setattr(guardrail_module, "ENFORCE_NARRATIVE_CONSISTENCY", True)
    passed, msg = verify_guardrail(
        {"numbers_used": [], "narrative": "We found $999,999 missing."},
        {"revenue": 1_000_000.0},
        strict=True,
    )
    assert passed is False
    assert "999999" in msg.replace(",", "") or "999999.0" in msg.replace(",", "")


def test_narrative_number_present_in_numbers_used_is_not_a_violation() -> None:
    claude_json = {
        "numbers_used": [2_400.0, 61.07],
        "narrative": "Travel is 61.07% above average, at 2,400.00 this month.",
    }
    assert check_narrative_consistency(claude_json) == []


# ---------------------------------------------------------------------------
# Reconciliation reference values
# ---------------------------------------------------------------------------


def test_reconciliation_values_extend_the_money_pool() -> None:
    passed, _ = verify_guardrail(
        {"numbers_used": [5_420.0]},
        {"accounts": {"Payroll": {"current": 10_920.0}}},
        reconciliation_values=[5_420.0],
        strict=True,
    )
    assert passed is True


def test_mismatch_returns_false_with_message() -> None:
    passed, msg = verify_guardrail(
        {"numbers_used": [999_999.0]}, {"revenue": 1.0}, strict=True
    )
    assert passed is False
    assert "Mismatch" in msg
