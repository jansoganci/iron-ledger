"""Unit tests for deterministic payroll account tagging."""

from __future__ import annotations

import pytest

from backend.tools.account_tags import is_payroll_account


@pytest.mark.parametrize(
    "name",
    [
        "Payroll Expense",
        "Wages Payable",
        "Salaries & Wages",
        "Officer Compensation",
        "PAYROLL",
        "Accrued salaries",
    ],
)
def test_payroll_names_match(name: str) -> None:
    assert is_payroll_account(name) is True


@pytest.mark.parametrize(
    "name",
    [
        "Vendor Name",
        "Account Number",
        "Office Rent",
        "Revenue",
        "Accounts Payable",
        "",
    ],
)
def test_non_payroll_names_do_not_match(name: str) -> None:
    assert is_payroll_account(name) is False
