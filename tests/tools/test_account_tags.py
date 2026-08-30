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
        "salary",
    ],
)
def test_salary_wages_compensation_needles(name: str) -> None:
    assert is_payroll_account(name) is True


def test_case_insensitive() -> None:
    assert is_payroll_account("SALARIES & WAGES") is True


@pytest.mark.parametrize(
    "name",
    [
        "Rent",
        "Installation Revenue",
        "Bank Charges",
        "Office Rent",
        "Revenue",
        "Accounts Payable",
    ],
)
def test_non_payroll_name_false(name: str) -> None:
    assert is_payroll_account(name) is False


def test_empty_and_none_safe() -> None:
    assert is_payroll_account("") is False
    assert is_payroll_account(None) is False
