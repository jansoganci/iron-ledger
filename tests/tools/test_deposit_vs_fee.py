"""Prove deposit vs fee hints fire on the isolated fixture — pandas only."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from backend.agents.interpreter import (
    _apply_reconciliation_classifications,
    _classify_from_hints,
)
from backend.tools.hint_computer import compute_hints
from tests.tools.deposit_vs_fee_fixture import (
    BANK_CHARGES_GL,
    DEPOSIT_DELTA,
    DEPOSIT_GL,
    DEPOSIT_PCT,
    DEPOSIT_SOURCE,
    FEE_DELTA,
    FEE_GL,
    FEE_NET,
    FEE_PCT,
    PERIOD,
    VANDELAY_TIMING_PCT,
    bank_charges_gl_only_item,
    deposit_consolidated,
    deposit_item,
    deposit_raw_dfs,
    fee_consolidated,
    fee_item,
    fee_raw_dfs,
)

PROMPT = Path("backend/prompts/narrative_prompt.txt").read_text()


def test_deposit_fixture_ratio_is_half() -> None:
    assert DEPOSIT_SOURCE / DEPOSIT_GL == 0.5
    assert abs(DEPOSIT_DELTA) == 4_000.0
    assert DEPOSIT_PCT == -0.5


def test_fee_fixture_clears_and_gate_and_fee_band() -> None:
    assert abs(FEE_DELTA) == 3_500.0  # > $500 AND-gate
    assert 0.03 <= abs(round(FEE_PCT, 4)) <= 0.08
    assert VANDELAY_TIMING_PCT < 0.03


def test_customer_deposit_hint_fires() -> None:
    hints = compute_hints(
        deposit_item(), deposit_consolidated(), PERIOD, deposit_raw_dfs()
    )
    assert hints.is_customer_deposit is True
    assert hints.is_round_fraction is True
    assert hints.is_processor_fee_gap is False
    assert hints.is_gl_only is False
    assert hints.is_source_only is False


def test_processor_fee_hint_fires() -> None:
    hints = compute_hints(fee_item(), fee_consolidated(), PERIOD, fee_raw_dfs())
    assert hints.is_processor_fee_gap is True
    assert hints.is_customer_deposit is False
    assert hints.is_round_fraction is False
    assert hints.is_gl_only is False
    assert hints.is_source_only is False


def test_bank_charges_95_is_not_a_fee_gap() -> None:
    item = bank_charges_gl_only_item()
    raw = {
        "gl_export.xlsx": pd.DataFrame(
            {"account": ["Bank Charges"], "amount": [BANK_CHARGES_GL]}
        )
    }
    consol = pd.DataFrame(
        [{"account": "Bank Charges", "category": "G&A", "amount": BANK_CHARGES_GL}]
    )
    hints = compute_hints(item, consol, PERIOD, raw)
    assert hints.is_gl_only is True
    assert hints.is_processor_fee_gap is False
    assert hints.is_customer_deposit is False


def test_deposit_classifies_as_timing_cutoff_not_accrual() -> None:
    hints = compute_hints(
        deposit_item(), deposit_consolidated(), PERIOD, deposit_raw_dfs()
    )
    assert _classify_from_hints(hints.model_dump()) == "timing_cutoff"
    assert _classify_from_hints(hints.model_dump()) != "accrual_mismatch"
    assert _classify_from_hints(hints.model_dump()) != "structural_explained"


def test_fee_classifies_as_structural_explained() -> None:
    hints = compute_hints(fee_item(), fee_consolidated(), PERIOD, fee_raw_dfs())
    assert _classify_from_hints(hints.model_dump()) == "structural_explained"


def test_merge_forces_deposit_class_when_claude_says_accrual() -> None:
    hints = compute_hints(
        deposit_item(), deposit_consolidated(), PERIOD, deposit_raw_dfs()
    )
    items = [
        {
            "account": "Installation Revenue",
            "card_kind": "exception",
            "hints": hints.model_dump(),
            "classification": None,
        }
    ]
    _apply_reconciliation_classifications(
        items, {"Installation Revenue": "accrual_mismatch"}
    )
    assert items[0]["classification"] == "timing_cutoff"


def test_merge_forces_fee_class_when_claude_says_missing_je() -> None:
    hints = compute_hints(fee_item(), fee_consolidated(), PERIOD, fee_raw_dfs())
    items = [
        {
            "account": "Product Sales",
            "card_kind": "exception",
            "hints": hints.model_dump(),
            "classification": None,
        }
    ]
    _apply_reconciliation_classifications(items, {"Product Sales": "missing_je"})
    assert items[0]["classification"] == "structural_explained"


def test_claude_cannot_invent_structural_explained_without_fee_hint() -> None:
    items = [
        {
            "account": "Office Rent",
            "card_kind": "exception",
            "hints": {
                "is_processor_fee_gap": False,
                "is_customer_deposit": False,
                "is_gl_only": False,
                "is_source_only": False,
            },
            "classification": None,
        }
    ]
    _apply_reconciliation_classifications(items, {"Office Rent": "structural_explained"})
    assert items[0]["classification"] == "stale_reference"


def test_prompt_binds_deposit_to_liability_not_prepaid() -> None:
    assert "liability until the job is done" in PROMPT
    assert "not a vendor prepaid" in PROMPT or "not a prepaid" in PROMPT
    deposit_block = PROMPT.split("Template (is_customer_deposit")[1].split("2. categorical")[0]
    assert "prepaid asset" not in deposit_block
    assert "earned revenue" in deposit_block or "unearned" in PROMPT.lower() or "liability" in deposit_block


def test_prompt_binds_fee_to_netting_not_future_revenue() -> None:
    assert "is_processor_fee_gap is true" in PROMPT
    fee_block = PROMPT.split("6. structural_explained")[1].split("Hard rules")[0]
    assert "unearned revenue" in fee_block
    assert "No action required" in fee_block
    assert "recognized as revenue later" in fee_block or "Do not say the amount will be recognized as revenue later" in fee_block
