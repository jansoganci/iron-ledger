"""Item 4 — end to end plus the gates, force-class, guardrail and negatives.

    ParserAgent._build_sidecar   (roster CSV -> contracts sidecar)
        -> _attach_roster_counts (R.4 / R.5 / R.7 gates)
            -> roster_counts.compute
                -> ReconciliationHints
                    -> interpreter force-class + guardrail
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from backend.agents.interpreter import _apply_reconciliation_classifications
from backend.agents.orchestrator import _attach_roster_counts
from backend.agents.parser import ParserAgent
from backend.domain.contracts import ReconciliationItem, ReconciliationSource
from backend.tools.guardrail import verify_guardrail

ROSTER = (
    Path(__file__).parent.parent / "tools" / "fixtures" / "kova_rmr_roster_mar_2026.csv"
)
PERIOD = date(2026, 3, 1)
ACCOUNT = "Service Revenue"


def _parser() -> ParserAgent:
    return ParserAgent.__new__(ParserAgent)


def _sidecar() -> pd.DataFrame:
    return _parser()._build_sidecar(pd.read_csv(ROSTER), "contracts")


def _item(account: str = ACCOUNT) -> ReconciliationItem:
    return ReconciliationItem(
        account=account,
        category="REVENUE",
        sources=[
            ReconciliationSource(source_file="roster.csv", amount=3825.0, row_count=1)
        ],
        gl_amount=3540.0,
        non_gl_total=3825.0,
        delta=285.0,
        delta_pct=0.08,
        severity="medium",
    )


def _entry(file_type: str, sidecar, accounts=(ACCOUNT,)) -> tuple:
    preview = [{"account": a, "amount": 0.0, "category": "REVENUE"} for a in accounts]
    return ("roster.csv", preview, "Fee", pd.DataFrame(), False, file_type, sidecar)


# ---------------------------------------------------------------------------
# Sidecar plumbing (C.1)
# ---------------------------------------------------------------------------


def test_contracts_sidecar_keeps_only_count_inputs() -> None:
    sc = _sidecar()
    assert set(sc.columns) == {
        "customer_id",
        "status",
        "monthly_fee",
        "last_billed",
        "_orig_row_index",
    }
    assert "customer_name" not in sc.columns  # not a count input


def test_contracts_sidecar_survives_groupby() -> None:
    """The whole point: 88 roster rows collapse to one preview row, counts don't."""
    raw = pd.read_csv(ROSTER)
    sc = _parser()._build_sidecar(raw, "contracts")
    collapsed = (
        pd.DataFrame({"account": [ACCOUNT] * len(raw), "amount": raw["monthly_fee"]})
        .groupby("account")["amount"]
        .sum()
    )
    assert len(collapsed) == 1  # the grain kill
    assert len(sc) == 88  # sidecar untouched by it


@pytest.mark.parametrize(
    "file_type", ["general_ledger", "payroll", "supplier_invoices", None]
)
def test_pnl_and_other_files_get_no_roster_sidecar(file_type) -> None:
    sc = _parser()._build_sidecar(pd.read_csv(ROSTER), file_type)
    assert sc is None or "status" not in sc.columns


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


@pytest.fixture()
def counted_item():
    item = _item()
    _attach_roster_counts([item], [_entry("contracts", _sidecar())], PERIOD, "r")
    return item


def test_counts_attach_to_the_mapped_gl_account(counted_item) -> None:
    h = counted_item.hints
    assert (h.n_active, h.n_billed_in_period, h.count_delta) == (85, 82, 3)
    assert (h.fee_sum_active, h.fee_sum_billed) == (3825.00, 3540.00)


# ---------------------------------------------------------------------------
# Gates — R.4 / R.5 / R.7
# ---------------------------------------------------------------------------


def test_r4_two_roster_files_emit_nothing() -> None:
    item = _item()
    _attach_roster_counts(
        [item],
        [_entry("contracts", _sidecar()), _entry("contracts", _sidecar())],
        PERIOD,
        "r",
    )
    assert item.hints.count_delta is None


def test_r5_roster_mapping_to_two_accounts_emits_nothing() -> None:
    item = _item()
    _attach_roster_counts(
        [item],
        [_entry("contracts", _sidecar(), accounts=(ACCOUNT, "Monitoring Revenue"))],
        PERIOD,
        "r",
    )
    assert item.hints.count_delta is None


def test_r5_roster_mapping_to_zero_accounts_emits_nothing() -> None:
    item = _item()
    _attach_roster_counts(
        [item], [_entry("contracts", _sidecar(), accounts=())], PERIOD, "r"
    )
    assert item.hints.count_delta is None


def test_r7_immaterial_account_is_not_resurrected() -> None:
    """consolidate() dropped the account — counts are discarded, no new card."""
    other = _item(account="Rent")
    _attach_roster_counts([other], [_entry("contracts", _sidecar())], PERIOD, "r")
    assert other.hints.count_delta is None


def test_no_contracts_file_is_a_no_op() -> None:
    item = _item()
    before = item.model_dump()
    _attach_roster_counts([item], [_entry("general_ledger", None)], PERIOD, "r")
    assert item.model_dump() == before


# ---------------------------------------------------------------------------
# Force-classification — R.6
# ---------------------------------------------------------------------------


def test_count_gap_forces_stale_reference_over_claude(counted_item) -> None:
    payload = counted_item.model_dump()
    _apply_reconciliation_classifications([payload], {ACCOUNT: "missing_je"})
    assert payload["classification"] == "stale_reference"


def test_count_delta_zero_forces_nothing() -> None:
    """R.6: counts attach, but there is no "0 accounts" story."""
    payload = _item().model_dump()
    payload["hints"] = {
        "n_active": 85,
        "n_billed_in_period": 85,
        "count_delta": 0,
        "similar_amount_in_other_account": True,
    }
    _apply_reconciliation_classifications([payload], {})
    # Falls through to the ordinary hint fallback, not a forced count story.
    assert payload["classification"] == "categorical_misclassification"


def test_fee_deposit_annual_still_outrank_roster_counts() -> None:
    for hint, expected in (
        ("is_processor_fee_gap", "structural_explained"),
        ("is_customer_deposit", "timing_cutoff"),
        ("looks_like_annual_prepayment", "accrual_mismatch"),
    ):
        payload = _item().model_dump()
        payload["hints"] = {hint: True, "count_delta": 3, "n_active": 85}
        _apply_reconciliation_classifications([payload], {})
        assert payload["classification"] == expected, hint


def test_coverage_still_outranks_roster_counts() -> None:
    payload = _item().model_dump()
    payload["card_kind"] = "coverage"
    payload["hints"] = {"count_delta": 3}
    _apply_reconciliation_classifications([payload], {})
    assert payload["classification"] is None


def test_only_six_classes_possible(counted_item) -> None:
    from typing import get_args

    from backend.domain.contracts import ReconciliationClassification

    payload = counted_item.model_dump()
    _apply_reconciliation_classifications([payload], {})
    assert payload["classification"] in set(get_args(ReconciliationClassification))


# ---------------------------------------------------------------------------
# Guardrail — R.8
# ---------------------------------------------------------------------------


def _recon_values(item: ReconciliationItem) -> list[float]:
    """Mirror of the interpreter's reference loop for the roster fields."""
    values: list[float] = []
    h = item.hints
    for field in (
        "n_active",
        "n_billed_in_period",
        "count_delta",
        "fee_sum_active",
        "fee_sum_billed",
    ):
        v = getattr(h, field)
        if v is not None:
            values.extend([float(v), float(abs(v))])
    return values


@pytest.mark.parametrize("number", [85.0, 82.0, 3.0, 3825.0, 3540.0])
def test_every_narratable_count_is_verified(counted_item, number) -> None:
    passed, msg = verify_guardrail(
        {"numbers_used": [number], "narrative": f"Value {number:,.2f}."},
        {"accounts": {ACCOUNT: {"current": 3540.0}}},
        reconciliation_values=_recon_values(counted_item),
        strict=True,
    )
    assert passed is True, msg


def test_invented_count_still_fails(counted_item) -> None:
    passed, _ = verify_guardrail(
        {"numbers_used": [7.0], "narrative": "7 accounts."},
        {"accounts": {ACCOUNT: {"current": 3540.0}}},
        reconciliation_values=_recon_values(counted_item),
        strict=True,
    )
    assert passed is False


def test_no_ratio_or_percentage_enters_the_pool(counted_item) -> None:
    """R.8: 3/85 = 0.0353 and 3.53% must never be reference values."""
    values = _recon_values(counted_item)
    assert 3 / 85 not in values
    assert round(3 / 85 * 100, 2) not in values
    assert all(v in (85.0, 82.0, 3.0, 3825.0, 3540.0) for v in values)


# ---------------------------------------------------------------------------
# Negatives the spec requires
# ---------------------------------------------------------------------------


def test_pr11_cutoff_allowlist_unaffected_by_roster_dates() -> None:
    """PR #11 regression: Last Billed must never become a timing_cutoff signal."""
    from backend.tools.hint_computer import (
        _CUTOFF_DATE_BLOCK,
        _crosses_period_boundary,
    )

    assert "last billed" in _CUTOFF_DATE_BLOCK
    assert "renewal" in _CUTOFF_DATE_BLOCK

    roster = pd.DataFrame(
        {
            "account": ["Service Revenue"] * 3,
            "amount": [43.0, 43.0, 43.0],
            "Last Billed": ["2026-04-15", "2026-04-20", "2026-03-01"],
        }
    )
    assert (
        _crosses_period_boundary(
            {"sentinel_contracts_mar_2026.xlsx"},
            {"sentinel_contracts_mar_2026.xlsx": roster},
            date(2026, 3, 31),
        )
        is False
    )


def test_annual_prepayment_is_not_turned_into_a_count_card() -> None:
    """Negative: Software 13,200 / 1,100 stays accrual_mismatch, no counts."""
    payload = _item(account="Software").model_dump()
    payload["hints"] = {
        "looks_like_annual_prepayment": True,
        "implied_monthly": 1100.0,
    }
    _apply_reconciliation_classifications([payload], {})
    assert payload["classification"] == "accrual_mismatch"
    assert payload["hints"].get("count_delta") is None


def test_dollar_only_stale_reference_has_no_count_fields() -> None:
    """A 285.00 gap with no roster stays dollar-only — nothing to say "0" about."""
    payload = _item().model_dump()
    payload["hints"] = {}
    _apply_reconciliation_classifications([payload], {ACCOUNT: "stale_reference"})
    assert payload["classification"] == "stale_reference"
    assert payload["hints"].get("n_active") is None


def test_consolidator_row_count_stays_one(counted_item) -> None:
    """row_count is rolled source lines, never a subscriber count."""
    assert counted_item.sources[0].row_count == 1


# ---------------------------------------------------------------------------
# Prompt contract
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "prompt",
    ["narrative_prompt.txt", "narrative_prompt_reinforced.txt"],
)
def test_prompts_forbid_the_dangerous_count_language(prompt) -> None:
    text = (
        Path(__file__).parent.parent.parent / "backend" / "prompts" / prompt
    ).read_text()
    lowered = text.lower()
    assert "count_delta" in lowered
    for forbidden_rule in ("customers", "subscribers", "percentage", "approximate"):
        assert forbidden_rule in lowered, forbidden_rule
