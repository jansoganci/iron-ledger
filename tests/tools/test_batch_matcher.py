"""Item 1 PR-B — the three-pass matcher and `_classify`.

Every row the spec pins in C.5.3 gets an assertion here: exact classification
and card/no-card status. Plus the two interactions the spec's own
re-verification flagged as load-bearing:

  (a) PZ-500 survives only because rule 4 (wrong account) outranks rule 6
      (the $0 drop). Proven by running a deliberately mis-ordered double.
  (b) test_does_not_match_on_gross_against_net — the E.5 guarantee.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from backend.domain.contracts import BatchMatch
from backend.tools.batch_matcher import (
    _FEE_BAND_MAX,
    _FEE_BAND_MIN,
    fee_pct,
    last_day_of,
    match,
    residue_classification,
)

FIXTURE_DIR = Path(__file__).parent / "fixtures"
PERIOD = date(2026, 3, 1)
UF = "Undeposited Funds"


def _load_sidecars() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Build the three canonical sidecar frames from the checked-in CSVs.

    This is the shape Discovery will hand the matcher in production: raw
    headers renamed onto the C.5.1 canonical names, `_orig_row_index`
    preserved, and the GL frame filtered to rows that carry a ref OR sit on the
    UF account ("Do not sidecar Rent").
    """
    fsm = pd.read_csv(
        FIXTURE_DIR / "kova_cash_fsm_mar_2026.csv", dtype={"payout_id": "string"}
    )
    fsm["_orig_row_index"] = range(len(fsm))

    gl = pd.read_csv(
        FIXTURE_DIR / "kova_cash_gl_mar_2026.csv", dtype={"memo": "string"}
    )
    gl["_orig_row_index"] = range(len(gl))
    gl = gl.rename(
        columns={"memo": "gl_ref", "account": "gl_account", "date": "gl_date"}
    )
    gl = gl[gl["gl_ref"].notna() | (gl["gl_account"] == UF)]

    bank = pd.read_csv(
        FIXTURE_DIR / "kova_cash_bank_mar_2026.csv", dtype={"bank_ref": "string"}
    )
    bank["_orig_row_index"] = range(len(bank))
    return fsm, gl, bank


@pytest.fixture(scope="module")
def result():
    fsm, gl, bank = _load_sidecars()
    return match(fsm, gl, bank, PERIOD, UF)


@pytest.fixture(scope="module")
def by_id(result):
    return {m.match_id: m for m in result.matches}


# ---------------------------------------------------------------------------
# Every pinned row (C.5.3 expected matcher output)
# ---------------------------------------------------------------------------


def test_period_end_is_last_day_of_march():
    assert last_day_of(PERIOD) == date(2026, 3, 31)


def test_card_count_is_six(result) -> None:
    assert len(result.matches) == 6


@pytest.mark.parametrize(
    "match_id,kind,gross,net,fee,settle,gl_account,classification",
    [
        (
            "pz-100",
            "id",
            1000.00,
            955.00,
            45.00,
            date(2026, 3, 15),
            UF,
            "structural_explained",
        ),
        (
            "pz-200",
            "id",
            2000.00,
            1920.00,
            80.00,
            date(2026, 4, 2),
            UF,
            "timing_cutoff",
        ),
        (
            "pz-300",
            "id",
            500.00,
            480.00,
            20.00,
            date(2026, 3, 20),
            None,
            "missing_je",
        ),
        (
            "none:bank:dep-99",
            "none",
            750.00,
            750.00,
            0.00,
            date(2026, 3, 22),
            None,
            "missing_je",
        ),
        (
            "pz-500",
            "id",
            600.00,
            600.00,
            0.00,
            date(2026, 3, 18),
            "Accounts Receivable",
            "categorical_misclassification",
        ),
        (
            "ad:100.00:2026-03-25",
            "amount_date",
            100.00,
            100.00,
            0.00,
            date(2026, 3, 25),
            None,
            "stale_reference",
        ),
    ],
)
def test_pinned_row(
    by_id, match_id, kind, gross, net, fee, settle, gl_account, classification
) -> None:
    m = by_id[match_id]
    assert m.match_kind == kind
    assert m.gross == gross
    assert m.net == net
    assert m.fee == fee
    assert m.settlement_date == settle
    assert m.gl_account == gl_account
    assert m.classification == classification


def test_pz900_is_the_true_negative_no_card(by_id) -> None:
    """Clean three-way tie-out is dropped by rule 6 — zero cards for PZ-900."""
    assert "pz-900" not in by_id


def test_ambiguous_pair_is_one_card_with_candidate_count_two(by_id) -> None:
    m = by_id["ad:100.00:2026-03-25"]
    assert m.ambiguous is True
    assert m.unmatched is True
    # max(nf, ng, nb) = max(2, 0, 2). Counting members would give 4.
    assert m.candidate_count == 2


def test_unmatched_counters(result) -> None:
    assert result.unmatched_processor_count == 0
    assert result.unmatched_bank_count == 1  # DEP-99


def test_only_the_six_classes_appear(result) -> None:
    from typing import get_args

    from backend.domain.contracts import ReconciliationClassification

    allowed = set(get_args(ReconciliationClassification))
    assert len(allowed) == 6
    for m in result.matches:
        assert m.classification in allowed


# ---------------------------------------------------------------------------
# (a) PZ-500 survives only because rule 4 outranks rule 6
# ---------------------------------------------------------------------------


def _classify_with_rules_4_and_6_swapped(
    m: BatchMatch, period_end: date, uf_account_name: str
) -> BatchMatch | None:
    """Deliberately mis-ordered double: the $0 drop runs BEFORE wrong-account.

    Used only to prove the real ordering matters. Not production code.
    """
    has_gl = m.gl_account is not None or m.gl_ref is not None or m.gl_amount is not None
    pct = fee_pct(m.gross, m.fee)
    if m.ambiguous:
        m.classification = "stale_reference"
        return m
    if m.settlement_date is not None and m.settlement_date > period_end:
        m.classification = "timing_cutoff"
        return m
    if not has_gl:
        m.classification = "missing_je"
        return m
    # ---- swapped: rule 6 before rule 4 ----
    if (
        m.fee == 0
        and m.gl_amount is not None
        and round(m.gl_amount, 2) == round(m.net, 2)
    ):
        return None
    if m.gl_account != uf_account_name:
        m.classification = "categorical_misclassification"
        return m
    if pct is not None and _FEE_BAND_MIN <= pct <= _FEE_BAND_MAX:
        m.classification = "structural_explained"
        return m
    m.classification = "stale_reference"
    return m


def _pz500_shaped() -> BatchMatch:
    """PZ-500: fee 0.00 and gl_amount == net — rule 6's drop condition verbatim."""
    return BatchMatch(
        match_id="pz-500",
        processor_ref="PZ-500",
        bank_ref="PZ-500",
        gl_ref="PZ-500",
        gl_account="Accounts Receivable",
        gl_amount=600.00,
        gross=600.00,
        fee=0.00,
        net=600.00,
        settlement_date=date(2026, 3, 18),
        match_kind="id",
        ambiguous=False,
        candidate_count=1,
        unmatched=False,
    )


def test_pz500_would_wrongly_vanish_if_rule6_outranked_rule4() -> None:
    """The failure mode the real ordering prevents."""
    wrong = _classify_with_rules_4_and_6_swapped(_pz500_shaped(), date(2026, 3, 31), UF)
    assert wrong is None, "mis-ordered double should silently drop PZ-500"


def test_pz500_survives_under_the_real_rule_order(by_id) -> None:
    m = by_id["pz-500"]
    assert m.fee == 0.00
    assert m.gl_amount == m.net  # rule 6's drop condition is satisfied...
    # ...but rule 4 fires first because the GL booked it to the wrong account.
    assert m.classification == "categorical_misclassification"


# ---------------------------------------------------------------------------
# (b) gross-vs-net (the E.5 guarantee)
# ---------------------------------------------------------------------------


def test_does_not_match_on_gross_against_net() -> None:
    """PZ-100 with ids stripped must NOT become structural_explained.

    FSM/GL group uniquely on 1000.00 with no bank row -> N1.3 sets net := gross,
    fee = 0.00, and rule 6 drops the card. The bank 955.00 falls to Pass 3 and
    hits rule 3 (no GL) -> missing_je. The bank row's own fee_pct of 0.045 is
    never reached.
    """
    fsm = pd.DataFrame(
        [
            {
                "payout_id": None,
                "collected_date": "2026-03-15",
                "gross": 1000.00,
                "_orig_row_index": 0,
            }
        ]
    )
    gl = pd.DataFrame(
        [
            {
                "gl_ref": None,
                "gl_account": UF,
                "amount": 1000.00,
                "gl_date": "2026-03-15",
                "_orig_row_index": 0,
            }
        ]
    )
    bank = pd.DataFrame(
        [
            {
                "bank_ref": None,
                "settlement_date": "2026-03-15",
                "gross": 1000.00,
                "net": 955.00,
                "_orig_row_index": 0,
            }
        ]
    )

    result = match(fsm, gl, bank, PERIOD, UF)
    classes = {m.classification for m in result.matches}

    assert "structural_explained" not in classes
    assert classes == {"missing_je"}
    assert len(result.matches) == 1
    assert result.matches[0].net == 955.00
    assert result.unmatched_bank_count == 1


def test_gross_and_net_only_group_when_fee_is_zero() -> None:
    """The zero tolerance IS the guarantee — 1000.00 and 955.00 never meet."""
    fsm = pd.DataFrame(
        [
            {
                "payout_id": None,
                "collected_date": "2026-03-15",
                "gross": 1000.00,
                "_orig_row_index": 0,
            }
        ]
    )
    bank = pd.DataFrame(
        [
            {
                "bank_ref": None,
                "settlement_date": "2026-03-15",
                "gross": 1000.00,
                "net": 955.00,
                "_orig_row_index": 0,
            }
        ]
    )
    result = match(fsm, None, bank, PERIOD, UF)
    # Different amounts -> different groups -> two leftovers, no fee story.
    assert all(m.match_kind == "none" for m in result.matches)
    assert "structural_explained" not in {m.classification for m in result.matches}


# ---------------------------------------------------------------------------
# N / S rules (E.2 / E.3)
# ---------------------------------------------------------------------------


def test_no_bank_row_sets_net_to_gross_and_fee_to_zero() -> None:
    """N1.3. A clean FSM<->GL pair on the UF account is dropped, not a 100% fee."""
    fsm = pd.DataFrame(
        [
            {
                "payout_id": "PZ-777",
                "collected_date": "2026-03-05",
                "gross": 400.00,
                "_orig_row_index": 0,
            }
        ]
    )
    gl = pd.DataFrame(
        [
            {
                "gl_ref": "PZ-777",
                "gl_account": UF,
                "amount": 400.00,
                "gl_date": "2026-03-05",
                "_orig_row_index": 0,
            }
        ]
    )
    result = match(fsm, gl, None, PERIOD, UF)
    assert result.matches == []  # rule 6 drop, no spurious stale_reference


def test_no_bank_row_can_never_be_timing_cutoff() -> None:
    """S2 + rule 2's None guard, even with a very late FSM/GL date."""
    fsm = pd.DataFrame(
        [
            {
                "payout_id": "PZ-888",
                "collected_date": "2026-04-30",
                "gross": 400.00,
                "_orig_row_index": 0,
            }
        ]
    )
    gl = pd.DataFrame(
        [
            {
                "gl_ref": "PZ-888",
                "gl_account": "Accounts Receivable",
                "amount": 400.00,
                "gl_date": "2026-04-30",
                "_orig_row_index": 0,
            }
        ]
    )
    result = match(fsm, gl, None, PERIOD, UF)
    assert len(result.matches) == 1
    assert result.matches[0].settlement_date is None
    assert result.matches[0].classification != "timing_cutoff"
    assert result.matches[0].classification == "categorical_misclassification"


def test_settlement_date_comes_only_from_the_bank_row(by_id) -> None:
    """S1. PZ-200's FSM and GL dates are both 2026-03-31, inside the period."""
    m = by_id["pz-200"]
    assert m.settlement_date == date(2026, 4, 2)
    assert m.classification == "timing_cutoff"


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------


def test_matcher_is_deterministic_across_runs() -> None:
    fsm, gl, bank = _load_sidecars()
    runs = [
        [
            (m.match_id, m.classification)
            for m in match(fsm, gl, bank, PERIOD, UF).matches
        ]
        for _ in range(5)
    ]
    assert all(r == runs[0] for r in runs)


def test_match_ids_are_unique(result) -> None:
    ids = [m.match_id for m in result.matches]
    assert len(set(ids)) == len(ids)


def test_empty_input_yields_nothing() -> None:
    result = match(None, None, None, PERIOD, UF)
    assert result.matches == []
    assert result.unmatched_processor_count == 0
    assert result.unmatched_bank_count == 0


# ---------------------------------------------------------------------------
# Account-level residue (E.6)
# ---------------------------------------------------------------------------


def _m(classification: str) -> BatchMatch:
    return BatchMatch(
        match_id=f"x-{classification}",
        processor_ref=None,
        bank_ref=None,
        gl_ref=None,
        gl_account=None,
        gl_amount=None,
        gross=0.0,
        fee=0.0,
        net=0.0,
        settlement_date=None,
        match_kind="id",
        ambiguous=False,
        candidate_count=1,
        unmatched=False,
        classification=classification,
    )


@pytest.mark.parametrize(
    "present,expected",
    [
        (["structural_explained", "missing_je"], "missing_je"),
        (
            ["timing_cutoff", "categorical_misclassification"],
            "categorical_misclassification",
        ),
        (["structural_explained", "timing_cutoff"], "timing_cutoff"),
        (["stale_reference", "timing_cutoff"], "stale_reference"),
        (["structural_explained"], "structural_explained"),
    ],
)
def test_residue_picks_most_action_requiring(present, expected) -> None:
    assert residue_classification([_m(c) for c in present]) == expected


def test_residue_is_none_without_matches() -> None:
    assert residue_classification([]) is None


def test_fixture_residue_is_missing_je(result) -> None:
    """A card must not read 'no action required' over a missing JE."""
    assert residue_classification(result.matches) == "missing_je"
