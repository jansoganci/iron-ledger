"""Unit tests for AccountMapper.build_draft() — no real API calls."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from backend.agents.account_mapper import AccountMapper
from backend.domain.contracts import (
    AccountMappingDecision,
    AccountMappingResponse,
    DEFAULT_GL_CATEGORIES,
)


def _make_mapper(
    haiku_response: dict[str, AccountMappingDecision]
) -> tuple[AccountMapper, MagicMock]:
    """Return (mapper, mock_llm) where mock returns the given response."""
    mock_llm = MagicMock()
    mock_llm.call.return_value = AccountMappingResponse(mappings=haiku_response)
    return AccountMapper(llm_client=mock_llm), mock_llm


GL_POOL = [
    "Equipment COGS",
    "Salaries & Wages",
    "Bonuses",
    "Subcontractor Costs",
    "Software Subscriptions",
]


# ---------------------------------------------------------------------------
# Test 1: Single Haiku call with all unique values
# ---------------------------------------------------------------------------


def test_single_haiku_call_for_all_uniques() -> None:
    mapper, mock_llm = _make_mapper(
        {
            "AlarmTech Industries": AccountMappingDecision(
                gl_account="Equipment COGS", confident=True
            ),
            "T. Rivera": AccountMappingDecision(
                gl_account="Salaries & Wages", confident=True
            ),
        }
    )

    mapping_dict, draft = mapper.build_draft(
        unique_values=["AlarmTech Industries", "T. Rivera"],
        file_type="supplier_invoices",
        source_file="vendor.xlsx",
        gl_pool=GL_POOL,
    )

    mock_llm.call.assert_called_once()
    assert mapping_dict["AlarmTech Industries"] == "Equipment COGS"
    assert mapping_dict["T. Rivera"] == "Salaries & Wages"
    assert len(draft.items) == 2
    assert all(item.confident for item in draft.items)


# ---------------------------------------------------------------------------
# Test 2: Hallucinated gl_account not in pool → demoted to confident=False
# ---------------------------------------------------------------------------


def test_hallucinated_gl_account_demoted() -> None:
    mapper, _ = _make_mapper(
        {
            "SomeVendor": AccountMappingDecision(
                gl_account="Made Up Account", confident=True
            ),
        }
    )

    mapping_dict, draft = mapper.build_draft(
        unique_values=["SomeVendor"],
        file_type="supplier_invoices",
        source_file="vendor.xlsx",
        gl_pool=GL_POOL,
    )

    assert mapping_dict["SomeVendor"] is None
    assert draft.items[0].confident is False
    assert draft.items[0].suggested_gl_account is None


# ---------------------------------------------------------------------------
# Test 3: Empty unique_values → empty draft, no Haiku call
# ---------------------------------------------------------------------------


def test_empty_unique_values_no_llm_call() -> None:
    mock_llm = MagicMock()
    mapper = AccountMapper(llm_client=mock_llm)

    mapping_dict, draft = mapper.build_draft(
        unique_values=[],
        file_type="payroll",
        source_file="payroll.xlsx",
        gl_pool=GL_POOL,
    )

    mock_llm.call.assert_not_called()
    assert mapping_dict == {}
    assert draft.items == []


# ---------------------------------------------------------------------------
# Test 4: GL pool empty → falls back to DEFAULT_GL_CATEGORIES
# ---------------------------------------------------------------------------


def test_empty_gl_pool_falls_back_to_defaults() -> None:
    mapper, mock_llm = _make_mapper(
        {
            "T. Rivera": AccountMappingDecision(gl_account=None, confident=False),
        }
    )

    _, draft = mapper.build_draft(
        unique_values=["T. Rivera"],
        file_type="payroll",
        source_file="payroll.xlsx",
        gl_pool=[],  # empty → should use DEFAULT_GL_CATEGORIES
    )

    call_args = mock_llm.call.call_args
    context_passed = call_args[0][2]  # positional arg 3 = context dict
    assert context_passed["gl_accounts"] == DEFAULT_GL_CATEGORIES
    assert draft.gl_account_pool == DEFAULT_GL_CATEGORIES


# ---------------------------------------------------------------------------
# Test 5: Haiku returns null gl_account → confident=False in draft
# ---------------------------------------------------------------------------


def test_null_gl_account_sets_confident_false() -> None:
    mapper, _ = _make_mapper(
        {
            "CableMax Corp": AccountMappingDecision(gl_account=None, confident=False),
        }
    )

    mapping_dict, draft = mapper.build_draft(
        unique_values=["CableMax Corp"],
        file_type="supplier_invoices",
        source_file="vendor.xlsx",
        gl_pool=GL_POOL,
    )

    assert mapping_dict["CableMax Corp"] is None
    assert draft.items[0].confident is False
    assert draft.items[0].suggested_gl_account is None


# ---------------------------------------------------------------------------
# Test 6: Value missing from Haiku response → treated as no match
# ---------------------------------------------------------------------------


def test_value_missing_from_haiku_response() -> None:
    # Haiku returns only one of two values
    mapper, _ = _make_mapper(
        {
            "AlarmTech": AccountMappingDecision(
                gl_account="Equipment COGS", confident=True
            ),
            # "MissingVendor" not in response
        }
    )

    mapping_dict, draft = mapper.build_draft(
        unique_values=["AlarmTech", "MissingVendor"],
        file_type="supplier_invoices",
        source_file="vendor.xlsx",
        gl_pool=GL_POOL,
    )

    assert mapping_dict["AlarmTech"] == "Equipment COGS"
    assert mapping_dict["MissingVendor"] is None
    missing_item = next(i for i in draft.items if i.source_pattern == "MissingVendor")
    assert missing_item.confident is False
