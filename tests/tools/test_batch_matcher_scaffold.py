"""Item 1 PR-A — inert scaffolding.

Covers only what PR-A ships: deterministic ``match_id`` construction, the
internal ``fee_pct`` gate, the frozen ``BatchMatch`` shape, and proof that the
new file-type literals are NOT wired into detection.

No matcher exists yet, so there are deliberately no ``_classify`` or matching
tests here — those land with PR-B.
"""

from __future__ import annotations

import re
from datetime import date

import pytest

from backend.domain.contracts import BatchMatch, ReconciliationItem
from backend.tools.batch_matcher import build_match_id, fee_pct, norm

# ---------------------------------------------------------------------------
# norm
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("PZ-100", "pz-100"),
        ("  PZ-100  ", "pz-100"),
        ("pz-100", "pz-100"),
        ("DEP-99", "dep-99"),
        (None, None),
        ("", None),
        ("   ", None),
    ],
)
def test_norm(raw, expected) -> None:
    assert norm(raw) == expected


# ---------------------------------------------------------------------------
# match_id — construction per kind (decision E.4)
# ---------------------------------------------------------------------------


def test_match_id_kind_id_is_normalized_join_id() -> None:
    assert build_match_id("id", id_val="PZ-100") == "pz-100"
    assert build_match_id("id", id_val="  pz-100 ") == "pz-100"


def test_match_id_kind_id_rejects_blank() -> None:
    # A blank ref never forms an ID match — it belongs to the amount+date pass.
    for blank in (None, "", "   "):
        with pytest.raises(ValueError, match="non-blank id_val"):
            build_match_id("id", id_val=blank)


def test_match_id_kind_amount_date_uses_group_key() -> None:
    assert (
        build_match_id("amount_date", amount=100.0, day=date(2026, 3, 25))
        == "ad:100.00:2026-03-25"
    )


def test_match_id_amount_date_always_two_decimals() -> None:
    # 1000 and 1000.004 must render identically; the key is rounded currency.
    assert (
        build_match_id("amount_date", amount=1000, day=date(2026, 3, 15))
        == "ad:1000.00:2026-03-15"
    )


def test_match_id_amount_date_requires_full_group_key() -> None:
    with pytest.raises(ValueError, match="group key"):
        build_match_id("amount_date", amount=100.0)
    with pytest.raises(ValueError, match="group key"):
        build_match_id("amount_date", day=date(2026, 3, 25))


def test_match_id_kind_none_with_ref() -> None:
    assert build_match_id("none", side="bank", ref="DEP-99") == "none:bank:dep-99"
    assert build_match_id("none", side="fsm", ref="PZ-777") == "none:fsm:pz-777"


def test_match_id_kind_none_null_ref_uses_amount_date_seq() -> None:
    assert (
        build_match_id(
            "none", side="fsm", ref=None, amount=100.0, day=date(2026, 3, 25), seq=0
        )
        == "none:fsm:100.00:2026-03-25:0"
    )
    assert (
        build_match_id(
            "none", side="fsm", ref="", amount=100.0, day=date(2026, 3, 25), seq=1
        )
        == "none:fsm:100.00:2026-03-25:1"
    )


def test_match_id_kind_none_requires_valid_side() -> None:
    with pytest.raises(ValueError, match="side='fsm' or side='bank'"):
        build_match_id("none", side="gl", ref="X")
    with pytest.raises(ValueError, match="side='fsm' or side='bank'"):
        build_match_id("none", ref="X")


def test_match_id_null_ref_leftover_requires_seq() -> None:
    with pytest.raises(ValueError, match="seq"):
        build_match_id(
            "none", side="bank", ref=None, amount=100.0, day=date(2026, 3, 25)
        )


def test_match_id_rejects_unknown_kind() -> None:
    with pytest.raises(ValueError, match="unknown match_kind"):
        build_match_id("fuzzy", id_val="PZ-100")


# ---------------------------------------------------------------------------
# match_id — no cross-kind collisions
# ---------------------------------------------------------------------------


def test_match_id_kinds_cannot_collide() -> None:
    """The ad: / none: prefixes keep the three kinds in disjoint namespaces."""
    ids = {
        build_match_id("id", id_val="PZ-100"),
        build_match_id("amount_date", amount=100.0, day=date(2026, 3, 25)),
        build_match_id("none", side="bank", ref="DEP-99"),
        build_match_id(
            "none", side="fsm", ref=None, amount=100.0, day=date(2026, 3, 25), seq=0
        ),
        build_match_id(
            "none", side="bank", ref=None, amount=100.0, day=date(2026, 3, 25), seq=0
        ),
    }
    assert len(ids) == 5


def test_same_amount_date_different_side_differ() -> None:
    fsm = build_match_id(
        "none", side="fsm", ref=None, amount=100.0, day=date(2026, 3, 25), seq=0
    )
    bank = build_match_id(
        "none", side="bank", ref=None, amount=100.0, day=date(2026, 3, 25), seq=0
    )
    assert fsm != bank


# ---------------------------------------------------------------------------
# match_id — determinism guard (decision E.4's explicit ban list)
# ---------------------------------------------------------------------------
#
# These exist so that swapping in a UUID, an object-identity hash, or a global
# insertion counter FAILS loudly instead of silently breaking re-run stability.

_UUID_RE = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", re.I
)
_LONG_HEX_RE = re.compile(r"\b[0-9a-f]{16,}\b", re.I)


def _all_kinds() -> list[str]:
    return [
        build_match_id("id", id_val="PZ-100"),
        build_match_id("amount_date", amount=100.0, day=date(2026, 3, 25)),
        build_match_id("none", side="bank", ref="DEP-99"),
        build_match_id(
            "none", side="fsm", ref=None, amount=100.0, day=date(2026, 3, 25), seq=0
        ),
    ]


def test_match_id_is_pure_repeated_calls_identical() -> None:
    first = _all_kinds()
    for _ in range(50):
        assert _all_kinds() == first


def test_match_id_has_no_insertion_counter() -> None:
    """Interleaving other constructions must not perturb a repeated call."""
    a1 = build_match_id("id", id_val="PZ-100")
    build_match_id("id", id_val="PZ-200")
    build_match_id("amount_date", amount=999.0, day=date(2026, 1, 1))
    build_match_id("none", side="bank", ref="DEP-99")
    a2 = build_match_id("id", id_val="PZ-100")
    assert a1 == a2 == "pz-100"


def test_match_id_is_not_a_uuid_or_opaque_hash() -> None:
    for value in _all_kinds():
        assert not _UUID_RE.search(value), f"{value!r} looks like a UUID"
        assert not _LONG_HEX_RE.search(value), f"{value!r} looks like an opaque hash"


def test_match_id_is_derived_from_input_content() -> None:
    """Every component must be traceable to file content, not to runtime state."""
    assert "pz-100" in build_match_id("id", id_val="PZ-100")
    ad = build_match_id("amount_date", amount=100.0, day=date(2026, 3, 25))
    assert "100.00" in ad and "2026-03-25" in ad
    none_id = build_match_id("none", side="bank", ref="DEP-99")
    assert "bank" in none_id and "dep-99" in none_id


# ---------------------------------------------------------------------------
# fee_pct — internal gate, never stored (decision E.1)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "gross,fee,expected",
    [
        (1000.0, 45.0, 0.045),  # PZ-100
        (2000.0, 80.0, 0.04),  # PZ-200
        (500.0, 20.0, 0.04),  # PZ-300
        (600.0, 0.0, 0.0),  # PZ-500
        (300.0, 0.0, 0.0),  # PZ-900
        (-1000.0, -45.0, 0.045),  # sign-independent
    ],
)
def test_fee_pct(gross, fee, expected) -> None:
    assert fee_pct(gross, fee) == pytest.approx(expected)


def test_fee_pct_none_when_gross_is_zero() -> None:
    assert fee_pct(0.0, 0.0) is None
    assert fee_pct(0, 50.0) is None


def test_fee_pct_is_not_a_batchmatch_field() -> None:
    """E.1: computed inline, so there is no serialization path at all."""
    assert "fee_pct" not in BatchMatch.model_fields


# ---------------------------------------------------------------------------
# BatchMatch — frozen shape (C.1)
# ---------------------------------------------------------------------------


def test_batchmatch_field_set_is_exactly_the_frozen_list() -> None:
    assert set(BatchMatch.model_fields) == {
        "match_id",
        "processor_ref",
        "bank_ref",
        "gl_ref",
        "gl_account",
        "gl_amount",
        "gross",
        "fee",
        "net",
        "settlement_date",
        "match_kind",
        "ambiguous",
        "candidate_count",
        "unmatched",
        "classification",
    }


def _sample_match(**overrides) -> BatchMatch:
    payload = {
        "match_id": "pz-100",
        "processor_ref": "PZ-100",
        "bank_ref": "PZ-100",
        "gl_ref": "PZ-100",
        "gl_account": "Undeposited Funds",
        "gl_amount": 1000.0,
        "gross": 1000.0,
        "fee": 45.0,
        "net": 955.0,
        "settlement_date": date(2026, 3, 15),
        "match_kind": "id",
        "ambiguous": False,
        "candidate_count": 1,
        "unmatched": False,
    }
    payload.update(overrides)
    return BatchMatch(**payload)


def test_batchmatch_classification_defaults_to_none() -> None:
    assert _sample_match().classification is None


def test_batchmatch_dump_never_leaks_fee_pct() -> None:
    dumped = _sample_match(classification="structural_explained").model_dump()
    assert "fee_pct" not in dumped
    assert dumped["gross"] == 1000.0 and dumped["net"] == 955.0


def test_batchmatch_rejects_a_seventh_classification() -> None:
    with pytest.raises(Exception):
        _sample_match(classification="unmatched_cash")


def test_batchmatch_match_kind_is_constrained() -> None:
    with pytest.raises(Exception):
        _sample_match(match_kind="fuzzy")


# ---------------------------------------------------------------------------
# ReconciliationItem.matches — additive, backward compatible (E.6)
# ---------------------------------------------------------------------------


def _recon_payload() -> dict:
    return {
        "account": "Undeposited Funds",
        "category": "REVENUE",
        "sources": [],
        "gl_amount": 1000.0,
        "non_gl_total": 1000.0,
        "delta": 0.0,
        "delta_pct": 0.0,
        "severity": "low",
    }


def test_reconciliation_item_matches_defaults_to_none() -> None:
    """Old JSONB without the key must still parse — PR-A changes nothing."""
    assert ReconciliationItem(**_recon_payload()).matches is None


def test_reconciliation_item_accepts_nested_matches() -> None:
    item = ReconciliationItem(**_recon_payload(), matches=[_sample_match()])
    assert item.matches is not None
    assert item.matches[0].match_id == "pz-100"


# ---------------------------------------------------------------------------
# FILE-TYPE DETECTION — went live in PR-B
# ---------------------------------------------------------------------------
#
# PR-A shipped these literals unwired on purpose; PR-B wires them now that a
# matcher exists behind them. What must NOT change: files that are not
# genuinely bank/processor shaped still resolve exactly as before.


def test_new_file_types_are_wired() -> None:
    from backend.agents.orchestrator import _FILE_TYPE_PATTERNS

    assert "bank_statement" in _FILE_TYPE_PATTERNS
    assert "processor_settlement" in _FILE_TYPE_PATTERNS


def test_new_types_are_matched_last_so_existing_types_win_on_overlap() -> None:
    from backend.agents.orchestrator import _FILE_TYPE_PATTERNS

    keys = list(_FILE_TYPE_PATTERNS)
    for pre_existing in ("general_ledger", "payroll", "contracts", "supplier_invoices"):
        assert keys.index(pre_existing) < keys.index("bank_statement")
        assert keys.index(pre_existing) < keys.index("processor_settlement")


@pytest.mark.parametrize(
    "filename,expected",
    [
        ("vandelay_shopify_payouts_mar_2026.xlsx", "processor_settlement"),
        ("stripe_payouts.xlsx", "processor_settlement"),
        ("vandelay_amazon_settlement_mar_2026.xlsx", "processor_settlement"),
        ("paypal_march.csv", "processor_settlement"),
        ("bank_statement.csv", "bank_statement"),
        ("kova_cash_bank_mar_2026.csv", "bank_statement"),
        ("checking_march.csv", "bank_statement"),
    ],
)
def test_genuinely_bank_or_processor_files_now_route(filename, expected) -> None:
    from backend.agents.orchestrator import _detect_file_type

    assert _detect_file_type(filename) == expected


@pytest.mark.parametrize(
    "filename,expected",
    [
        # Pre-existing behaviour must be untouched.
        ("sentinel_gl_mar_2026.xlsx", "general_ledger"),
        ("quickbooks_export.xlsx", "general_ledger"),
        ("helix_payroll_mar_2026.xlsx", "payroll"),
        ("gusto_salaries.csv", "payroll"),
        ("sentinel_contracts_mar_2026.xlsx", "contracts"),
        ("vendor_invoices_march.xlsx", "supplier_invoices"),
        ("ap_bills.csv", "supplier_invoices"),
        ("vandelay_inventory_purchases_mar_2026.xlsx", "supplier_invoices"),
        # Generic unknowns still fall back, exactly as before.
        ("mystery_file.xlsx", "supplier_invoices"),
        ("march_data.csv", "supplier_invoices"),
    ],
)
def test_non_bank_files_are_unaffected(filename, expected) -> None:
    from backend.agents.orchestrator import _detect_file_type

    assert _detect_file_type(filename) == expected


@pytest.mark.parametrize(
    "filename",
    [
        "income_statement.xlsx",
        "profit_and_loss_statement.xlsx",
        "financial_statement_q1.csv",
    ],
)
def test_pl_statements_are_not_captured_as_bank_files(filename) -> None:
    """Why bare "statement" is deliberately not a bank needle.

    C.2 lists it, but it would swallow every P&L export named "...statement".
    The conservative list uses "bank" / "bank_statement" instead. See the
    deviation note in the PR-B commit message.
    """
    from backend.agents.orchestrator import _detect_file_type

    assert _detect_file_type(filename) != "bank_statement"


def test_customer_deposit_files_are_not_stolen_by_the_bank_needles() -> None:
    """C.2: "do not steal `deposit` from customer-deposit files"."""
    from backend.agents.orchestrator import _detect_file_type

    assert _detect_file_type("customer_deposits_mar_2026.xlsx") != "bank_statement"
