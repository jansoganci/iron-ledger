"""Unknown class tokens are dropped; the six-class Literal stays closed."""

from __future__ import annotations

from pathlib import Path

from pydantic import ValidationError

from backend.domain.contracts import (
    ALLOWED_RECONCILIATION_CLASSIFICATIONS,
    NarrativeJSON,
    ReconciliationClassification,
)

PROMPTS = Path("backend/prompts")


def test_live_invented_token_does_not_fail_validation() -> None:
    """Regression for Riverbend run 7636747a / gap 7b.

    Claude fused card_kind 'exception' with nested three-way matches into
    exception_three_way_matches. That string is not a seventh class.
    """
    parsed = NarrativeJSON.model_validate(
        {
            "narrative": "Undeposited Funds shows 1,000.00 unmatched.",
            "numbers_used": [1000.00],
            "reconciliation_classifications": {
                "Undeposited Funds": "exception_three_way_matches",
            },
        }
    )
    assert parsed.narrative.startswith("Undeposited Funds")
    assert parsed.numbers_used == [1000.00]
    assert parsed.reconciliation_classifications == {}


def test_each_of_the_six_tokens_round_trips() -> None:
    tokens = ReconciliationClassification.__args__
    assert len(tokens) == 6
    assert set(tokens) == ALLOWED_RECONCILIATION_CLASSIFICATIONS
    for token in tokens:
        parsed = NarrativeJSON.model_validate(
            {
                "narrative": "Office Rent is 200.00.",
                "numbers_used": [200.00],
                "reconciliation_classifications": {"Office Rent": token},
            }
        )
        assert parsed.reconciliation_classifications == {"Office Rent": token}


def test_mixed_dict_keeps_only_valid_tokens() -> None:
    parsed = NarrativeJSON.model_validate(
        {
            "narrative": "Rent is 200.00 and payroll is 500.00.",
            "numbers_used": [200.00, 500.00],
            "reconciliation_classifications": {
                "Rent": "stale_reference",
                "Undeposited Funds": "exception_three_way_matches",
                "Payroll": "missing_je",
            },
        }
    )
    assert parsed.reconciliation_classifications == {
        "Rent": "stale_reference",
        "Payroll": "missing_je",
    }


def test_non_dict_classifications_still_fail() -> None:
    """Coercion is for unknown tokens, not for a broken JSON shape."""
    try:
        NarrativeJSON.model_validate(
            {
                "narrative": "Revenue was 1000.00.",
                "numbers_used": [1000.00],
                "reconciliation_classifications": ["missing_je"],
            }
        )
    except ValidationError:
        return
    raise AssertionError("expected ValidationError for a list of classes")


def test_monthly_prompts_pin_the_six_tokens_and_omit_matches() -> None:
    tokens = ReconciliationClassification.__args__
    for name in ("narrative_prompt.txt", "narrative_prompt_reinforced.txt"):
        text = (PROMPTS / name).read_text()
        lowered = text.casefold()
        for token in tokens:
            assert token in text, f"{token} is not named in {name}"
        assert "classification string from the taxonomy above" not in lowered
        assert "non-empty" in lowered and "matches" in lowered
        assert "any other string is dropped" in lowered
        assert "seventh class" in lowered
