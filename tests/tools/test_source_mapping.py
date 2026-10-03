"""Deterministic vendor/expense memory helpers — no LLM, no I/O."""

from __future__ import annotations

from backend.domain.contracts import MappingDraftItem
from backend.domain.entities import SourceAccountMapping
from backend.tools.source_mapping import (
    annotate_draft_items,
    payroll_draft_items,
    remember_payroll_items,
    index_stored,
    is_payroll,
    is_persistable,
    remember_file_total_item,
    needs_user_review,
    persistable_upserts,
    remembered_file_total_decisions,
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


def test_payroll_choices_are_saved_like_vendor_names() -> None:
    assert is_payroll("payroll")
    assert is_persistable("payroll")
    assert is_persistable("supplier_invoices")
    assert is_persistable("contracts")


def test_payroll_roles_become_unselected_review_rows() -> None:
    from datetime import date

    items = payroll_draft_items(
        ["Owner / Operations", "Install Technician", ""],
        source_file="p.xlsx",
        amount_scope="Base Compensation",
        period=date(2026, 3, 1),
    )
    assert [i.source_pattern for i in items] == [
        "Owner / Operations",
        "Install Technician",
    ]
    assert all(i.origin == "new" and i.suggested_gl_account is None for i in items)
    assert all(not i.confident and i.mapping_mode == "row" for i in items)
    assert needs_user_review(items)
    assert persistable_upserts(
        items,
        {
            "Owner / Operations": "Owner Salary",
            "Install Technician": "Technician Wages",
        },
    ) == [
        ("payroll", "Owner / Operations", "Owner Salary"),
        ("payroll", "Install Technician", "Technician Wages"),
    ]


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
    assert remembered_decisions(items) == {"AlarmTech Industries": "Equipment COGS"}


def test_haiku_none_with_saved_row_is_remembered() -> None:
    stored = {("supplier_invoices", "Electricity"): "Utilities"}
    items = annotate_draft_items(
        [
            _item(
                source_pattern="Electricity", suggested_gl_account=None, confident=False
            )
        ],
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


def test_saved_payroll_role_is_reused_when_the_wage_account_is_on_the_gl() -> None:
    from datetime import date

    draft = payroll_draft_items(
        ["Owner / Operations", "New Role"],
        source_file="payroll.xlsx",
        amount_scope="Base Compensation",
        period=date(2026, 3, 1),
    )
    stored = {("payroll", "Owner / Operations"): "Owner Salary"}
    items = remember_payroll_items(draft, stored, ["Owner Salary", "Technician Wages"])
    by_role = {item.source_pattern: item for item in items}
    assert by_role["Owner / Operations"].origin == "remembered"
    assert by_role["Owner / Operations"].suggested_gl_account == "Owner Salary"
    assert by_role["New Role"].origin == "new"
    assert needs_user_review(items)
    assert remembered_decisions(items) == {"Owner / Operations": "Owner Salary"}


def test_saved_payroll_role_is_asked_again_when_the_wage_account_is_gone() -> None:
    from datetime import date

    draft = payroll_draft_items(
        ["Owner / Operations"],
        source_file="payroll.xlsx",
        amount_scope="Base Compensation",
        period=date(2026, 3, 1),
    )
    stored = {("payroll", "Owner / Operations"): "Owner Salary"}
    items = remember_payroll_items(draft, stored, ["Technician Wages"])
    assert items[0].origin == "new"
    assert items[0].suggested_gl_account is None
    assert needs_user_review(items)


def test_saved_contract_file_mapping_ignores_filename_when_account_exists() -> None:
    item = _item(
        source_pattern="(entire file)",
        source_file="renamed_customer_roster.xlsx",
        file_type="contracts",
        mapping_mode="file_total",
        suggested_gl_account="Service Revenue",
    )
    saved = {("contracts", "(entire file)"): "Service Revenue"}

    remembered = remember_file_total_item(item, saved, ["Service Revenue"])

    assert remembered.origin == "remembered"
    assert remembered.suggested_gl_account == "Service Revenue"
    assert remembered_file_total_decisions([remembered]) == {
        "renamed_customer_roster.xlsx": "Service Revenue"
    }
    assert not needs_user_review([remembered])


def test_saved_contract_file_mapping_is_asked_again_when_account_is_gone() -> None:
    item = _item(
        source_pattern="(entire file)",
        source_file="contracts_april.xlsx",
        file_type="contracts",
        mapping_mode="file_total",
        suggested_gl_account="Service Revenue",
    )
    remembered = remember_file_total_item(
        item,
        {("contracts", "(entire file)"): "Service Revenue"},
        ["Other Revenue"],
    )

    assert remembered.origin == "new"
    assert remembered.suggested_gl_account is None
    assert needs_user_review([remembered])


def test_persistable_upserts_keep_payroll() -> None:
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
    assert rows == [
        ("supplier_invoices", "AlarmTech Industries", "Equipment COGS"),
        ("payroll", "Alice Johnson", "Salaries & Wages"),
    ]


def test_persistable_upserts_remember_contract_file_total() -> None:
    items = [
        _item(
            source_pattern="(entire file)",
            source_file="contracts.xlsx",
            file_type="contracts",
            mapping_mode="file_total",
            suggested_gl_account="Service Revenue",
        ),
        _item(),
    ]
    rows = persistable_upserts(
        items,
        {
            "AlarmTech Industries": "Equipment COGS",
        },
        {"contracts.xlsx": "Service Revenue"},
    )
    assert rows == [
        ("contracts", "(entire file)", "Service Revenue"),
        ("supplier_invoices", "AlarmTech Industries", "Equipment COGS"),
    ]


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
