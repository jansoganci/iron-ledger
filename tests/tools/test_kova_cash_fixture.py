"""Item 1 PR-A — the isolated three-file cash fixture (spec C.5.3).

The fixture is checked in at PR-A; the matcher assertions that consume it land
at PR-B. These tests pin the *data* so PR-B cannot silently drift from the
spec, and pin the expected per-row outcomes as a declared table.

Self-contained by design: no Sentinel, no Vandelay, no DRONE.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from backend.tools.batch_matcher import build_match_id

FIXTURE_DIR = Path(__file__).parent / "fixtures"
FSM_CSV = FIXTURE_DIR / "kova_cash_fsm_mar_2026.csv"
GL_CSV = FIXTURE_DIR / "kova_cash_gl_mar_2026.csv"
BANK_CSV = FIXTURE_DIR / "kova_cash_bank_mar_2026.csv"

PERIOD = date(2026, 3, 1)
PERIOD_END = date(2026, 3, 31)
UF_ACCOUNT_NAME = "Undeposited Funds"


# ---------------------------------------------------------------------------
# Expected matcher output — the PR-B acceptance table (C.5.3), declared here so
# PR-B consumes a pinned constant rather than re-deriving it. PR-A cannot
# assert the classifications themselves: there is no matcher yet. What PR-A
# DOES assert is that every match_id below is exactly what build_match_id
# produces, and that the source rows behind them are present and correct.
# ---------------------------------------------------------------------------

EXPECTED_MATCHES: list[dict] = [
    {
        "label": "PZ-100",
        "match_kind": "id",
        "fee": 45.00,
        "settlement_date": date(2026, 3, 15),
        "gl_account": UF_ACCOUNT_NAME,
        "classification": "structural_explained",
        "card": True,
        "match_id": "pz-100",
    },
    {
        "label": "PZ-200",
        "match_kind": "id",
        "fee": 80.00,
        "settlement_date": date(2026, 4, 2),
        "gl_account": UF_ACCOUNT_NAME,
        "classification": "timing_cutoff",
        "card": True,
        "match_id": "pz-200",
    },
    {
        "label": "PZ-300",
        "match_kind": "id",
        "fee": 20.00,
        "settlement_date": date(2026, 3, 20),
        "gl_account": None,
        "classification": "missing_je",
        "card": True,
        "match_id": "pz-300",
    },
    {
        "label": "DEP-99",
        "match_kind": "none",
        "fee": 0.00,
        "settlement_date": date(2026, 3, 22),
        "gl_account": None,
        "classification": "missing_je",
        "card": True,
        "match_id": "none:bank:dep-99",
    },
    {
        "label": "PZ-500",
        "match_kind": "id",
        "fee": 0.00,
        "settlement_date": date(2026, 3, 18),
        "gl_account": "Accounts Receivable",
        "classification": "categorical_misclassification",
        "card": True,
        "match_id": "pz-500",
    },
    {
        "label": "PZ-900",
        "match_kind": "id",
        "fee": 0.00,
        "settlement_date": date(2026, 3, 10),
        "gl_account": UF_ACCOUNT_NAME,
        "classification": None,  # true negative — dropped by rule 6
        "card": False,
        "match_id": "pz-900",
    },
    {
        "label": "blank x2",
        "match_kind": "amount_date",
        "fee": 0.00,
        "settlement_date": date(2026, 3, 25),
        "gl_account": None,
        "classification": "stale_reference",  # ambiguous, rule 1
        "card": True,
        "match_id": "ad:100.00:2026-03-25",
    },
]

EXPECTED_UNMATCHED_PROCESSOR_COUNT = 0
EXPECTED_UNMATCHED_BANK_COUNT = 1  # DEP-99


# ---------------------------------------------------------------------------
# Files exist and load
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("path", [FSM_CSV, GL_CSV, BANK_CSV])
def test_fixture_file_exists(path: Path) -> None:
    assert path.is_file(), f"missing fixture: {path.name}"


def test_fixture_filenames_are_the_locked_names() -> None:
    names = sorted(p.name for p in FIXTURE_DIR.glob("kova_cash_*.csv"))
    assert names == [
        "kova_cash_bank_mar_2026.csv",
        "kova_cash_fsm_mar_2026.csv",
        "kova_cash_gl_mar_2026.csv",
    ]


# ---------------------------------------------------------------------------
# File 1 — FSM / job card-batch
# ---------------------------------------------------------------------------


def test_fsm_fixture_rows() -> None:
    df = pd.read_csv(FSM_CSV, dtype={"payout_id": "string"})
    assert list(df.columns) == ["payout_id", "collected_date", "gross", "customer"]
    assert len(df) == 7

    ided = df[df["payout_id"].notna()]
    assert list(ided["payout_id"]) == ["PZ-100", "PZ-200", "PZ-300", "PZ-500", "PZ-900"]
    assert list(ided["gross"]) == [1000.00, 2000.00, 500.00, 600.00, 300.00]
    assert list(ided["collected_date"]) == [
        "2026-03-15",
        "2026-03-31",
        "2026-03-20",
        "2026-03-18",
        "2026-03-10",
    ]


def test_fsm_has_no_net_column_so_gross_feeds_the_fallback_key() -> None:
    """C.5.1: FSM `net` is optional and absent here.

    This is exactly why the E.5 correction matters — the Pass-2 grouping key
    takes FSM *gross* against bank *net*, and only the $0.00 tolerance keeps
    that safe.
    """
    df = pd.read_csv(FSM_CSV)
    assert "net" not in df.columns


def test_fsm_ambiguous_pair_is_blank_ref_same_amount_and_day() -> None:
    df = pd.read_csv(FSM_CSV, dtype={"payout_id": "string"})
    blanks = df[df["payout_id"].isna()]
    assert len(blanks) == 2
    assert set(blanks["gross"]) == {100.00}
    assert set(blanks["collected_date"]) == {"2026-03-25"}


# ---------------------------------------------------------------------------
# File 2 — GL with UF detail
# ---------------------------------------------------------------------------


def test_gl_fixture_rows() -> None:
    df = pd.read_csv(GL_CSV, dtype={"memo": "string"})
    assert list(df.columns) == ["date", "account", "amount", "memo"]
    assert len(df) == 6
    assert list(df["amount"]) == [1000.00, 2000.00, 600.00, 300.00, 3540.00, 3200.00]


def test_gl_has_no_row_for_pz300_or_dep99() -> None:
    """These absences are what make states 3 and 4 reachable."""
    memos = set(pd.read_csv(GL_CSV, dtype={"memo": "string"})["memo"].dropna())
    assert "PZ-300" not in memos
    assert "DEP-99" not in memos


def test_gl_distractor_rows_are_not_matcher_inputs() -> None:
    """Rent / Service Revenue have no ref and are not UF — 'Do not sidecar Rent'."""
    df = pd.read_csv(GL_CSV, dtype={"memo": "string"})
    distractors = df[df["memo"].isna()]
    assert set(distractors["account"]) == {"Service Revenue", "Rent"}
    for account in distractors["account"]:
        assert account != UF_ACCOUNT_NAME


def test_gl_pz500_is_booked_to_the_wrong_clearing_account() -> None:
    df = pd.read_csv(GL_CSV, dtype={"memo": "string"})
    row = df[df["memo"] == "PZ-500"].iloc[0]
    assert row["account"] == "Accounts Receivable"
    assert row["account"] != UF_ACCOUNT_NAME


# ---------------------------------------------------------------------------
# File 3 — bank / processor settlement
# ---------------------------------------------------------------------------


def test_bank_fixture_rows() -> None:
    df = pd.read_csv(BANK_CSV, dtype={"bank_ref": "string"})
    assert list(df.columns) == ["bank_ref", "settlement_date", "gross", "net"]
    assert len(df) == 8

    ided = df[df["bank_ref"].notna()]
    assert list(ided["bank_ref"]) == [
        "PZ-100",
        "PZ-200",
        "PZ-300",
        "DEP-99",
        "PZ-500",
        "PZ-900",
    ]
    assert list(ided["gross"]) == [1000.0, 2000.0, 500.0, 750.0, 600.0, 300.0]
    assert list(ided["net"]) == [955.0, 1920.0, 480.0, 750.0, 600.0, 300.0]


def test_bank_has_no_fee_column_on_purpose() -> None:
    """C.5.3: fee must come from pandas `gross - net` (N3), never a column."""
    df = pd.read_csv(BANK_CSV)
    assert "fee" not in df.columns


def test_bank_pz200_settles_after_period_end() -> None:
    """The only row whose settlement date is outside the period (S1 / rule 2)."""
    df = pd.read_csv(BANK_CSV, dtype={"bank_ref": "string"})
    row = df[df["bank_ref"] == "PZ-200"].iloc[0]
    assert date.fromisoformat(row["settlement_date"]) > PERIOD_END

    others = df[df["bank_ref"].notna() & (df["bank_ref"] != "PZ-200")]
    for value in others["settlement_date"]:
        assert date.fromisoformat(value) <= PERIOD_END


# ---------------------------------------------------------------------------
# Expected-outcome table — match_ids are assertable in PR-A
# ---------------------------------------------------------------------------


def test_expected_table_covers_every_pinned_outcome() -> None:
    labels = [row["label"] for row in EXPECTED_MATCHES]
    assert labels == [
        "PZ-100",
        "PZ-200",
        "PZ-300",
        "DEP-99",
        "PZ-500",
        "PZ-900",
        "blank x2",
    ]
    assert sum(1 for r in EXPECTED_MATCHES if r["card"]) == 6
    assert sum(1 for r in EXPECTED_MATCHES if not r["card"]) == 1


def test_expected_match_ids_match_the_construction_rule() -> None:
    """Every pinned match_id is reproducible from build_match_id (E.4)."""
    by_label = {row["label"]: row for row in EXPECTED_MATCHES}

    for label in ("PZ-100", "PZ-200", "PZ-300", "PZ-500", "PZ-900"):
        assert by_label[label]["match_id"] == build_match_id("id", id_val=label)

    assert by_label["DEP-99"]["match_id"] == build_match_id(
        "none", side="bank", ref="DEP-99"
    )
    assert by_label["blank x2"]["match_id"] == build_match_id(
        "amount_date", amount=100.00, day=date(2026, 3, 25)
    )


def test_expected_match_ids_are_unique() -> None:
    ids = [row["match_id"] for row in EXPECTED_MATCHES]
    assert len(set(ids)) == len(ids)


def test_expected_classifications_use_only_the_six_values() -> None:
    from backend.domain.contracts import ReconciliationClassification
    from typing import get_args

    allowed = set(get_args(ReconciliationClassification))
    assert len(allowed) == 6
    for row in EXPECTED_MATCHES:
        if row["classification"] is not None:
            assert row["classification"] in allowed


def test_pz900_is_the_true_negative() -> None:
    row = next(r for r in EXPECTED_MATCHES if r["label"] == "PZ-900")
    assert row["card"] is False
    assert row["classification"] is None
    assert row["fee"] == 0.00


def test_unmatched_counts_are_pinned() -> None:
    assert EXPECTED_UNMATCHED_PROCESSOR_COUNT == 0
    assert EXPECTED_UNMATCHED_BANK_COUNT == 1
