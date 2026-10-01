"""Payroll roles are confirmed one by one against this period's GL accounts.

Redhawk March 2026 fixture. No LLM, no I/O. Sums are pandas.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from backend import messages
from backend.agents.consolidator import consolidate
from backend.domain.contracts import MappingDraft
from backend.tools.close_controls import build_control_summary
from backend.tools.source_mapping import (
    mapping_confirmation_error,
    payroll_draft_items,
)

PERIOD = date(2026, 3, 1)
REDHAWK = Path(__file__).resolve().parents[2] / "docs" / "demo_data" / "redhawk"
APPROVED = {
    "Install Technician": "Technician Wages",
    "Lead Install Technician": "Technician Wages",
    "Service Technician": "Technician Wages",
    "Office Administrator": "Admin Wages",
    "Owner / Operations": "Owner Salary",
}


def _gl() -> pd.DataFrame:
    raw = pd.read_excel(REDHAWK / "redhawk_gl_mar_2026.xlsx", header=4)
    raw = raw[raw["Account"].notna() & raw["Amount"].notna()]
    return pd.DataFrame(
        {
            "account": raw["Account"].astype(str),
            "category": "OPEX",
            "amount": raw["Amount"].astype(float),
        }
    )


def _payroll() -> pd.DataFrame:
    raw = pd.read_excel(REDHAWK / "redhawk_payroll_mar_2026.xlsx")
    return pd.DataFrame(
        {
            "account": raw["Role"].astype(str).str.strip(),
            "category": "OPEX",
            "amount": raw["Base Compensation"].astype(float),
        }
    )


def _draft() -> MappingDraft:
    roles = sorted(_payroll()["account"].unique())
    return MappingDraft(
        items=payroll_draft_items(
            roles,
            source_file="redhawk_payroll_mar_2026.xlsx",
            amount_scope="Base Compensation",
            period=PERIOD,
        ),
        gl_account_pool=sorted(_gl()["account"].unique()),
    )


def test_five_roles_are_listed_unselected_with_gl_targets_only() -> None:
    draft = _draft()
    assert sorted(i.source_pattern for i in draft.items) == sorted(APPROVED)
    assert all(i.suggested_gl_account is None for i in draft.items)
    assert "Technician Wages" in draft.gl_account_pool
    assert not set(APPROVED) & set(draft.gl_account_pool)


def test_unconfirmed_or_invalid_payroll_mapping_is_rejected() -> None:
    draft = _draft()
    assert (
        mapping_confirmation_error(draft, {}, {})
        == messages.MAPPING_CONFIRMATION_REQUIRED
    )
    partial = dict(APPROVED)
    partial.pop("Owner / Operations")
    assert (
        mapping_confirmation_error(draft, partial, {})
        == messages.MAPPING_CONFIRMATION_REQUIRED
    )
    identity = {**APPROVED, "Owner / Operations": "Owner / Operations"}
    assert (
        mapping_confirmation_error(draft, identity, {})
        == messages.MAPPING_INVALID_GL_ACCOUNT
    )
    assert mapping_confirmation_error(draft, APPROVED, {}) is None


def test_approved_roles_tie_out_and_leave_no_missing_je() -> None:
    gl, payroll = _gl(), _payroll()
    mapped = payroll.assign(account=payroll["account"].map(APPROVED))
    assert not mapped["account"].isna().any()
    totals = mapped.groupby("account")["amount"].sum().round(2).to_dict()
    assert totals == {
        "Technician Wages": 6200.0,
        "Admin Wages": 1400.0,
        "Owner Salary": 5500.0,
    }

    consolidated, recon = consolidate(
        [
            ("redhawk_gl_mar_2026.xlsx", gl),
            (
                "redhawk_payroll_mar_2026.xlsx",
                mapped.groupby("account", as_index=False)["amount"]
                .sum()
                .assign(category="OPEX"),
            ),
        ]
    )
    book = consolidated.set_index("account")["amount"].to_dict()
    assert book["Technician Wages"] == pytest.approx(6200.0)
    assert book["Admin Wages"] == pytest.approx(1400.0)
    assert book["Owner Salary"] == pytest.approx(5500.0)
    classes = {getattr(i, "classification", None) for i in recon}
    assert "missing_je" not in classes
    assert not any(
        i.account in APPROVED for i in recon
    ), "role names must not survive as accounts"

    summary = build_control_summary(
        period=PERIOD,
        source_files=["redhawk_gl_mar_2026.xlsx", "redhawk_payroll_mar_2026.xlsx"],
        per_file_rows={
            "redhawk_payroll_mar_2026.xlsx": [
                {"account": a, "amount": v} for a, v in totals.items()
            ]
        },
        gl_amounts=dict(zip(gl["account"], gl["amount"])),
        amount_scopes={"redhawk_payroll_mar_2026.xlsx": "Base Compensation"},
        file_total_mappings={},
        mapping_pending_files=set(),
        recon_items=[],
        mapping_modes={"redhawk_payroll_mar_2026.xlsx": "row"},
    )
    payroll_control = next(c for c in summary.controls if c.key == "payroll")
    assert payroll_control.status == "tied_out"
    assert {c.gl_account for c in payroll_control.comparisons} == set(totals)
    assert all(c.difference == 0 for c in payroll_control.comparisons)
