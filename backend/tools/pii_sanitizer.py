from __future__ import annotations

import re

import pandas as pd

from backend.domain.errors import FileHasNoValidColumns
from backend.logger import get_logger, get_trace_id

logger = get_logger(__name__)

# SSN value-level regex: 000-00-0000 or 000000000
# Anchored — used by the column-level detector (whole column is SSNs).
_SSN_REGEX = re.compile(r"^\d{3}-?\d{2}-?\d{4}$")

# Regexes for sanitize_sample — run on raw cell values BEFORE Discovery's
# LLM call. Tight by design: must not match legitimate accounting values
# like "4000 - HobiFly X1", "03/31/2026", or "45000".
# Hyphenated-only SSN avoids collisions with invoice numbers.
_SSN_EMBEDDED_RE = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_CC_RE = re.compile(r"\b\d{4}[- ]?\d{4}[- ]?\d{4}[- ]?\d{4}\b")

_REDACTED = "[REDACTED]"

# Maximum input length for _scrub_value — guards against catastrophic
# regex backtracking on pathological input. 40-char output means we never
# need more than ~60 input chars for correctness; 200 is generous.
_SCRUB_INPUT_CAP = 200


def _scrub_value(s: str) -> str:
    """Substring-level PII scrub for free-text strings.

    Unlike sanitize_sample (which replaces an entire cell on any match),
    _scrub_value replaces only the matched substrings in-place so
    surrounding context is preserved. Used by the Normalizer's drop
    report to build account_snippets the user can eyeball safely.

    Caller order invariant: SCRUB FIRST, TRUNCATE SECOND.
      snippet = _scrub_value(raw)[:40]
    Reversing this would let a truncated prefix of a PII match escape
    detection (e.g. "alice@" with no TLD no longer matches the email regex).

    Empty / None-safe: returns "" for falsy input.
    """
    if not s:
        return ""
    capped = s[:_SCRUB_INPUT_CAP]
    capped = _CC_RE.sub(_REDACTED, capped)
    capped = _SSN_EMBEDDED_RE.sub(_REDACTED, capped)
    capped = _EMAIL_RE.sub(_REDACTED, capped)
    return capped


# 20% threshold for value-level SSN drop
_SSN_VALUE_THRESHOLD = 0.20

# Header blacklist — case-insensitive substring match.
# Conservative bias: bare name/address/phone/email/account are intentionally absent.
# See docs/agent-flow.md §Agent 1 Step 4 for rationale.
_ALWAYS_DROP: list[str] = [
    # SSN / Tax ID
    "ssn",
    "social_security",
    "social security",
    "taxpayer_id",
    "tax_id",
    "tin",
    # Date of Birth
    "dob",
    "date_of_birth",
    "date of birth",
    "birth_date",
    "birthdate",
    "birthday",
    # Home Address
    "home_address",
    "residence",
    "street_address",
    "zip_code",
    "postal_code",
    "mailing_address",
    # Bank Account / Routing
    "bank_account",
    "account_number",
    "routing_number",
    "iban",
    "swift_code",
    "aba_routing",
    # Personal Contact
    "phone_number",
    "mobile_phone",
    "cell_phone",
    "personal_email",
    "home_phone",
    "home_email",
]

# Personal name substrings dropped only when employee_id column is present
_NAME_WHEN_EMPLOYEE_ID: list[str] = [
    "first_name",
    "last_name",
    "full_name",
    "employee_name",
    "personal_name",
]


def _header_matches(col: str, substrings: list[str]) -> bool:
    col_lower = col.lower()
    return any(s in col_lower for s in substrings)


def _ssn_value_match_ratio(series: pd.Series) -> float:
    non_null = series.dropna().astype(str)
    if len(non_null) == 0:
        return 0.0
    matches = non_null.apply(lambda v: bool(_SSN_REGEX.match(v))).sum()
    return matches / len(non_null)


def sanitize(
    df: pd.DataFrame,
    run_id: str = "",
) -> pd.DataFrame:
    """Strip PII columns from *df* before pandera validation and any Claude call.

    Returns the sanitized DataFrame. Raises FileHasNoValidColumns if nothing survives.
    Never logs cell values — only column names and counts.
    """
    columns_before = list(df.columns)
    has_employee_id = any("employee_id" in str(c).lower() for c in df.columns)
    cols_to_drop: list[str] = []

    for col in df.columns:
        col_str = str(col)
        if _header_matches(col_str, _ALWAYS_DROP):
            cols_to_drop.append(col_str)
            continue
        if has_employee_id and _header_matches(col_str, _NAME_WHEN_EMPLOYEE_ID):
            cols_to_drop.append(col_str)
            continue
        # Value-level fallback: SSN regex on unmapped columns
        if _ssn_value_match_ratio(df[col]) >= _SSN_VALUE_THRESHOLD:
            cols_to_drop.append(col_str)

    dropped = [c for c in cols_to_drop if c in df.columns]
    df = df.drop(columns=dropped, errors="ignore")

    logger.info(
        "pii_sanitization complete",
        extra={
            "event": "pii_sanitization",
            "trace_id": get_trace_id(),
            "run_id": run_id,
            "columns_dropped": dropped,
            "rows_in_file": len(df),
            "strategy": "header_blacklist+ssn_regex",
        },
    )

    remaining = [c for c in df.columns if c not in dropped]
    if not remaining:
        raise FileHasNoValidColumns(
            f"All {len(columns_before)} columns were dropped during PII sanitization"
        )

    return df


def sanitize_sample(
    rows: list[dict],
    run_id: str = "",
) -> list[dict]:
    """Redact value-level PII from the Discovery sample before Claude sees it.

    Scope (regex-only, deliberately narrow — see docs/sprint/discovery-layer-plan.md §Step 3.5):
      - SSN (hyphenated): 123-45-6789
      - Email: alice@example.com
      - Credit card: 16-digit runs with optional separators

    Out of scope (not regex-reliable — handled column-level by sanitize()):
      - Personal names, home addresses, phone numbers, DOB

    Non-destructive: row count, column width, None cells, and visual flags
    (is_bold / indent_level / is_merged) are preserved. Only matching cell
    values are replaced with "[REDACTED]".

    Never logs cell values. Logs only counts + categories.
    """
    redacted: dict[str, int] = {"ssn": 0, "email": 0, "cc": 0}
    out: list[dict] = []

    for row in rows:
        new_values = []
        for v in row["values"]:
            if v is None:
                new_values.append(v)
                continue
            s = str(v)
            category: str | None = None
            if _CC_RE.search(s):
                category = "cc"
            elif _SSN_EMBEDDED_RE.search(s):
                category = "ssn"
            elif _EMAIL_RE.search(s):
                category = "email"

            if category is not None:
                redacted[category] += 1
                new_values.append(_REDACTED)
            else:
                new_values.append(v)
        out.append({**row, "values": new_values})

    total = sum(redacted.values())
    logger.info(
        "pii_sanitization_sample complete",
        extra={
            "event": "pii_sanitization_sample",
            "trace_id": get_trace_id(),
            "run_id": run_id,
            "cells_redacted": total,
            "categories": redacted,
        },
    )
    return out


def build_preview_snippet(
    sample: list[dict],
    max_rows: int = 20,
    max_cols: int = 10,
) -> list[list]:
    """Extract a 2D cell-value snippet for `discovery_plan._preview` (D7).

    Used by ParserAgent.discover() (Step 9b) to attach a compact sample to
    the DiscoveryPlan dict before persistence so the frontend's
    DiscoveryConfirmationModal can render header-row context without a
    second file fetch.

    Caller MUST have already run `sanitize_sample()` on the input — this
    helper does NOT re-sanitize. It just slices and returns plain cell
    values (not the full row dict with flags).
    """
    snippet: list[list] = []
    for row in sample[:max_rows]:
        values = list(row.get("values", []))[:max_cols]
        snippet.append(values)
    return snippet
