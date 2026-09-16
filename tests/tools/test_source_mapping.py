"""Deterministic vendor/expense memory helpers — no LLM, no I/O."""

from __future__ import annotations

from backend.domain.contracts import MappingDraftItem
from backend.domain.entities import SourceAccountMapping
from backend.tools.source_mapping import (
    annotate_draft_items,
    auto_map_payroll,
    index_stored,
    is_payroll,
    is_persistable,
    needs_user_review,
    persistable_upserts,
    remembered_decisions,
)


def _item(**kwargs) -> MappingDraftItem:
    payload = {
        "source_pattern": "AlarmTech Industries",
        "source_file": "vendor.xlsx",
        "file_type": "supplier_invoices",
        "suggested_gl_account": "Equipment COGS",
        "confident": True,
    }
    payload.update(kwargs)
    return MappingDraftItem.model_validate(payload)


def test_payroll_is_not_persistable() -> None:
    assert is_payroll("payroll")
    assert not is_persistable("payroll")
    assert is_persistable("supplier_invoices")
    assert not is_persistable("contracts")


def test_auto_map_payroll_keeps_sub_lines() -> None:
    mapping = auto_map_payroll(["Meals", "Office Rent", "Salary", "Bonus", ""])
    assert mapping == {
        "Meals": "Meals",
        "Office Rent": "Office Rent",
        "Salary": "Salary",
        "Bonus": "Bonus",
    }


def test_new_row_needs_review() -> None:
    items = annotate_draft_items([_item()], {})
    assert items[0].origin == "new"
    assert needs_user_review(items)


def test_remembered_match_skips_review() -> None:
    stored = {("supplier_invoices", "AlarmTech Industries"): "Equipment COGS"}
    items = annotate_draft_items([_item()], stored)
    assert items[0].origin == "remembered"
    assert items[0].suggested_gl_account == "Equipment COGS"
    assert not needs_user_review(items)
    assert remembered_decisions(items) == {
        "AlarmTech Industries": "Equipment COGS"
    }


def test_haiku_none_with_saved_row_is_remembered() -> None:
    stored = {("supplier_invoices", "Electricity"): "Utilities"}
    items = annotate_draft_items(
        [_item(source_pattern="Electricity", suggested_gl_account=None, confident=False)],
        stored,
    )
    assert items[0].origin == "remembered"
    assert items[0].suggested_gl_account == "Utilities"
    assert not needs_user_review(items)


def test_haiku_disagreement_is_conflict() -> None:
    stored = {("supplier_invoices", "AlarmTech Industries"): "Equipment COGS"}
    items = annotate_draft_items(
        [_item(suggested_gl_account="Subcontractor Costs")],
        stored,
    )
    assert items[0].origin == "conflict"
    assert items[0].suggested_gl_account is None
    assert items[0].remembered_gl_account == "Equipment COGS"
    assert items[0].haiku_gl_account == "Subcontractor Costs"
    assert needs_user_review(items)


def test_persistable_upserts_skip_payroll() -> None:
    items = [
        _item(),
        _item(
            source_pattern="Alice Johnson",
            source_file="payroll.xlsx",
            file_type="payroll",
            suggested_gl_account="Salaries & Wages",
        ),
    ]
    rows = persistable_upserts(
        items,
        {
            "AlarmTech Industries": "Equipment COGS",
            "Alice Johnson": "Salaries & Wages",
        },
    )
    assert rows == [("supplier_invoices", "AlarmTech Industries", "Equipment COGS")]


def test_index_stored_uses_company_file_type_pattern() -> None:
    indexed = index_stored(
        [
            SourceAccountMapping(
                id="m1",
                company_id="co-1",
                file_type="supplier_invoices",
                source_pattern="Phone",
                gl_account="Utilities",
            )
        ]
    )
    assert indexed[("supplier_invoices", "Phone")] == "Utilities"
