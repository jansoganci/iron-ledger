"""Python-only close-checklist counts. Claude does not compute N of M."""

from __future__ import annotations

from pathlib import Path

from backend.tools.file_type import match_file_type

GROUP_ORDER: tuple[str, ...] = (
    "payroll",
    "supplier_invoices",
    "contracts",
    "other",
)

GROUP_LABELS: dict[str, str] = {
    "payroll": "Payroll",
    "supplier_invoices": "Vendors",
    "contracts": "Contracts",
    "other": "Other supporting files",
}

_NAMED_GROUPS = frozenset({"payroll", "supplier_invoices", "contracts"})


def is_coverage_item(item: dict) -> bool:
    if item.get("card_kind") == "coverage":
        return True
    hints = item.get("hints") or {}
    if isinstance(hints, dict):
        return bool(hints.get("is_gl_only"))
    return False


def tie_out_group_for_filename(filename: str) -> str | None:
    """Map a supporting file to a checklist group. GL returns None."""
    kind = match_file_type(filename)
    if kind == "general_ledger":
        return None
    if kind in _NAMED_GROUPS:
        return kind
    return "other"


def _source_filename(src: object) -> str | None:
    if isinstance(src, dict):
        raw = src.get("source_file")
    else:
        raw = getattr(src, "source_file", None)
    if not raw:
        return None
    return Path(str(raw)).name


def group_for_item(item: dict) -> str | None:
    """Exception cards group by the first non-GL supporting source file."""
    if is_coverage_item(item):
        return None
    for src in item.get("sources") or []:
        name = _source_filename(src)
        if not name:
            continue
        group = tie_out_group_for_filename(name)
        if group:
            return group
    return "other"


def build_tie_out_summary(
    source_files: list[str] | None,
    reconciliations: list[dict] | None,
) -> dict:
    """Counts from uploaded filenames + recon cards. No LLM, no new engine."""
    items = [i for i in (reconciliations or []) if isinstance(i, dict)]
    files_by_group: dict[str, set[str]] = {key: set() for key in GROUP_ORDER}

    for raw in source_files or []:
        name = Path(str(raw)).name if raw else ""
        if not name:
            continue
        group = tie_out_group_for_filename(name)
        if group:
            files_by_group[group].add(name)

    gap_keys: set[str] = set()
    not_compared = 0
    for item in items:
        if is_coverage_item(item):
            not_compared += 1
            continue
        group = group_for_item(item)
        if group:
            gap_keys.add(group)

    groups: list[dict] = []
    for key in GROUP_ORDER:
        files = sorted(files_by_group[key])
        if not files and key not in gap_keys:
            continue
        groups.append(
            {
                "key": key,
                "label": GROUP_LABELS[key],
                "status": "gap" if key in gap_keys else "clean",
                "files": files,
            }
        )

    compared = len(groups)
    with_gap = sum(1 for g in groups if g["status"] == "gap")
    return {
        "groups": groups,
        "compared": compared,
        "with_gap": with_gap,
        "not_compared": not_compared,
    }
