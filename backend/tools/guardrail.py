from __future__ import annotations

import re

from backend.logger import get_logger, get_trace_id

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Rollout flag — narrative consistency (Stage 1)
# ---------------------------------------------------------------------------

# Stage 1 checks that every number written in the narrative also appears in
# numbers_used. It is MEASUREMENT-ONLY for one release: violations are logged
# at WARNING and the report still saves.
#
# Flip to True to make an unlisted narrative number fail the report. This is a
# deliberate, named switch — do not re-express it as an inline conditional and
# do not flip it without an explicit decision. See
# docs/sprint/guardrail-fix-pre-analysis.md, decision 3.
ENFORCE_NARRATIVE_CONSISTENCY = False


# ---------------------------------------------------------------------------
# Tolerances — unit-aware
# ---------------------------------------------------------------------------

# Money: cent precision. The relative term only binds above $10,000 and exists
# solely to absorb float64 representation noise (at $1M it is $1.00).
_MONEY_ABS_FLOOR = 0.01
_MONEY_REL = 1e-6

# Percent: percentage points. variance_pct is already round(..., 2), so a
# verbatim copy is exact; 0.05pp absorbs a one-decimal rendering (61.07 -> 61.1)
# without admitting a fabricated percentage.
_PCT_TOLERANCE = 0.05

# Legacy tolerance — retained ONLY for callers not yet migrated to strict mode
# (quarterly.py, opus_upgrade.py). max(1% of ref, $1,000). Do not use for new
# call sites: on SMB-scale data it accepts ~41% of invented dollar values,
# because percentages share the reference pool with dollars and each one
# whitelists a +/-$1,000 band.
_LEGACY_DOLLAR_FLOOR = 1_000.0
_LEGACY_REL = 0.01


def money_tolerance(ref: float) -> float:
    """Allowed absolute deviation for a dollar reference value."""
    return max(_MONEY_ABS_FLOOR, _MONEY_REL * abs(ref))


def pct_tolerance(ref: float) -> float:
    """Allowed deviation, in percentage points, for a percentage reference."""
    return _PCT_TOLERANCE


def _tolerance_for(pandas_val: float) -> float:
    """Legacy tolerance: max(1% of |pandas_val|, $1,000).

    Kept for un-migrated callers only. See _LEGACY_* above.
    """
    return max(_LEGACY_REL * abs(pandas_val), _LEGACY_DOLLAR_FLOOR)


# ---------------------------------------------------------------------------
# Reference flattening
# ---------------------------------------------------------------------------

# Keys whose values are percentages, not dollars. Grounded in real field names:
# AccountSummary.variance_pct, ReconciliationItem.delta_pct, and quarterly's
# yoy_revenue_pct / yoy_gross_margin_delta / yoy_opex_pct.
_PCT_KEY_RE = re.compile(r"pct|percent|margin", re.IGNORECASE)


def flatten_summary(d: dict) -> list[float]:
    """Recursively extract all numeric leaf values from a nested dict.

    Unit-blind. Retained for the legacy path and for callers that only need a
    flat pool; strict mode uses flatten_summary_by_unit instead.
    """
    values: list[float] = []
    for v in d.values():
        if isinstance(v, dict):
            values.extend(flatten_summary(v))
        elif isinstance(v, (int, float)) and not isinstance(v, bool):
            values.append(float(v))
    return values


def flatten_summary_by_unit(d: dict) -> tuple[list[float], list[float]]:
    """Split numeric leaves into (money_values, percent_values) by key name.

    Keeping the two apart is the structural half of the guardrail fix: in one
    shared pool a percentage reference and a dollar reference are
    indistinguishable, so whichever tolerance is looser governs both.
    """
    money: list[float] = []
    percent: list[float] = []

    def _walk(node: dict) -> None:
        for key, v in node.items():
            if isinstance(v, dict):
                _walk(v)
            elif isinstance(v, (int, float)) and not isinstance(v, bool):
                if _PCT_KEY_RE.search(str(key)):
                    percent.append(float(v))
                else:
                    money.append(float(v))

    _walk(d)
    return money, percent


# ---------------------------------------------------------------------------
# Narrative token parsing (Stage 1)
# ---------------------------------------------------------------------------

# A percentage: digits followed by an optional space and '%'.
_PCT_TOKEN_RE = re.compile(r"(?<![\w.])(-?\d+(?:\.\d+)?)\s*%")

# A dollar amount, in one of three writable forms: $-prefixed, comma-grouped,
# or two-decimal. Deliberately does NOT match bare integers — that would treat
# dates ("2026-03-31"), ordinals ("3-period"), item counts ("4 items") and GL
# codes ("Account 4500") as money. The prompt requires money to be written in
# one of these three forms; see narrative_prompt.txt.
_MONEY_TOKEN_RE = re.compile(
    r"""(?<![\w.$])
        (?:
            \$\s?(?P<dollar>-?\d[\d,]*(?:\.\d+)?)
          | (?P<grouped>-?\d{1,3}(?:,\d{3})+(?:\.\d+)?)
          | (?P<decimal>-?\d+\.\d{2})
        )
        (?!\s*%)
        (?![\d.]*\d)
    """,
    re.VERBOSE,
)


def _to_float(token: str) -> float | None:
    try:
        return float(token.replace(",", "").replace("$", "").strip())
    except ValueError:
        return None


def parse_narrative_numbers(narrative: str) -> tuple[list[float], list[float]]:
    """Return (money_tokens, percent_tokens) written in *narrative*.

    Percentages are extracted first and blanked out so that "61.07%" is never
    also read as the money value 61.07.

    This is a strong filter, not a proof: a number spelled as words, or a bare
    integer dollar amount written against the prompt's formatting rule, is not
    detected. Stage 1 closes the demonstrated numbers_used=[] bypass; it does
    not guarantee narrative integrity.
    """
    percents: list[float] = []
    for match in _PCT_TOKEN_RE.finditer(narrative):
        value = _to_float(match.group(1))
        if value is not None:
            percents.append(value)

    blanked = _PCT_TOKEN_RE.sub(lambda m: " " * len(m.group(0)), narrative)

    money: list[float] = []
    for match in _MONEY_TOKEN_RE.finditer(blanked):
        raw = match.group("dollar") or match.group("grouped") or match.group("decimal")
        value = _to_float(raw)
        if value is not None:
            money.append(value)

    return money, percents


def _matches_any(value: float, refs: list[float], tolerance) -> bool:
    return any(abs(value - ref) <= tolerance(ref) for ref in refs)


def _excerpt(narrative: str, value: float, width: int = 120) -> str:
    """Bounded window around the first mention of *value*, for debugging."""
    for candidate in (f"{value:,.2f}", f"{value:.2f}", f"{value:g}"):
        idx = narrative.find(candidate)
        if idx != -1:
            start = max(0, idx - width // 2)
            return narrative[start : start + width].replace("\n", " ").strip()
    return narrative[:width].replace("\n", " ").strip()


def check_narrative_consistency(
    claude_json: dict,
    run_id: str | None = None,
) -> list[dict]:
    """Stage 1: every number in the narrative must appear in numbers_used.

    Returns a list of violation dicts. Logging is the caller-visible effect;
    whether a violation blocks the report is governed by
    ENFORCE_NARRATIVE_CONSISTENCY, never decided here.
    """
    narrative = claude_json.get("narrative") or ""
    if not narrative:
        return []

    declared = [float(n) for n in claude_json.get("numbers_used", []) or []]
    money_tokens, pct_tokens = parse_narrative_numbers(narrative)

    violations: list[dict] = []
    for value, unit, tolerance in (
        *[(v, "money", money_tolerance) for v in money_tokens],
        *[(v, "percent", pct_tolerance) for v in pct_tokens],
    ):
        if not _matches_any(value, declared, tolerance):
            violations.append(
                {
                    "value": value,
                    "unit": unit,
                    "excerpt": _excerpt(narrative, value),
                }
            )

    for violation in violations:
        logger.warning(
            "guardrail_narrative_unlisted_number",
            extra={
                "event": "guardrail_narrative_unlisted_number",
                "run_id": run_id,
                "trace_id": get_trace_id(),
                "value": violation["value"],
                "unit": violation["unit"],
                "narrative_excerpt": violation["excerpt"],
                "numbers_used_count": len(declared),
                "enforcing": ENFORCE_NARRATIVE_CONSISTENCY,
            },
        )

    return violations


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def verify_guardrail(
    claude_json: dict,
    pandas_summary: dict,
    reconciliation_values: list[float] | None = None,
    *,
    strict: bool = False,
    run_id: str | None = None,
) -> tuple[bool, str]:
    """Verify Claude's numbers against the pandas-derived reference data.

    Reference data = pandas_summary (consolidated totals) PLUS
    reconciliation_values (source-level amounts from individual files), so a
    multi-file run can safely mention a GL-level figure that differs from the
    consolidated total.

    strict=False (default) — legacy behaviour: one unit-blind reference pool,
        tolerance max(1% of ref, $1,000), zero references excluded. Retained
        for callers not yet migrated (quarterly.py, opus_upgrade.py).

    strict=True — money and percentage references are kept in separate pools
        with separate tolerances, so neither unit can widen the other:
          money   : max($0.01, 1e-6 x |ref|)
          percent : 0.05 percentage points
        Zero references are NOT excluded, so a legitimate $0.00 can match a
        real 0.0 and nothing else. Additionally runs the Stage 1 narrative
        consistency check (warn-only unless ENFORCE_NARRATIVE_CONSISTENCY).
    """
    if not strict:
        flat_values = flatten_summary(pandas_summary)
        if reconciliation_values:
            flat_values.extend(float(v) for v in reconciliation_values if v is not None)
        for num in claude_json["numbers_used"]:
            exists = any(
                abs(num - p_val) <= _tolerance_for(p_val)
                for p_val in flat_values
                if p_val != 0
            )
            if not exists:
                return False, f"Mismatch: {num} not found in pandas output"
        return True, "Success"

    money_refs, pct_refs = flatten_summary_by_unit(pandas_summary)
    if reconciliation_values:
        money_refs.extend(float(v) for v in reconciliation_values if v is not None)

    # Stage 1 — narrative vs numbers_used. Warn-only for this release.
    violations = check_narrative_consistency(claude_json, run_id=run_id)
    if violations and ENFORCE_NARRATIVE_CONSISTENCY:
        first = violations[0]
        return (
            False,
            f"Narrative mentions {first['value']} which is absent from numbers_used",
        )

    # Stage 2 — every declared number must match a pandas reference, in its own
    # unit. A value is valid if it matches a money reference at money tolerance
    # OR a percentage reference at percentage tolerance.
    for num in claude_json["numbers_used"]:
        if _matches_any(num, money_refs, money_tolerance):
            continue
        if _matches_any(num, pct_refs, pct_tolerance):
            continue
        return False, f"Mismatch: {num} not found in pandas output"

    return True, "Success"
