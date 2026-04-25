from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from backend.domain.contracts import (
    DiscoveryPlan,
    DropReason,
    HierarchyHint,
    NormalizerDropReport,
)
from backend.tools.normalizer import _build_snippet, apply_plan
from backend.tools.pii_sanitizer import _scrub_value


def _plan(
    header_row_index: int = 0,
    skip_row_indices: list[int] | None = None,
    column_mapping: dict | None = None,
    hierarchy_hints: list[HierarchyHint] | None = None,
) -> DiscoveryPlan:
    return DiscoveryPlan(
        header_row_index=header_row_index,
        skip_row_indices=skip_row_indices or [],
        column_mapping=column_mapping or {"account": "account", "amount": "amount"},
        hierarchy_hints=hierarchy_hints or [],
        discovery_confidence=0.95,
        notes="",
    )


# ---------------------------------------------------------------------------
# Return shape
# ---------------------------------------------------------------------------


def test_apply_plan_returns_dataframe_and_report():
    raw = pd.DataFrame(
        [
            ["account", "amount"],
            ["Revenue", 1000],
            ["COGS", -500],
        ]
    )
    result = apply_plan(raw, _plan(), date(2026, 3, 1))

    assert isinstance(result, tuple)
    assert len(result) == 2
    df, report = result
    assert isinstance(df, pd.DataFrame)
    assert isinstance(report, NormalizerDropReport)


def test_clean_frame_produces_empty_drop_report():
    raw = pd.DataFrame(
        [
            ["account", "amount"],
            ["Revenue", 1000],
            ["COGS", -500],
        ]
    )
    _, report = apply_plan(raw, _plan(), date(2026, 3, 1))
    assert report.total_dropped == 0
    assert report.entries == []


# ---------------------------------------------------------------------------
# Drop-site population
# ---------------------------------------------------------------------------


def test_drop_report_tracks_amount_coerce_failures():
    raw = pd.DataFrame(
        [
            ["account", "amount"],
            ["Revenue", 1000],
            ["Broken line", "not-a-number"],
            ["COGS", -500],
        ]
    )
    df, report = apply_plan(raw, _plan(), date(2026, 3, 1))

    assert len(df) == 2
    assert report.total_dropped == 1
    assert len(report.entries) == 1
    entry = report.entries[0]
    assert entry.reason == "amount_coerce_failed"
    assert entry.account_snippet == "Broken line"
    # row_index is the RAW file index (pandas index 2 after reading header=None)
    assert entry.row_index == 2


def test_drop_report_tracks_subtotal_safety_net():
    raw = pd.DataFrame(
        [
            ["account", "amount"],
            ["Revenue", 1000],
            ["Total Revenue", 1000],  # subtotal Discovery missed
            ["COGS", -500],
            ["Gross Profit", 500],  # another subtotal
            ["Contribution %", 50],  # percent row
        ]
    )
    df, report = apply_plan(raw, _plan(), date(2026, 3, 1))

    assert len(df) == 2
    assert set(df["account"]) == {"Revenue", "COGS"}
    assert report.total_dropped == 3
    reasons = {e.reason for e in report.entries}
    assert reasons == {"subtotal_safety_net"}
    snippets = {e.account_snippet for e in report.entries}
    assert snippets == {"Total Revenue", "Gross Profit", "Contribution %"}


def test_drop_report_mixes_reasons_when_both_fire():
    raw = pd.DataFrame(
        [
            ["account", "amount"],
            ["Revenue", 1000],
            ["Garbage row", "NOPE"],  # amount_coerce_failed
            ["Total Revenue", 1000],  # subtotal_safety_net
            ["COGS", -500],
        ]
    )
    df, report = apply_plan(raw, _plan(), date(2026, 3, 1))
    assert len(df) == 2
    assert report.total_dropped == 2
    reasons = sorted(e.reason for e in report.entries)
    assert reasons == ["amount_coerce_failed", "subtotal_safety_net"]


# ---------------------------------------------------------------------------
# PII scrubbing in account_snippet
# ---------------------------------------------------------------------------


def test_account_snippet_scrubs_email_pii():
    # A subtotal-matching row whose account contains an email
    raw = pd.DataFrame(
        [
            ["account", "amount"],
            ["Revenue", 1000],
            ["Total contact alice@example.com", 500],
        ]
    )
    _, report = apply_plan(raw, _plan(), date(2026, 3, 1))
    assert report.total_dropped == 1
    snippet = report.entries[0].account_snippet
    assert "alice" not in snippet
    assert "@example" not in snippet
    assert "[REDACTED]" in snippet


def test_account_snippet_scrubs_ssn_and_cc_pii():
    raw = pd.DataFrame(
        [
            ["account", "amount"],
            ["Revenue", 1000],
            ["Total SSN 123-45-6789 bucket", 500],
            ["Gross card 4111-1111-1111-1111", 500],
        ]
    )
    _, report = apply_plan(raw, _plan(), date(2026, 3, 1))
    assert report.total_dropped == 2
    joined = " | ".join(e.account_snippet for e in report.entries)
    assert "123-45" not in joined
    assert "4111-1111" not in joined
    assert joined.count("[REDACTED]") == 2


def test_account_snippet_truncates_at_40_chars():
    long_name = "Total " + "x" * 100  # >100 chars after "Total "
    raw = pd.DataFrame(
        [
            ["account", "amount"],
            ["Revenue", 1000],
            [long_name, 500],
        ]
    )
    _, report = apply_plan(raw, _plan(), date(2026, 3, 1))
    assert len(report.entries[0].account_snippet) <= 40


# ---------------------------------------------------------------------------
# The load-bearing ordering invariant
# ---------------------------------------------------------------------------


def test_scrub_before_truncate_prevents_partial_email_leak():
    """If we truncated before scrubbing, 'alice@' would escape the email regex."""
    long_memo = "Total for Q1 services billed to alice@example.com inc"  # len > 40
    assert len(long_memo) > 40

    # Simulate the Normalizer's composed call: SCRUB FIRST, TRUNCATE SECOND.
    safe = _scrub_value(long_memo)[:40]
    assert "alice" not in safe
    assert "@example" not in safe
    assert "[REDAC" in safe  # truncated placeholder is what remains

    # Counter-example: truncate-first would leak the partial email.
    # Locked here so any future refactor that inverts the order fails loudly.
    naive = _scrub_value(long_memo[:40])
    assert "alice@" in naive  # demonstrates the leak we're preventing


def test_scrub_before_truncate_integrated_via_build_snippet():
    long_memo = "Total for Q1 services billed to alice@example.com inc"
    snippet = _build_snippet(long_memo)
    assert "alice" not in snippet
    assert len(snippet) <= 40


# ---------------------------------------------------------------------------
# NaN / None / pathological input defense
# ---------------------------------------------------------------------------


def test_build_snippet_handles_nan_and_none():
    assert _build_snippet(None) == ""
    assert _build_snippet(float("nan")) == ""
    assert _build_snippet("") == ""


def test_build_snippet_input_cap_protects_against_pathological_input():
    pathological = "x" * 10_000
    result = _build_snippet(pathological)
    assert len(result) <= 40  # truncation still applies


def test_amount_coerce_drop_with_nan_account_produces_empty_snippet():
    """If account is NaN at an amount_coerce_failed drop site, snippet=''."""
    raw = pd.DataFrame(
        [
            ["account", "amount"],
            [None, "not-numeric"],
            ["Revenue", 1000],
        ]
    )
    _, report = apply_plan(raw, _plan(), date(2026, 3, 1))
    # The NaN-account row failed coerce; snippet should be empty, not "nan"
    nan_drops = [e for e in report.entries if e.reason == "amount_coerce_failed"]
    if nan_drops:
        assert nan_drops[0].account_snippet == ""


# ---------------------------------------------------------------------------
# Ensure drop report is serializable for JSONB storage
# ---------------------------------------------------------------------------


def test_drop_report_model_dump_shape_matches_jsonb_contract():
    entry = DropReason(
        row_index=14,
        account_snippet="Gross Margin %",
        reason="subtotal_safety_net",
    )
    report = NormalizerDropReport(entries=[entry], total_dropped=1)
    dumped = report.model_dump()
    assert set(dumped.keys()) == {"entries", "total_dropped"}
    assert dumped["total_dropped"] == 1
    assert dumped["entries"] == [
        {
            "row_index": 14,
            "account_snippet": "Gross Margin %",
            "reason": "subtotal_safety_net",
        }
    ]
    # "drops" must NOT appear (the rename is locked)
    assert "drops" not in dumped


# ---------------------------------------------------------------------------
# Sanity: rows already in plan.skip_row_indices are NOT in the drop report
# ---------------------------------------------------------------------------


def test_plan_skip_rows_not_in_drop_report():
    """Discovery's intentional skips are separate from Normalizer's drops."""
    raw = pd.DataFrame(
        [
            ["account", "amount"],
            ["METADATA_ROW", None],  # row index 1 — Discovery skips
            ["Revenue", 1000],
            ["COGS", -500],
        ]
    )
    plan = _plan(skip_row_indices=[1])
    _, report = apply_plan(raw, plan, date(2026, 3, 1))
    assert report.total_dropped == 0
    # The metadata row's index (1) is never in report.entries
    assert all(e.row_index != 1 for e in report.entries)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
