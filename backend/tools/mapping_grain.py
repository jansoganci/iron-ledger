"""Deterministic mapping grain for supporting files.

Absence of an Account column does not select file-total mode. File-total is
only for a source whose entire validated scope belongs to one GL account.
"""

from __future__ import annotations

from datetime import date

import pandas as pd

from backend.domain.contracts import DiscoveryPlan

TRUE_ACCOUNT_HEADERS = frozenset(
    {"account", "gl_account", "gl", "acct", "acct_name", "account_name"}
)
IDENTITY_ACCOUNT_HEADERS = frozenset(
    {
        "employee_name",
        "employee",
        "name",
        "customer_name",
        "customer",
        "vendor",
        "vendor_name",
        "supplier",
        "supplier_name",
    }
)
ALLOCATION_HEADERS: dict[str, tuple[str, ...]] = {
    "payroll": ("role", "job_title", "position", "department"),
    "supplier_invoices": ("product_line", "expense_account", "account"),
}

FILE_TOTAL_PATTERN = "(entire file)"
MONTHLY_FEE_HEADERS = frozenset({"monthly_fee", "monthly_amount", "rate", "mrr", "rmr"})


def _norm(header: object) -> str:
    return str(header).strip().lower().replace(" ", "_").replace("-", "_")


def _header_lookup(headers: list[object]) -> dict[str, str]:
    return {_norm(h): str(h) for h in headers if str(h).strip()}


def has_true_account_header(headers: list[object]) -> bool:
    return any(key in TRUE_ACCOUNT_HEADERS for key in _header_lookup(headers))


def allocation_header(file_type: str, headers: list[object]) -> str | None:
    lookup = _header_lookup(headers)
    for alias in ALLOCATION_HEADERS.get(file_type, ()):
        if alias in lookup and alias not in TRUE_ACCOUNT_HEADERS:
            return lookup[alias]
        if alias in lookup and file_type == "supplier_invoices" and alias == "account":
            return lookup[alias]
    return None


def current_account_source(plan: DiscoveryPlan) -> str | None:
    for src, tgt in plan.column_mapping.items():
        if tgt == "account":
            return str(src)
    return None


def retarget_account_column(
    plan: DiscoveryPlan,
    file_type: str,
    headers: list[object],
) -> DiscoveryPlan:
    """Point `account` at an allocation header when discovery used identity.

    Prefer a real account column over identity/allocation fields. File-total
    eligibility is checked separately against the original source schema.
    """
    current = current_account_source(plan)
    if current is not None and _norm(current) in TRUE_ACCOUNT_HEADERS:
        return plan
    lookup = _header_lookup(headers)
    real_account = next(
        (v for k, v in lookup.items() if k in TRUE_ACCOUNT_HEADERS), None
    )
    alloc = real_account or allocation_header(file_type, headers)
    if not alloc:
        return plan
    if current is not None and _norm(current) == _norm(alloc):
        return plan
    mapping = dict(plan.column_mapping)
    if current is not None and _norm(current) in IDENTITY_ACCOUNT_HEADERS:
        mapping[current] = None
    elif current is not None and _norm(current) not in TRUE_ACCOUNT_HEADERS:
        mapping[current] = None
    mapping[alloc] = "account"
    return plan.model_copy(update={"column_mapping": mapping})


def is_file_total_candidate(
    file_type: str,
    headers: list[object],
    *,
    roster_sidecar_present: bool = False,
    unique_source_values: list[str] | None = None,
    amount_scope: str | None = None,
) -> bool:
    """True only when the whole validated scope can belong to one GL account.

    Call this on original file headers, not the post-normalize golden frame
    (that frame always has an `account` column).
    """
    if has_true_account_header(headers):
        return False
    # A missing account column or an empty parsed grain proves nothing. The
    # first delivery supports only the explicit monthly-fee roster contract.
    return (
        file_type == "contracts"
        and roster_sidecar_present
        and _norm(amount_scope) in MONTHLY_FEE_HEADERS
        and _norm(amount_scope) in _header_lookup(headers)
    )


def should_file_total_after_parse(
    file_type: str,
    unique_values: list[str],
    gl_pool: list[str],
    *,
    validated_file_total: bool = False,
) -> bool:
    """Use parser-validated original schema, never filename or account count."""
    return file_type == "contracts" and validated_file_total


def payroll_period_column(headers: list[object]) -> str | None:
    lookup = _header_lookup(headers)
    for alias in ("pay_period", "period", "pay_date"):
        if alias in lookup:
            return lookup[alias]
    return None


def payroll_period_skip_indices(
    promoted: pd.DataFrame,
    file_type: str | None,
    period: date,
) -> set[int]:
    """Row indexes (from `_orig_row_index`) whose Pay Period is not the close month."""
    if file_type != "payroll" or promoted is None or promoted.empty:
        return set()
    period_col = payroll_period_column(list(promoted.columns))
    if period_col is None or "_orig_row_index" not in promoted.columns:
        return set()
    parsed = pd.to_datetime(promoted[period_col], errors="coerce")
    keep = (parsed.dt.year == period.year) & (parsed.dt.month == period.month)
    skip = promoted.loc[~keep.fillna(False), "_orig_row_index"]
    out: set[int] = set()
    for value in skip.tolist():
        try:
            out.add(int(value))
        except (TypeError, ValueError):
            continue
    return out


def payroll_period_filtered(headers: list[object]) -> bool:
    return payroll_period_column(headers) is not None


def proposed_contracts_gl(gl_pool: list[str]) -> str | None:
    """Suggest Service Revenue when it exists. Do not invent Monitoring Revenue."""
    for name in gl_pool:
        if str(name).strip().casefold() == "service revenue":
            return name
    return None
