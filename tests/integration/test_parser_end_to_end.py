"""End-to-end integration tests for the Discovery & Mapping Layer.

Each test drives ParserAgent.run() against a fixture, mocking only the
I/O seams (FileStorage, LLMClient, and the Supabase repos). The Normalizer,
Validator, and state machine run for real.

Cross-reference: docs/sprint/discovery-layer-plan.md §Step 11.
"""

from __future__ import annotations

import json
from datetime import date
from unittest.mock import MagicMock

import pytest

from backend.agents.discovery import DiscoveryAgent
from backend.agents.parser import ParserAgent
from backend.domain.contracts import (
    DiscoveryPlan,
    HierarchyHint,
    MappingOutput,
    MappingResponse,
)
from backend.domain.errors import DiscoveryFailed, DiscoveryLowConfidence
from backend.tools.file_reader import read_raw_cells


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------


def _make_mocks(xlsx_bytes: bytes):
    """Standard mock setup: storage returns bytes, runs starts at pending."""
    storage = MagicMock()
    storage.download.return_value = xlsx_bytes
    llm = MagicMock()
    runs = MagicMock()
    runs.get_by_id.return_value = {"status": "pending", "company_id": "c1"}
    accounts = MagicMock()
    accounts.list_for_company.return_value = {}
    return storage, llm, runs, accounts


def _canned_mapping(prompt=None, model=None, context=None, schema=None):
    """Fake LLM for mapping calls: every unknown account → OTHER at 0.5."""
    assert prompt == "mapping_prompt.txt"
    unknowns = (context or {}).get("accounts", [])
    return MappingResponse(
        mappings=[
            MappingOutput(column=a["name"], category="OTHER", confidence=0.5)
            for a in unknowns
        ]
    )


def _make_fake_discovery(plan: DiscoveryPlan) -> MagicMock:
    agent = MagicMock(spec=DiscoveryAgent)
    agent.discover.return_value = plan
    return agent


def _status_walk(runs_mock) -> list[str]:
    return [c.args[1].value for c in runs_mock.update_status.call_args_list]


# ---------------------------------------------------------------------------
# 1. QBO clean happy path
# ---------------------------------------------------------------------------


def test_qbo_clean_happy_path(drone_qbo_clean_bytes, tmp_path):
    """Real DRONE fixture → full pipeline → awaiting_confirmation with preview."""
    # Derive a plan from the actual file so the test isn't coupled to a
    # hand-guessed structure — any future DRONE reshape only breaks the
    # fixture, not the test.
    tmp = tmp_path / "drone.xlsx"
    tmp.write_bytes(drone_qbo_clean_bytes)
    rows = read_raw_cells(tmp)
    header_idx = next(
        i
        for i, r in enumerate(rows)
        if r["is_bold"] and sum(1 for v in r["values"] if v is not None) >= 3
    )
    # Skip metadata (0..header-1), banner rows (bold + single value), and
    # subtotal rows (starts with Total/Gross/Net or contains %).
    skip = list(range(header_idx))
    hints = []
    current_parent = None
    for r in rows:
        if r["row_index"] == header_idx:
            continue
        values = [v for v in r["values"] if v is not None]
        first_account = (
            str(r["values"][1]) if len(r["values"]) > 1 and r["values"][1] else ""
        )
        if r["is_bold"] and len(values) == 1:
            skip.append(r["row_index"])
            current_parent = str(values[0])
        elif r["is_bold"] and (
            first_account.startswith(("Total", "Gross", "Net")) or "%" in first_account
        ):
            skip.append(r["row_index"])
        elif (
            not r["is_bold"]
            and r["indent_level"] > 0
            and current_parent
            and r["row_index"] > header_idx
        ):
            hints.append(
                HierarchyHint(row_index=r["row_index"], parent_category=current_parent)
            )

    plan = DiscoveryPlan(
        header_row_index=header_idx,
        skip_row_indices=sorted(set(skip)),
        column_mapping={
            "Date": "date",
            "Account": "account",
            "Category": None,
            "Description": "description",
            "Amount": "amount",
            "Debit": None,
            "Credit": None,
        },
        hierarchy_hints=hints,
        discovery_confidence=0.92,
        notes="derived-from-fixture",
    )

    storage, llm, runs, accounts = _mock_with(drone_qbo_clean_bytes)
    llm.call.side_effect = _canned_mapping
    parser = ParserAgent(
        file_storage=storage,
        llm_client=llm,
        accounts_repo=accounts,
        runs_repo=runs,
        discovery_agent=_make_fake_discovery(plan),
    )
    output = parser.run("r-qbo", "c1", "drone_mar.xlsx", date(2026, 3, 1))

    assert _status_walk(runs) == [
        "parsing",
        "discovering",
        "mapping",
        "awaiting_confirmation",
    ]
    assert output.rows_parsed > 0
    # High-confidence auto-approve persisted
    args = runs.set_discovery_plan.call_args
    mode = args.args[2] if len(args.args) > 2 else args.kwargs.get("approval_mode")
    assert mode == "auto"
    # parse_preview.drops present (possibly non-empty — safety net may fire)
    preview = runs.set_parse_preview.call_args.args[1]
    assert "drops" in preview
    assert "entries" in preview["drops"]


def _mock_with(xlsx_bytes):
    # Alias so per-test setup reads tighter — doesn't shadow _make_mocks, just uses it.
    return _make_mocks(xlsx_bytes)


# ---------------------------------------------------------------------------
# 2. Flat CSV
# ---------------------------------------------------------------------------


def test_flat_csv_trivial_plan(flat_csv_bytes):
    plan = DiscoveryPlan(
        header_row_index=0,
        skip_row_indices=[],
        column_mapping={"Account": "account", "Amount": "amount", "Date": "date"},
        hierarchy_hints=[],
        discovery_confidence=0.98,
        notes="flat",
    )
    storage, llm, runs, accounts = _make_mocks(flat_csv_bytes)
    llm.call.side_effect = _canned_mapping
    parser = ParserAgent(
        file_storage=storage,
        llm_client=llm,
        accounts_repo=accounts,
        runs_repo=runs,
        discovery_agent=_make_fake_discovery(plan),
    )
    output = parser.run("r-csv", "c1", "flat.csv", date(2026, 3, 1))

    assert _status_walk(runs) == [
        "parsing",
        "discovering",
        "mapping",
        "awaiting_confirmation",
    ]
    assert output.rows_parsed == 3  # Revenue, COGS, OpEx
    preview = runs.set_parse_preview.call_args.args[1]
    assert preview["drops"]["total_dropped"] == 0


# ---------------------------------------------------------------------------
# 3. No hierarchy
# ---------------------------------------------------------------------------


def test_no_hierarchy_file_still_maps_categories(no_hierarchy_xlsx_bytes):
    plan = DiscoveryPlan(
        header_row_index=0,
        skip_row_indices=[],
        column_mapping={"Account": "account", "Amount": "amount"},
        hierarchy_hints=[],  # deliberately empty
        discovery_confidence=0.95,
        notes="no-hier",
    )
    storage, llm, runs, accounts = _make_mocks(no_hierarchy_xlsx_bytes)
    llm.call.side_effect = _canned_mapping
    parser = ParserAgent(
        file_storage=storage,
        llm_client=llm,
        accounts_repo=accounts,
        runs_repo=runs,
        discovery_agent=_make_fake_discovery(plan),
    )
    output = parser.run("r-nh", "c1", "no_hier.xlsx", date(2026, 3, 1))

    assert output.rows_parsed == 4  # 4 line items
    # Mapping LLM still called — accounts list is built even without hierarchy
    mapping_call = llm.call.call_args
    ctx = mapping_call.kwargs.get("context") or mapping_call.args[2]
    assert len(ctx["accounts"]) == 4
    # parent_category is None for every account (none supplied by plan)
    assert all(a["parent_category"] is None for a in ctx["accounts"])


# ---------------------------------------------------------------------------
# 4. PII never reaches Claude (end-to-end audit)
# ---------------------------------------------------------------------------


def test_pii_never_reaches_claude(pii_laced_xlsx_bytes):
    """The critical R-006 regression guard: record every LLM invocation,
    assert no PII value survived into any payload."""
    recorded: list[dict] = []

    def capturing_llm(prompt=None, model=None, context=None, schema=None):
        recorded.append({"prompt": prompt, "context": context})
        if prompt == "discovery_prompt.txt":
            # Return a trivial high-confidence plan — we don't actually need
            # to exercise Discovery logic for this test, only confirm the
            # sanitize_sample step fired upstream.
            return DiscoveryPlan(
                header_row_index=0,
                skip_row_indices=[],
                column_mapping={
                    "Date": "date",
                    "Account": "account",
                    "Amount": "amount",
                    "Memo": "description",
                },
                hierarchy_hints=[],
                discovery_confidence=0.90,
                notes="",
            )
        if prompt == "mapping_prompt.txt":
            return _canned_mapping(
                prompt=prompt, model=model, context=context, schema=schema
            )
        raise AssertionError(f"unexpected prompt {prompt!r}")

    storage, llm, runs, accounts = _make_mocks(pii_laced_xlsx_bytes)
    llm.call.side_effect = capturing_llm
    # Use the REAL DiscoveryAgent — we need sanitize_sample to actually run
    # inside ParserAgent.discover() before the first LLM invocation.
    parser = ParserAgent(
        file_storage=storage,
        llm_client=llm,
        accounts_repo=accounts,
        runs_repo=runs,
        discovery_agent=DiscoveryAgent(llm),
    )
    parser.run("r-pii", "c1", "pii.xlsx", date(2026, 3, 1))

    # Two LLM calls expected: one discovery, one mapping.
    assert [r["prompt"] for r in recorded] == [
        "discovery_prompt.txt",
        "mapping_prompt.txt",
    ]

    # Serialize all payloads and grep for the PII values from the fixture.
    all_payloads = json.dumps([r["context"] for r in recorded], default=str)
    assert "alice@example.com" not in all_payloads
    assert "123-45-6789" not in all_payloads
    assert "4111-1111-1111-1111" not in all_payloads
    # At least one [REDACTED] proves the sanitizer fired, not just that PII happened to be absent.
    assert "[REDACTED]" in all_payloads


# ---------------------------------------------------------------------------
# 5. Low-confidence pauses run
# ---------------------------------------------------------------------------


def test_low_confidence_pauses_run_at_awaiting_confirmation(drone_qbo_clean_bytes):
    low_plan = DiscoveryPlan(
        header_row_index=5,
        skip_row_indices=[0, 1, 2, 3, 4],
        column_mapping={"Account": "account", "Amount": "amount"},
        hierarchy_hints=[],
        discovery_confidence=0.50,
        notes="low",
    )
    fake = MagicMock(spec=DiscoveryAgent)
    fake.discover.side_effect = DiscoveryLowConfidence(low_plan)

    storage, llm, runs, accounts = _make_mocks(drone_qbo_clean_bytes)
    parser = ParserAgent(
        file_storage=storage,
        llm_client=llm,
        accounts_repo=accounts,
        runs_repo=runs,
        discovery_agent=fake,
    )

    with pytest.raises(DiscoveryLowConfidence):
        parser.run("r-low", "c1", "drone_mar.xlsx", date(2026, 3, 1))

    # Plan + _preview persisted BEFORE raise, approval_mode stays NULL.
    runs.set_discovery_plan.assert_called_once()
    args = runs.set_discovery_plan.call_args
    persisted = args.args[1] if len(args.args) > 1 else args.kwargs["plan"]
    mode = args.args[2] if len(args.args) > 2 else args.kwargs.get("approval_mode")
    assert "_preview" in persisted
    assert mode is None

    # State walk halted at discovering — orchestrator would transition from here.
    assert _status_walk(runs) == ["parsing", "discovering"]


# ---------------------------------------------------------------------------
# 6. Discovery failure → PARSING_FAILED (renamed from the original
#    discovery_failed name to match D2)
# ---------------------------------------------------------------------------


def test_discovery_failure_transitions_to_parsing_failed(drone_qbo_clean_bytes):
    fake = MagicMock(spec=DiscoveryAgent)
    fake.discover.side_effect = DiscoveryFailed("synthetic — plan invalid after retry")

    storage, llm, runs, accounts = _make_mocks(drone_qbo_clean_bytes)
    parser = ParserAgent(
        file_storage=storage,
        llm_client=llm,
        accounts_repo=accounts,
        runs_repo=runs,
        discovery_agent=fake,
    )

    with pytest.raises(DiscoveryFailed):
        parser.run("r-fail", "c1", "drone_mar.xlsx", date(2026, 3, 1))

    walk = _status_walk(runs)
    assert "parsing_failed" in walk
    # error_message set on the final update
    final_extra = runs.update_status.call_args.kwargs["extra"]
    assert "error_message" in final_extra


# ---------------------------------------------------------------------------
# 7. Subtotal safety net catches a misplan
# ---------------------------------------------------------------------------


def test_subtotal_safety_net_catches_misplan(drone_qbo_clean_bytes):
    """A plan that skips metadata but FORGETS subtotals → Normalizer catches them."""
    plan = DiscoveryPlan(
        header_row_index=5,
        skip_row_indices=[
            0,
            1,
            2,
            3,
            4,
        ],  # only metadata — subtotals deliberately missed
        column_mapping={
            "Date": "date",
            "Account": "account",
            "Category": None,
            "Description": "description",
            "Amount": "amount",
            "Debit": None,
            "Credit": None,
        },
        hierarchy_hints=[],
        discovery_confidence=0.95,
        notes="intentionally incomplete — tests safety net",
    )
    storage, llm, runs, accounts = _make_mocks(drone_qbo_clean_bytes)
    llm.call.side_effect = _canned_mapping
    parser = ParserAgent(
        file_storage=storage,
        llm_client=llm,
        accounts_repo=accounts,
        runs_repo=runs,
        discovery_agent=_make_fake_discovery(plan),
    )
    parser.run("r-subs", "c1", "drone_mar.xlsx", date(2026, 3, 1))

    preview = runs.set_parse_preview.call_args.args[1]
    drops = preview["drops"]
    assert drops["total_dropped"] > 0, "safety net should have fired on subtotals"

    reasons = {e["reason"] for e in drops["entries"]}
    assert "subtotal_safety_net" in reasons

    # At least one snippet should mention a classic subtotal label.
    snippets = [e["account_snippet"] for e in drops["entries"]]
    assert any(
        s.startswith("Total")
        or s.startswith("Gross")
        or s.startswith("Net")
        or "%" in s
        for s in snippets
    ), f"expected a subtotal-shaped snippet; got {snippets!r}"


# ---------------------------------------------------------------------------
# 8. Bonus: merged cells flagged by read_raw_cells
# ---------------------------------------------------------------------------


def test_merged_cells_in_banner_row_detected(merged_cells_xlsx_bytes, tmp_path):
    """The DRONE fixtures have no merged cells. This one does — and the
    is_merged flag is the hint the Discovery prompt uses to identify
    NetSuite-style banners that span multiple columns.
    """
    tmp = tmp_path / "merged.xlsx"
    tmp.write_bytes(merged_cells_xlsx_bytes)
    rows = read_raw_cells(tmp)

    # Row 0 is the merged metadata title. Row 2 is the merged REVENUE banner.
    # (is_merged is True if ANY cell in the row sits inside a merged range.)
    assert rows[0]["is_merged"] is True
    assert rows[2]["is_merged"] is True

    # Line items (rows 3, 4) should not be merged.
    assert rows[3]["is_merged"] is False
    assert rows[4]["is_merged"] is False

    # Bold flag independently verified — the header row AND the banner row
    # are bold (what Discovery's prompt uses in conjunction with is_merged).
    assert rows[1]["is_bold"] is True  # header
    assert rows[2]["is_bold"] is True  # banner


# ---------------------------------------------------------------------------
# 9. NetSuite XML — skipped, post-MVP
# ---------------------------------------------------------------------------


@pytest.mark.skip(
    reason=(
        "Post-MVP: _read_xml_spreadsheet in file_reader.py still has its own "
        "first-non-empty-row header detection. That doesn't align with the "
        "Normalizer's raw-row-index assumption (established in Step 9b when "
        "read_file was flipped to header=None for xlsx/csv/xls_binary). "
        "Fixing requires (a) a real NetSuite XML sample to reverse-engineer "
        "against and (b) converting _read_xml_spreadsheet to raw-index mode. "
        "Not demo-critical — DRONE files are xlsx."
    )
)
def test_netsuite_xml_falls_back_without_formatting_hints():
    pass
