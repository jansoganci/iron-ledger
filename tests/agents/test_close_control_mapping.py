"""Production parser/mapping wiring with local fixtures and mocked external I/O."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from backend import messages
from backend.agents.parser import ParserAgent
from backend.domain.contracts import DiscoveryPlan
from backend.domain.errors import MappingAmbiguous
from backend.tools.file_reader import read_file
from backend.tools.mapping_grain import FILE_TOTAL_PATTERN

PERIOD = date(2026, 3, 1)


def _parser(raw: pd.DataFrame, columns: dict[str, str | None]):
    discovery = MagicMock()
    discovery.discover.return_value = DiscoveryPlan(
        header_row_index=0,
        skip_row_indices=[],
        column_mapping=columns,
        hierarchy_hints=[],
        discovery_confidence=1,
    )
    parser = ParserAgent(MagicMock(), MagicMock(), MagicMock(), MagicMock(), discovery)
    parser._read_full = MagicMock(return_value=raw)
    parser._read_sample = MagicMock(
        return_value=[
            {
                "row_index": 0,
                "values": ["review@example.com", "123-45-6789"],
                "is_bold": False,
                "indent_level": 0,
                "is_merged": False,
            }
        ]
    )
    return parser, discovery


def _parse(parser, **kwargs):
    return parser.parse_file_silently(
        storage_key="mock/contracts.xlsx",
        company_id="co-1",
        period=PERIOD,
        run_id="run-1",
        file_type="contracts",
        **kwargs,
    )


def _categories(*args):
    accounts = args[2]["account"].unique()
    return {a: {"category": "REVENUE"} for a in accounts}, []


def test_redhawk_roster_is_aggregate_draft_then_confirmed_file_total():
    fixture = (
        Path(__file__).resolve().parents[2]
        / "docs/demo_data/redhawk/redhawk_contracts_mar_2026.xlsx"
    )
    parser, discovery = _parser(
        read_file(fixture),
        {
            "Customer ID": "account",
            "Monthly Fee": "amount",
        },
    )
    with patch(
        "backend.agents.parser.map_accounts", side_effect=_categories
    ) as mapping:
        rows, scope, detailed, sidecar = _parse(parser)
        mapping.assert_not_called()  # Customer identifiers never become GL suggestions.
        assert rows == [
            {"account": FILE_TOTAL_PATTERN, "amount": 3825.0, "category": "REVENUE"}
        ]
        assert scope == "Monthly Fee"
        assert detailed.attrs["file_total_candidate"] is True
        assert sidecar is not None
        sent_sample = repr(discovery.discover.call_args.args[1])
        assert "review@example.com" not in sent_sample
        assert "123-45-6789" not in sent_sample

        rows, _, detailed, _ = _parse(parser, file_total_account="Service Revenue")
        assert rows == [
            {"account": "Service Revenue", "amount": 3825.0, "category": "REVENUE"}
        ]
        assert set(detailed["account"]) == {"Service Revenue"}
        assert mapping.call_count == 1


def test_contracts_with_real_accounts_preserve_multiple_targets():
    raw = pd.DataFrame(
        [
            ["Customer", "Account", "Amount"],
            ["Customer A", "Service Revenue", 1000],
            ["Customer B", "Installation Revenue", 2000],
        ]
    )
    # Even when discovery picks the customer column, the real account wins.
    parser, _ = _parser(raw, {"Customer": "account", "Amount": "amount"})
    with patch("backend.agents.parser.map_accounts", side_effect=_categories):
        rows, _, detailed, _ = _parse(parser)
    assert {r["account"]: r["amount"] for r in rows} == {
        "Service Revenue": 1000,
        "Installation Revenue": 2000,
    }
    assert detailed.attrs["file_total_candidate"] is False
    with pytest.raises(MappingAmbiguous, match="contracts export"):
        _parse(parser, file_total_account="Service Revenue")


def test_ambiguous_contract_schema_stops_before_account_mapping():
    raw = pd.DataFrame([["Customer", "Amount"], ["Customer A", 1000]])
    parser, _ = _parser(raw, {"Customer": "account", "Amount": "amount"})
    with patch("backend.agents.parser.map_accounts") as mapping:
        with pytest.raises(MappingAmbiguous) as exc:
            _parse(parser)
        assert str(exc.value) == messages.CONTROL_CONTRACT_SCHEMA
        mapping.assert_not_called()


@pytest.mark.parametrize("candidate", [True, False])
def test_orchestrator_uses_parser_schema_evidence_for_file_total(candidate):
    from backend.agents.orchestrator import run_multi_file_parser_with_mapping
    from backend.domain.contracts import MappingDraft, MappingDraftItem

    with patch("backend.agents.orchestrator.ParserAgent") as parser_cls, patch(
        "backend.agents.orchestrator.AccountMapper"
    ) as mapper_cls, patch("backend.agents.orchestrator.get_runs_repo") as runs, patch(
        "backend.agents.orchestrator.get_accounts_repo"
    ) as accounts, patch(
        "backend.agents.orchestrator.get_source_mappings_repo"
    ) as memory, patch(
        "backend.agents.orchestrator.get_file_storage"
    ), patch(
        "backend.agents.orchestrator.get_llm_client"
    ):
        accounts.return_value.list_for_company.return_value = {
            "Service Revenue": {},
            "Installation Revenue": {},
        }
        memory.return_value.list_for_company.return_value = []
        detailed = pd.DataFrame()
        detailed.attrs["file_total_candidate"] = candidate
        source_rows = [
            {
                "account": FILE_TOTAL_PATTERN if candidate else "Installation Revenue",
                "amount": 1000,
                "category": "REVENUE",
            }
        ]
        parser_cls.return_value.parse_file_silently.side_effect = [
            (
                [{"account": "Service Revenue", "amount": 1000, "category": "REVENUE"}],
                "Amount",
                pd.DataFrame(),
                None,
            ),
            (source_rows, "Monthly Fee", detailed, None),
        ]
        mapper_cls.return_value.build_draft.return_value = (
            {},
            MappingDraft(
                items=[
                    MappingDraftItem(
                        source_pattern="Installation Revenue",
                        source_file="contracts.xlsx",
                        file_type="contracts",
                        suggested_gl_account="Installation Revenue",
                        confident=True,
                    )
                ],
                gl_account_pool=["Service Revenue", "Installation Revenue"],
            ),
        )
        run_multi_file_parser_with_mapping(
            run_id="run-1",
            storage_keys=["mock/gl.xlsx", "mock/contracts.xlsx"],
            company_id="co-1",
            period=PERIOD,
        )
        draft = runs.return_value.set_parse_preview.call_args.args[1]["mapping_draft"]
        assert draft["items"][0]["mapping_mode"] == (
            "file_total" if candidate else "row"
        )
        if candidate:
            mapper_cls.return_value.build_draft.assert_not_called()
