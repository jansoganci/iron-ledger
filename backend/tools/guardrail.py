from __future__ import annotations


def flatten_summary(d: dict) -> list[float]:
    """Recursively extract all numeric leaf values from a nested dict."""
    values: list[float] = []
    for v in d.values():
        if isinstance(v, dict):
            values.extend(flatten_summary(v))
        elif isinstance(v, (int, float)):
            values.append(float(v))
    return values


def _tolerance_for(pandas_val: float) -> float:
    """Return the allowed absolute deviation for a single pandas value.

    New rule (Track 4): max(1% of |pandas_val|, $1,000).
    This prevents small-dollar amounts from drifting on percentage-only
    tolerance while keeping large amounts anchored to a percentage floor.
    The old flat 2% allowed a $20 drift on a $1,000 value but $20,000
    drift on a $1M value — the dollar floor closes the small-value gap.
    """
    return max(0.01 * abs(pandas_val), 1_000.0)


def verify_guardrail(
    claude_json: dict,
    pandas_summary: dict,
    reconciliation_values: list[float] | None = None,
) -> tuple[bool, str]:
    """Verify every number in claude_json["numbers_used"] exists in the reference data.

    Reference data = pandas_summary (consolidated totals) PLUS reconciliation_values
    (source-level amounts from individual files). Multi-file runs pass reconciliation
    source amounts as extra context so Claude can safely mention GL-level figures like
    "GL shows $5,420" without failing the check just because the consolidated total
    is $10,920.

    Tolerance per value: max(1% of |ref_val|, $1,000).
    """
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
