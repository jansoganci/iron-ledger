"""Deterministic source-value → GL memory helpers.

No LLM. No I/O. AccountMapper still calls Haiku; this module overlays saved
vendor/expense mappings and decides whether the user must review.
"""

from __future__ import annotations

from backend import messages
from backend.domain.contracts import MappingDraft, MappingDraftItem, SourceFileType
from backend.domain.entities import SourceAccountMapping

PERSISTABLE_FILE_TYPES: frozenset[str] = frozenset({"supplier_invoices"})
PAYROLL_FILE_TYPE: SourceFileType = "payroll"


def mapping_confirmation_error(
    draft: MappingDraft,
    decisions: dict[str, str],
    file_total_decisions: dict[str, str],
) -> str | None:
    """Validate the entire confirmation before any persistence or pipeline work."""
    row_keys = {i.source_pattern for i in draft.items if i.mapping_mode == "row"}
    total_keys = {i.source_file for i in draft.items if i.mapping_mode == "file_total"}
    row_files = {i.source_file for i in draft.items if i.mapping_mode == "row"}
    if not draft.items or row_files & total_keys:
        return messages.MAPPING_DRAFT_INVALID
    if set(decisions) - row_keys or set(file_total_decisions) - total_keys:
        return messages.MAPPING_DRAFT_INVALID
    if set(decisions) != row_keys or set(file_total_decisions) != total_keys:
        return messages.MAPPING_CONFIRMATION_REQUIRED
    selected = [*decisions.values(), *file_total_decisions.values()]
    if any(not value.strip() for value in selected):
        return messages.MAPPING_CONFIRMATION_REQUIRED
    if any(value not in draft.gl_account_pool for value in selected):
        return messages.MAPPING_INVALID_GL_ACCOUNT
    return None


def is_persistable(file_type: str) -> bool:
    return file_type in PERSISTABLE_FILE_TYPES


def is_payroll(file_type: str) -> bool:
    return file_type == PAYROLL_FILE_TYPE


def auto_map_payroll(unique_values: list[str]) -> dict[str, str]:
    """Keep payroll lines as they are (total or meals/rent/salary/bonus)."""
    return {value: value for value in unique_values if value and str(value).strip()}


def index_stored(
    mappings: list[SourceAccountMapping],
) -> dict[tuple[str, str], str]:
    return {(row.file_type, row.source_pattern): row.gl_account for row in mappings}


def annotate_draft_items(
    items: list[MappingDraftItem],
    stored: dict[tuple[str, str], str],
) -> list[MappingDraftItem]:
    annotated: list[MappingDraftItem] = []
    for item in items:
        haiku_gl = item.suggested_gl_account
        remembered = stored.get((item.file_type, item.source_pattern))
        if remembered is None:
            annotated.append(
                item.model_copy(
                    update={
                        "origin": "new",
                        "haiku_gl_account": haiku_gl,
                        "remembered_gl_account": None,
                    }
                )
            )
            continue
        if haiku_gl is not None and haiku_gl != remembered:
            annotated.append(
                item.model_copy(
                    update={
                        "origin": "conflict",
                        "suggested_gl_account": None,
                        "confident": False,
                        "haiku_gl_account": haiku_gl,
                        "remembered_gl_account": remembered,
                    }
                )
            )
            continue
        annotated.append(
            item.model_copy(
                update={
                    "origin": "remembered",
                    "suggested_gl_account": remembered,
                    "confident": True,
                    "haiku_gl_account": haiku_gl,
                    "remembered_gl_account": remembered,
                }
            )
        )
    return annotated


def needs_user_review(items: list[MappingDraftItem]) -> bool:
    return any(item.origin in ("new", "conflict") for item in items)


def remembered_decisions(items: list[MappingDraftItem]) -> dict[str, str]:
    decisions: dict[str, str] = {}
    for item in items:
        if item.origin == "remembered" and item.suggested_gl_account:
            decisions[item.source_pattern] = item.suggested_gl_account
    return decisions


def persistable_upserts(
    items: list[MappingDraftItem],
    decisions: dict[str, str],
) -> list[tuple[str, str, str]]:
    """Return (file_type, source_pattern, gl_account) rows safe to remember."""
    out: list[tuple[str, str, str]] = []
    seen: set[tuple[str, str]] = set()
    for item in items:
        if item.mapping_mode == "file_total":
            continue
        if not is_persistable(item.file_type):
            continue
        gl_account = decisions.get(item.source_pattern)
        if not gl_account:
            continue
        key = (item.file_type, item.source_pattern)
        if key in seen:
            continue
        seen.add(key)
        out.append((item.file_type, item.source_pattern, gl_account))
    return out
