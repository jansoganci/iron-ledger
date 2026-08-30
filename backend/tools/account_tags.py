"""Deterministic account-name tags. No DB, no LLM, no I/O."""

from __future__ import annotations

# Case-insensitive substring needles. Keep this list narrow — a false
# positive promotes a G&A/OPEX line into the tight Tier 2 flux gates.
# "salary" already matches "salaries"; both are listed so the intent is obvious.
_PAYROLL_NEEDLES: tuple[str, ...] = (
    "payroll",
    "wages",
    "salary",
    "salaries",
    "compensation",
)


def is_payroll_account(account_name: str | None) -> bool:
    """Return True if *account_name* looks like a payroll GL account.

    Same pattern as ``pii_sanitizer._header_matches``: case-insensitive
    substring. Mapping (Haiku) is not involved — call this on the canonical
    GL name after AccountMapper has already assigned a US GAAP category.
    """
    if not account_name:
        return False
    lowered = account_name.lower()
    return any(needle in lowered for needle in _PAYROLL_NEEDLES)
