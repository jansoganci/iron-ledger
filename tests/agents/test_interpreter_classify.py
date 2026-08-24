"""Unit tests for interpreter classification merge — no LLM."""

from __future__ import annotations

from backend.agents.interpreter import (
    _apply_reconciliation_classifications,
    _classify_from_hints,
    _is_coverage_item,
)


def test_classify_gl_only_is_not_missing_je() -> None:
    assert _classify_from_hints({"is_gl_only": True}) is None


def test_classify_source_only_is_missing_je() -> None:
    assert _classify_from_hints({"is_source_only": True}) == "missing_je"


def test_is_coverage_from_card_kind() -> None:
    assert _is_coverage_item({"card_kind": "coverage", "hints": {}}) is True


def test_is_coverage_from_gl_only_hint() -> None:
    assert _is_coverage_item({"hints": {"is_gl_only": True}}) is True


def test_apply_classifications_ignores_claude_on_coverage() -> None:
    items = [
        {
            "account": "Rent",
            "card_kind": "coverage",
            "hints": {"is_gl_only": True},
            "classification": None,
        },
        {
            "account": "Bonus",
            "card_kind": "exception",
            "hints": {"is_source_only": True},
            "classification": None,
        },
    ]
    _apply_reconciliation_classifications(
        items, {"Rent": "missing_je", "Bonus": "missing_je"}
    )
    assert items[0]["classification"] is None
    assert items[0]["card_kind"] == "coverage"
    assert items[1]["classification"] == "missing_je"
