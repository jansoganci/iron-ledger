"""Riverbend HVAC demo — Item 1 files that survive the real upload shape.

The kova_cash_*.csv fixtures are matcher unit data. They have no `account`
column, so pandera rejects them on POST /upload. These workbooks are the
uploadable stand-in: Golden Schema on every file, sidecar columns intact,
six exception states plus one true negative.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from backend.agents.orchestrator import _detect_file_type
from backend.domain.contracts import DiscoveryPlan
from backend.tools import file_reader, normalizer, validator
from backend.tools.batch_matcher import match
from backend.tools.sidecar import _DEFAULT_UF_ACCOUNT_NAME, build_sidecar

DEMO_DIR = Path("docs/demo_data/riverbend")
PERIOD = date(2026, 3, 1)

GL = DEMO_DIR / "riverbend_gl_mar_2026.xlsx"
PROCESSOR = DEMO_DIR / "riverbend_stripe_payouts_mar_2026.xlsx"
BANK = DEMO_DIR / "riverbend_bank_statement_mar_2026.xlsx"

HEADER_ROW = 4
SKIP = [0, 1, 2, 3]

GL_PLAN = DiscoveryPlan(
    header_row_index=HEADER_ROW,
    skip_row_indices=SKIP,
    column_mapping={
        "Date": "date",
        "Account": "account",
        "Account Code": "account_code",
        "Category": "parent_category",
        "Amount": "amount",
        "Memo": None,
        "Description": "description",
    },
    hierarchy_hints=[],
    discovery_confidence=0.95,
)

PROCESSOR_PLAN = DiscoveryPlan(
    header_row_index=HEADER_ROW,
    skip_row_indices=SKIP,
    column_mapping={
        "Payout ID": None,
        "Collected Date": "date",
        "Account": "account",
        "Customer": "description",
        "Gross": "amount",
    },
    hierarchy_hints=[],
    discovery_confidence=0.95,
)

BANK_PLAN = DiscoveryPlan(
    header_row_index=HEADER_ROW,
    skip_row_indices=SKIP,
    column_mapping={
        "Bank Ref": None,
        "Settlement Date": "date",
        "Account": "account",
        "Description": "description",
        "Gross": "amount",
        "Fee": None,
        "Net": None,
    },
    hierarchy_hints=[],
    discovery_confidence=0.95,
)


@pytest.mark.parametrize(
    "path, expected",
    [
        (GL, "general_ledger"),
        (PROCESSOR, "processor_settlement"),
        (BANK, "bank_statement"),
    ],
)
def test_filenames_route_to_item1_types(path: Path, expected: str) -> None:
    assert path.is_file()
    assert _detect_file_type(path.name) == expected


@pytest.mark.parametrize(
    "path, plan",
    [
        (GL, GL_PLAN),
        (PROCESSOR, PROCESSOR_PLAN),
        (BANK, BANK_PLAN),
    ],
)
def test_golden_schema_survives_apply_plan(
    path: Path,
    plan: DiscoveryPlan,
) -> None:
    """The kova CSVs die here. These files must not."""
    raw = file_reader.read_file(path)
    normalized, report = normalizer.apply_plan(raw, plan, PERIOD)
    validated = validator.validate(normalized)
    assert "account" in validated.columns
    assert "amount" in validated.columns
    assert report.total_dropped == 0
    assert not validated.empty
    assert validated["account"].notna().all()


def test_processor_and_bank_map_to_undeposited_funds() -> None:
    for path, plan in ((PROCESSOR, PROCESSOR_PLAN), (BANK, BANK_PLAN)):
        raw = file_reader.read_file(path)
        df, _ = normalizer.apply_plan(raw, plan, PERIOD)
        assert set(df["account"]) == {_DEFAULT_UF_ACCOUNT_NAME}


def test_matcher_emits_six_cards_and_drops_the_clean_tie_out() -> None:
    fsm = build_sidecar(
        file_reader.read_file(PROCESSOR),
        "processor_settlement",
        PROCESSOR_PLAN,
    )
    gl = build_sidecar(
        file_reader.read_file(GL),
        "general_ledger",
        GL_PLAN,
    )
    bank = build_sidecar(file_reader.read_file(BANK), "bank_statement", BANK_PLAN)
    assert fsm is not None and gl is not None and bank is not None

    result = match(fsm, gl, bank, PERIOD, _DEFAULT_UF_ACCOUNT_NAME)
    by_id = {m.match_id: m for m in result.matches}

    assert len(result.matches) == 6
    assert "po_1rb7vc9ezvrb" not in by_id

    fee = by_id["po_1qx8km2ezvrb"]
    assert fee.classification == "structural_explained"
    assert fee.gross == 1847.50
    assert fee.net == 1764.36
    assert fee.fee == 83.14
    assert fee.gl_account == _DEFAULT_UF_ACCOUNT_NAME

    cutoff = by_id["po_1qy2nt4ezvrb"]
    assert cutoff.classification == "timing_cutoff"
    assert cutoff.settlement_date == date(2026, 4, 2)
    assert cutoff.fee == 92.67

    missing = by_id["po_1qz9pw7ezvrb"]
    assert missing.classification == "missing_je"
    assert missing.gl_account is None
    assert missing.fee == 26.33

    bank_only = by_id["none:bank:ach-44192"]
    assert bank_only.classification == "missing_je"
    assert bank_only.match_kind == "none"
    assert bank_only.fee == 0.0

    wrong_account = by_id["po_1ra3ls1ezvrb"]
    assert wrong_account.classification == "categorical_misclassification"
    assert wrong_account.gl_account == "Accounts Receivable"
    assert wrong_account.fee == 0.0

    ambiguous = by_id["ad:186.40:2026-03-25"]
    assert ambiguous.classification == "stale_reference"
    assert ambiguous.ambiguous is True
    assert ambiguous.candidate_count == 2

    assert result.unmatched_processor_count == 0
    assert result.unmatched_bank_count == 1
