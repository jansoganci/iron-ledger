"""Unit tests for AccountMapper orchestrator integration.

All Supabase / LLM / Storage calls are mocked — no real I/O.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from backend.agents.orchestrator import (
    _detect_file_type,
    run_multi_file_parser_with_mapping,
    apply_mapping_and_consolidate,
)
from backend.domain.run_state_machine import RunStatus


# ---------------------------------------------------------------------------
# _detect_file_type helper
# ---------------------------------------------------------------------------


def test_detect_file_type_gl() -> None:
    assert _detect_file_type("sentinel_gl_mar_2026.xlsx") == "general_ledger"
    assert _detect_file_type("quickbooks_export.xlsx") == "general_ledger"


def test_detect_file_type_payroll() -> None:
    assert _detect_file_type("helix_payroll_mar_2026.xlsx") == "payroll"
    assert _detect_file_type("gusto_salaries.csv") == "payroll"


def test_detect_file_type_supplier() -> None:
    assert _detect_file_type("vendor_invoices_march.xlsx") == "supplier_invoices"
    assert _detect_file_type("ap_bills.csv") == "supplier_invoices"


def test_detect_file_type_contracts() -> None:
    assert _detect_file_type("sentinel_contracts_mar_2026.xlsx") == "contracts"


def test_detect_file_type_fallback() -> None:
    assert _detect_file_type("mystery_file.xlsx") == "supplier_invoices"


# ---------------------------------------------------------------------------
# Shared mock factories
# ---------------------------------------------------------------------------


def _mock_preview_rows(account_names: list[str]) -> list[dict]:
    return [{"account": a, "amount": 1000.0, "category": "OPEX"} for a in account_names]


def _stub_parse_file_silently(preview_rows, source_column="Amount", raw_df=None):
    """Return a mock parser whose parse_file_silently returns fixed data."""
    if raw_df is None:
        raw_df = pd.DataFrame(
            {
                "account": [r["account"] for r in preview_rows],
                "amount": [r["amount"] for r in preview_rows],
                "date": pd.Timestamp("2026-03-01"),
            }
        )
    parser = MagicMock()
    parser.parse_file_silently.return_value = (preview_rows, source_column, raw_df)
    return parser


def _stub_runs_repo(status=RunStatus.PENDING.value, parse_preview=None):
    repo = MagicMock()
    repo.get_by_id.return_value = {
        "status": status,
        "parse_preview": parse_preview or {},
    }
    return repo


# ---------------------------------------------------------------------------
# Test: pure GL upload → no AWAITING_MAPPING_CONFIRMATION
# ---------------------------------------------------------------------------


@patch("backend.agents.orchestrator.get_llm_client")
@patch("backend.agents.orchestrator.get_file_storage")
@patch("backend.agents.orchestrator.get_accounts_repo")
@patch("backend.agents.orchestrator.get_runs_repo")
@patch("backend.agents.orchestrator.ParserAgent")
@patch("backend.agents.account_mapper.AccountMapper")
def test_pure_gl_upload_goes_to_awaiting_confirmation(
    mock_mapper_cls,
    mock_parser_cls,
    mock_get_runs,
    mock_get_accounts,
    mock_get_storage,
    mock_get_llm,
):
    """When all files are GL, mapping step is skipped entirely."""
    gl_preview = _mock_preview_rows(["Service Revenue", "Equipment COGS"])
    parser = _stub_parse_file_silently(gl_preview)
    mock_parser_cls.return_value = parser

    runs_repo = _stub_runs_repo()
    mock_get_runs.return_value = runs_repo

    accounts_repo = MagicMock()
    accounts_repo.list_for_company.return_value = {"Service Revenue": "REVENUE"}
    mock_get_accounts.return_value = accounts_repo

    mock_mapper_cls.return_value = MagicMock()

    with patch("backend.agents.orchestrator.consolidate") as mock_consolidate, patch(
        "backend.tools.hint_computer.compute_hints",
        side_effect=lambda **kw: kw["item"].hints,
    ):
        mock_consolidate.return_value = (
            pd.DataFrame(
                [
                    {
                        "account": "Service Revenue",
                        "amount": 3540.0,
                        "category": "REVENUE",
                        "source_breakdown": [],
                    }
                ]
            ),
            [],
        )
        run_multi_file_parser_with_mapping(
            run_id="run-1",
            storage_keys=["user/2026-03-01/sentinel_gl_mar_2026.xlsx"],
            company_id="co-1",
            period=__import__("datetime").date(2026, 3, 1),
        )

    # Must NOT have called update_status with AWAITING_MAPPING_CONFIRMATION
    statuses_set = [
        call.args[1] if call.args else call.kwargs.get("status")
        for call in runs_repo.update_status.call_args_list
    ]
    assert RunStatus.AWAITING_MAPPING_CONFIRMATION not in statuses_set
    # Must have called set_parse_preview (consolidation ran)
    runs_repo.set_parse_preview.assert_called_once()


# ---------------------------------------------------------------------------
# Test: GL + payroll → passes through AWAITING_MAPPING_CONFIRMATION
# ---------------------------------------------------------------------------


@patch("backend.agents.orchestrator.get_llm_client")
@patch("backend.agents.orchestrator.get_file_storage")
@patch("backend.agents.orchestrator.get_accounts_repo")
@patch("backend.agents.orchestrator.get_runs_repo")
@patch("backend.agents.orchestrator.ParserAgent")
@patch("backend.agents.account_mapper.AccountMapper")
def test_gl_plus_payroll_reaches_awaiting_mapping_confirmation(
    mock_mapper_cls,
    mock_parser_cls,
    mock_get_runs,
    mock_get_accounts,
    mock_get_storage,
    mock_get_llm,
):
    """GL + non-GL upload → stops at AWAITING_MAPPING_CONFIRMATION."""
    from backend.domain.contracts import (
        AccountMappingDecision,
        MappingDraft,
        MappingDraftItem,
    )

    gl_preview = _mock_preview_rows(["Salaries & Wages", "Bonuses"])
    payroll_preview = _mock_preview_rows(["Alice Johnson", "Bob Smith"])

    parser = MagicMock()
    parser.parse_file_silently.side_effect = [
        (gl_preview, "Amount", pd.DataFrame()),  # GL first
        (payroll_preview, "Gross Pay", pd.DataFrame()),  # payroll second
    ]
    mock_parser_cls.return_value = parser

    runs_repo = _stub_runs_repo()
    mock_get_runs.return_value = runs_repo

    accounts_repo = MagicMock()
    accounts_repo.list_for_company.return_value = {
        "Salaries & Wages": "OPEX",
        "Bonuses": "OPEX",
    }
    mock_get_accounts.return_value = accounts_repo

    draft_items = [
        MappingDraftItem(
            source_pattern="Alice Johnson",
            source_file="payroll.xlsx",
            file_type="payroll",
            suggested_gl_account="Salaries & Wages",
            confident=True,
        ),
        MappingDraftItem(
            source_pattern="Bob Smith",
            source_file="payroll.xlsx",
            file_type="payroll",
            suggested_gl_account="Salaries & Wages",
            confident=True,
        ),
    ]
    mapper = MagicMock()
    mapper.build_draft.return_value = (
        {"Alice Johnson": "Salaries & Wages", "Bob Smith": "Salaries & Wages"},
        MappingDraft(
            items=draft_items, gl_account_pool=["Salaries & Wages", "Bonuses"]
        ),
    )
    mock_mapper_cls.return_value = mapper

    run_multi_file_parser_with_mapping(
        run_id="run-2",
        storage_keys=[
            "user/2026-03-01/gl.xlsx",
            "user/2026-03-01/payroll.xlsx",
        ],
        company_id="co-1",
        period=__import__("datetime").date(2026, 3, 1),
    )

    # Must have stored mapping_draft
    runs_repo.set_parse_preview.assert_called_once()
    stored_preview = runs_repo.set_parse_preview.call_args[0][1]
    assert "mapping_draft" in stored_preview
    assert "file_keys" in stored_preview

    # Must have transitioned to AWAITING_MAPPING_CONFIRMATION
    statuses_set = [
        call.args[1] if call.args else call.kwargs.get("status")
        for call in runs_repo.update_status.call_args_list
    ]
    assert RunStatus.AWAITING_MAPPING_CONFIRMATION in statuses_set


# ---------------------------------------------------------------------------
# Test: GL files bypass mapper (no account_name_map passed)
# ---------------------------------------------------------------------------


@patch("backend.agents.orchestrator.get_llm_client")
@patch("backend.agents.orchestrator.get_file_storage")
@patch("backend.agents.orchestrator.get_accounts_repo")
@patch("backend.agents.orchestrator.get_runs_repo")
@patch("backend.agents.orchestrator.ParserAgent")
@patch("backend.agents.account_mapper.AccountMapper")
def test_gl_files_bypass_mapper(
    mock_mapper_cls,
    mock_parser_cls,
    mock_get_runs,
    mock_get_accounts,
    mock_get_storage,
    mock_get_llm,
):
    """parse_file_silently is called without account_name_map for GL files."""
    from backend.domain.contracts import MappingDraft, MappingDraftItem

    gl_preview = _mock_preview_rows(["Service Revenue"])
    payroll_preview = _mock_preview_rows(["T. Rivera"])

    parser = MagicMock()
    parser.parse_file_silently.side_effect = [
        (gl_preview, "Amount", pd.DataFrame()),
        (payroll_preview, "Gross Pay", pd.DataFrame()),
    ]
    mock_parser_cls.return_value = parser

    runs_repo = _stub_runs_repo()
    mock_get_runs.return_value = runs_repo

    accounts_repo = MagicMock()
    accounts_repo.list_for_company.return_value = {"Service Revenue": "REVENUE"}
    mock_get_accounts.return_value = accounts_repo

    draft_items = [
        MappingDraftItem(
            source_pattern="T. Rivera",
            source_file="payroll.xlsx",
            file_type="payroll",
            suggested_gl_account="Service Revenue",
            confident=True,
        )
    ]
    mapper = MagicMock()
    mapper.build_draft.return_value = (
        {"T. Rivera": "Service Revenue"},
        MappingDraft(items=draft_items, gl_account_pool=["Service Revenue"]),
    )
    mock_mapper_cls.return_value = mapper

    run_multi_file_parser_with_mapping(
        run_id="run-3",
        storage_keys=["user/2026-03-01/gl.xlsx", "user/2026-03-01/payroll.xlsx"],
        company_id="co-1",
        period=__import__("datetime").date(2026, 3, 1),
    )

    calls = parser.parse_file_silently.call_args_list
    # GL call (index 0): account_name_map should be None or absent
    gl_call_kwargs = calls[0].kwargs
    assert gl_call_kwargs.get("account_name_map") is None
    # Non-GL call (index 1): account_name_map may be set later in Phase B; Phase A also None
    payroll_call_kwargs = calls[1].kwargs
    assert payroll_call_kwargs.get("account_name_map") is None


# ---------------------------------------------------------------------------
# Test: Phase B applies user decisions to non-GL files
# ---------------------------------------------------------------------------


@patch("backend.agents.orchestrator.get_llm_client")
@patch("backend.agents.orchestrator.get_file_storage")
@patch("backend.agents.orchestrator.get_accounts_repo")
@patch("backend.agents.orchestrator.get_runs_repo")
@patch("backend.agents.orchestrator.ParserAgent")
def test_phase_b_applies_user_decisions_to_non_gl(
    mock_parser_cls, mock_get_runs, mock_get_accounts, mock_get_storage, mock_get_llm
):
    """apply_mapping_and_consolidate passes user_decisions as account_name_map for non-GL files."""
    gl_preview = _mock_preview_rows(["Salaries & Wages"])
    payroll_preview = _mock_preview_rows(["Salaries & Wages"])  # after mapping

    parser = MagicMock()
    parser.parse_file_silently.side_effect = [
        (gl_preview, "Amount", pd.DataFrame()),
        (payroll_preview, "Gross Pay", pd.DataFrame()),
    ]
    mock_parser_cls.return_value = parser

    file_keys = {
        "gl.xlsx": "user/2026-03-01/gl.xlsx",
        "payroll.xlsx": "user/2026-03-01/payroll.xlsx",
    }
    runs_repo = _stub_runs_repo(
        status=RunStatus.APPLYING_MAPPING.value,
        parse_preview={
            "file_keys": file_keys,
            "mapping_draft": {},
            "is_multi_file": True,
        },
    )
    mock_get_runs.return_value = runs_repo

    accounts_repo = MagicMock()
    mock_get_accounts.return_value = accounts_repo

    user_decisions = {
        "Alice Johnson": "Salaries & Wages",
        "Bob Smith": "Salaries & Wages",
    }

    with patch("backend.agents.orchestrator.consolidate") as mock_consolidate, patch(
        "backend.tools.hint_computer.compute_hints",
        side_effect=lambda **kw: kw["item"].hints,
    ):
        mock_consolidate.return_value = (
            pd.DataFrame(
                [
                    {
                        "account": "Salaries & Wages",
                        "amount": 142800.0,
                        "category": "OPEX",
                        "source_breakdown": [],
                    }
                ]
            ),
            [],
        )
        apply_mapping_and_consolidate(
            run_id="run-4",
            company_id="co-1",
            period=__import__("datetime").date(2026, 3, 1),
            user_decisions=user_decisions,
        )

    calls = parser.parse_file_silently.call_args_list
    # GL file → no account_name_map
    gl_call = next(c for c in calls if "gl.xlsx" in str(c))
    assert gl_call.kwargs.get("account_name_map") is None
    # Payroll file → user_decisions passed as account_name_map
    payroll_call = next(c for c in calls if "payroll.xlsx" in str(c))
    assert payroll_call.kwargs.get("account_name_map") == user_decisions

    # Must have written final parse_preview (no mapping_draft)
    runs_repo.set_parse_preview.assert_called_once()
    stored = runs_repo.set_parse_preview.call_args[0][1]
    assert "mapping_draft" not in stored
    assert "reconciliations" in stored
