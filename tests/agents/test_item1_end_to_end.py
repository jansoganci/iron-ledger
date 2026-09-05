"""Item 1 PR-C — end to end through the real invocation path.

Exercises the production functions, not the matcher in isolation:

    ParserAgent._build_sidecar   (real CSV headers -> canonical sidecar)
        -> _attach_batch_matches (the orchestrator call site)
            -> batch_matcher.match + _classify
                -> ReconciliationItem.matches

Three scenarios, all required by the spec:
  1. Real three-way match on the C.5.3 fixture.
  2. Vandelay negative — payouts with no bank file must NOT claim three-way.
  3. Sentinel negative — no bank/processor file at all, nothing changes.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from backend.agents.orchestrator import _attach_batch_matches
from backend.agents.parser import _DEFAULT_UF_ACCOUNT_NAME, ParserAgent
from backend.domain.contracts import (
    DiscoveryPlan,
    ReconciliationItem,
    ReconciliationSource,
)
from backend.tools import file_reader

FIXTURE_DIR = Path(__file__).parent.parent / "tools" / "fixtures"
PERIOD = date(2026, 3, 1)


def _parser() -> ParserAgent:
    """_build_sidecar uses no instance state; skip the dependency wiring."""
    return ParserAgent.__new__(ParserAgent)


# The production read path. `read_file` promotes no headers — columns come
# back as integer positions and Discovery's plan names them later. Reading the
# fixtures with pd.read_csv instead (header=0) is what hid the bug where
# _build_sidecar matched aliases against integers and always returned None.
_PLAN = DiscoveryPlan(
    header_row_index=0,
    skip_row_indices=[],
    column_mapping={},
    hierarchy_hints=[],
    discovery_confidence=0.9,
)


def _raw(name: str) -> pd.DataFrame:
    return file_reader.read_file(FIXTURE_DIR / name)


def _sidecar(name: str, file_type: str | None) -> "pd.DataFrame | None":
    return _parser()._build_sidecar(_raw(name), file_type, _PLAN)


def _uf_item() -> ReconciliationItem:
    return ReconciliationItem(
        account=_DEFAULT_UF_ACCOUNT_NAME,
        category="REVENUE",
        sources=[
            ReconciliationSource(source_file="bank.csv", amount=4225.0, row_count=1)
        ],
        gl_amount=3300.0,
        non_gl_total=4225.0,
        delta=925.0,
        delta_pct=0.28,
        severity="high",
    )


def _entry(label: str, file_type: str, sidecar) -> tuple:
    """A per_file_data row in the shape _finalize_consolidation builds."""
    return (label, [], "Amount", pd.DataFrame(), False, file_type, sidecar)


# ---------------------------------------------------------------------------
# Sidecar extraction on real headers
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "name,file_type",
    [
        ("kova_cash_fsm_mar_2026.csv", "processor_settlement"),
        ("kova_cash_bank_mar_2026.csv", "bank_statement"),
        ("kova_cash_gl_mar_2026.csv", "general_ledger"),
    ],
)
def test_sidecar_built_from_the_real_read_path(name, file_type) -> None:
    """Regression: every matcher sidecar must survive positional columns.

    `file_reader.read_file` labels columns 0..n; header promotion happens later
    in apply_plan. _build_sidecar matches aliases by name, so before the fix it
    returned None here for all three file types and the matcher never ran on a
    real upload. Fails against the pre-fix two-argument _build_sidecar.
    """
    raw = _raw(name)
    assert all(isinstance(c, int) for c in raw.columns)
    assert _sidecar(name, file_type) is not None


def test_fsm_sidecar_keeps_matcher_columns_and_drops_customer() -> None:
    sidecar = _sidecar("kova_cash_fsm_mar_2026.csv", "processor_settlement")
    assert sidecar is not None
    assert set(sidecar.columns) == {
        "payout_id",
        "gross",
        "collected_date",
        "_orig_row_index",
    }
    assert "customer" not in sidecar.columns  # not a matcher column
    assert len(sidecar) == 7


def test_bank_sidecar_maps_canonical_headers() -> None:
    sidecar = _sidecar("kova_cash_bank_mar_2026.csv", "bank_statement")
    assert sidecar is not None
    assert {"bank_ref", "gross", "net", "settlement_date"} <= set(sidecar.columns)
    assert len(sidecar) == 8


def test_gl_sidecar_does_not_sidecar_rent() -> None:
    """C.5.1: only rows with a ref OR on the UF account."""
    sidecar = _sidecar("kova_cash_gl_mar_2026.csv", "general_ledger")
    assert sidecar is not None
    accounts = set(sidecar["gl_account"])
    assert "Rent" not in accounts
    assert "Service Revenue" not in accounts
    assert accounts == {_DEFAULT_UF_ACCOUNT_NAME, "Accounts Receivable"}
    assert len(sidecar) == 4


@pytest.mark.parametrize(
    "file_type", ["payroll", "supplier_invoices", "contracts", None]
)
def test_no_sidecar_for_pre_existing_file_types(file_type) -> None:
    """The golden path must be untouched for every file the matcher ignores."""
    assert _sidecar("kova_cash_gl_mar_2026.csv", file_type) is None


# ---------------------------------------------------------------------------
# Scenario 1 — real three-way match
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def matched_item():
    p = _parser()
    per_file_data = [
        _entry(
            "fsm.csv",
            "processor_settlement",
            _sidecar("kova_cash_fsm_mar_2026.csv", "processor_settlement"),
        ),
        _entry(
            "gl.csv",
            "general_ledger",
            _sidecar("kova_cash_gl_mar_2026.csv", "general_ledger"),
        ),
        _entry(
            "bank.csv",
            "bank_statement",
            _sidecar("kova_cash_bank_mar_2026.csv", "bank_statement"),
        ),
    ]
    item = _uf_item()
    _attach_batch_matches([item], per_file_data, PERIOD, "run-e2e")
    return item


def test_e2e_matches_are_attached_to_the_uf_item(matched_item) -> None:
    assert matched_item.matches is not None
    assert len(matched_item.matches) == 6


def test_e2e_every_pinned_classification(matched_item) -> None:
    got = {m.match_id: m.classification for m in matched_item.matches}
    assert got == {
        "pz-100": "structural_explained",
        "pz-200": "timing_cutoff",
        "pz-300": "missing_je",
        "pz-500": "categorical_misclassification",
        "none:bank:dep-99": "missing_je",
        "ad:100.00:2026-03-25": "stale_reference",
    }


def test_e2e_pz900_produces_no_card(matched_item) -> None:
    assert "pz-900" not in {m.match_id for m in matched_item.matches}


def test_e2e_amounts_survive_the_real_path(matched_item) -> None:
    by_id = {m.match_id: m for m in matched_item.matches}
    assert (by_id["pz-100"].gross, by_id["pz-100"].net, by_id["pz-100"].fee) == (
        1000.0,
        955.0,
        45.0,
    )
    assert by_id["pz-200"].settlement_date == date(2026, 4, 2)
    assert by_id["ad:100.00:2026-03-25"].candidate_count == 2


def test_e2e_force_class_and_residue(matched_item) -> None:
    """The card's own class is the pandas residue, not Claude's choice."""
    from backend.agents.interpreter import _apply_reconciliation_classifications

    payload = matched_item.model_dump()
    payload["matches"] = [m.model_dump() for m in matched_item.matches]
    _apply_reconciliation_classifications(
        [payload], {_DEFAULT_UF_ACCOUNT_NAME: "structural_explained"}
    )
    # Claude said "no action required"; a missing JE is nested underneath.
    assert payload["classification"] == "missing_je"


def test_e2e_golden_rule_every_narratable_number_is_verified(matched_item) -> None:
    """No computed value reaches Claude without being a guardrail reference."""
    from backend.tools.guardrail import verify_guardrail

    recon_values: list[float] = []
    for m in matched_item.matches:
        for f in ("gross", "fee", "net", "gl_amount"):
            v = getattr(m, f)
            if v is not None:
                recon_values.extend([float(v), float(abs(v))])
        recon_values.append(float(m.candidate_count))

    summary = {"accounts": {_DEFAULT_UF_ACCOUNT_NAME: {"current": 3300.0}}}
    for number in (1000.0, 955.0, 45.0, 2000.0, 1920.0, 80.0, 750.0, 600.0, 2.0):
        passed, msg = verify_guardrail(
            {"numbers_used": [number], "narrative": f"Value {number:,.2f}."},
            summary,
            reconciliation_values=recon_values,
            strict=True,
        )
        assert passed is True, f"{number} should be verifiable: {msg}"

    # And an invented number still fails.
    passed, _ = verify_guardrail(
        {"numbers_used": [4321.99], "narrative": "Value 4,321.99."},
        summary,
        reconciliation_values=recon_values,
        strict=True,
    )
    assert passed is False


def test_e2e_fee_pct_never_reaches_the_payload(matched_item) -> None:
    for m in matched_item.matches:
        assert "fee_pct" not in m.model_dump()


def test_e2e_only_six_classes(matched_item) -> None:
    from typing import get_args

    from backend.domain.contracts import ReconciliationClassification

    allowed = set(get_args(ReconciliationClassification))
    for m in matched_item.matches:
        assert m.classification in allowed


# ---------------------------------------------------------------------------
# Scenario 2 — Vandelay negative: payouts with NO bank file
# ---------------------------------------------------------------------------


def test_vandelay_payouts_without_a_bank_file_do_not_claim_three_way() -> None:
    """The spec's repeated warning: Vandelay alone is two-sided, not three-way."""
    p = _parser()
    per_file_data = [
        _entry(
            "vandelay_shopify_payouts_mar_2026.csv",
            "processor_settlement",
            _sidecar("kova_cash_fsm_mar_2026.csv", "processor_settlement"),
        ),
        _entry(
            "gl.csv",
            "general_ledger",
            _sidecar("kova_cash_gl_mar_2026.csv", "general_ledger"),
        ),
    ]
    item = _uf_item()
    _attach_batch_matches([item], per_file_data, PERIOD, "run-vandelay")

    assert item.matches is None, "matcher must not run without a settlement file"


def test_vandelay_negative_leaves_kova1_fee_hint_free_to_fire() -> None:
    """Falling back means today's account-total behaviour still applies."""
    from backend.agents.interpreter import _apply_reconciliation_classifications

    item = _uf_item().model_dump()
    item["matches"] = None
    item["hints"] = {"is_processor_fee_gap": True}
    _apply_reconciliation_classifications([item], {})
    assert item["classification"] == "structural_explained"


# ---------------------------------------------------------------------------
# Scenario 3 — Sentinel negative: no bank or processor file at all
# ---------------------------------------------------------------------------


def test_sentinel_style_run_is_completely_unaffected() -> None:
    p = _parser()
    per_file_data = [
        _entry(
            "sentinel_gl_mar_2026.csv",
            "general_ledger",
            _sidecar("kova_cash_gl_mar_2026.csv", "general_ledger"),
        ),
        _entry("sentinel_payroll.csv", "payroll", None),
        _entry("sentinel_contracts.csv", "contracts", None),
    ]
    item = _uf_item()
    before = item.model_dump()
    _attach_batch_matches([item], per_file_data, PERIOD, "run-sentinel")

    assert item.matches is None
    assert item.model_dump() == before  # byte-for-byte untouched


def test_no_sidecars_at_all_is_a_no_op() -> None:
    item = _uf_item()
    _attach_batch_matches([item], [], PERIOD, "run-empty")
    assert item.matches is None


def test_missing_uf_item_does_not_invent_a_card() -> None:
    """If the GL has no UF line there is nothing to nest under — log, not guess."""
    p = _parser()
    per_file_data = [
        _entry(
            "fsm.csv",
            "processor_settlement",
            _sidecar("kova_cash_fsm_mar_2026.csv", "processor_settlement"),
        ),
        _entry(
            "bank.csv",
            "bank_statement",
            _sidecar("kova_cash_bank_mar_2026.csv", "bank_statement"),
        ),
    ]
    other = _uf_item()
    other.account = "Service Revenue"
    _attach_batch_matches([other], per_file_data, PERIOD, "run-no-uf")
    assert other.matches is None
