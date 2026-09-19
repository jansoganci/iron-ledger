"""Python-only named close controls. Claude does not count or classify these.

Redhawk first-delivery contract (computed from docs/demo_data/redhawk, March 2026):

Payroll — `redhawk_payroll_mar_2026.xlsx`
  Amount: discovered amount column (Base Compensation in the fixture). Bonus
  and Benefits Cost are out of scope unless discovery maps them to amount.
  Period: Pay Period matching the close month when that column exists.
  Grain: Role → GL, never employee names, never file-total (five roles).
  Installation Labor is subcontracted COGS and is not a payroll target.
  Fixture after confirmed Role mapping vs GL: Owner Salary 5,500 / 5,500,
  Technician Wages 6,200 / 6,200, Admin Wages 1,400 / 1,400.

Vendors — `redhawk_vendor_invoices_mar_2026.xlsx`
  Amount: Amount column. Product Line is the allocation grain. The whole file
  is not one COGS account. Fuel/insurance/marketing invoices stay vendor
  expense lines; they do not open a Fuel control.
  Fixture after confirmed Product Line mapping: Equipment & Parts 7,200,
  Central Station Monitoring 1,105, Vehicle & Fuel 1,840, Insurance 1,180,
  Marketing & Advertising 780 — each matching GL.

Contracts — `redhawk_contracts_mar_2026.xlsx`
  Amount: Monthly Fee, not multiplied. Roster status/last-billed rules stay.
  File-total → Service Revenue (do not invent Monitoring Revenue).
  Fixture: active fees 3,825.00 vs GL 3,540.00, gap 285.00; n_active 85,
  n_billed_in_period 82, count_delta 3. Material → has_exceptions.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Any

from backend import messages
from backend.agents.consolidator import _is_gl_label, _is_material
from backend.domain.contracts import (
    ControlComparison,
    ControlResult,
    ControlSummary,
    ReconciliationClassification,
)
from backend.tools.file_type import match_file_type
from backend.tools.tie_out_summary import is_coverage_item

SUPPORTED_CONTROL_KEYS: tuple[str, ...] = (
    "payroll",
    "supplier_invoices",
    "contracts",
)
CONTROL_LABELS: dict[str, str] = {
    "payroll": "Payroll",
    "supplier_invoices": "Vendors",
    "contracts": "Contracts",
}
REPORT_RECON_SCHEMA = "close_controls_v1"

_NEXT_ACTION = {
    "tied_out": messages.CONTROL_NEXT_REVIEW_EVIDENCE,
    "has_exceptions": messages.CONTROL_NEXT_REVIEW_EXCEPTION,
    "mapping_required": messages.CONTROL_NEXT_CONFIRM_MAPPING,
    "source_missing": messages.CONTROL_NEXT_ADD_SOURCE,
    "not_compared": messages.CONTROL_NEXT_INCOMPLETE,
}


def _filename(raw: object) -> str:
    if not raw:
        return ""
    return Path(str(raw)).name


def pack_report_reconciliations(
    items: list[dict] | None,
    control_summary: ControlSummary | dict | None,
) -> dict:
    summary = (
        control_summary
        if isinstance(control_summary, dict)
        else (
            control_summary.model_dump(mode="json")
            if control_summary is not None
            else None
        )
    )
    return {
        "schema": REPORT_RECON_SCHEMA,
        "items": list(items or []),
        "control_summary": summary,
    }


def unpack_report_reconciliations(
    raw: object,
) -> tuple[list[dict], ControlSummary | None]:
    if raw is None:
        return [], None
    if isinstance(raw, list):
        items = [i for i in raw if isinstance(i, dict)]
        return items, None
    if isinstance(raw, dict) and raw.get("schema") == REPORT_RECON_SCHEMA:
        items = [i for i in (raw.get("items") or []) if isinstance(i, dict)]
        payload = raw.get("control_summary")
        if not payload:
            return items, None
        try:
            return items, ControlSummary.model_validate(payload)
        except Exception:
            return items, None
    if isinstance(raw, dict) and "account" in raw:
        return [raw], None
    return [], None


def coverage_account_count(recon_items: list[dict] | None) -> int:
    return sum(1 for item in recon_items or [] if is_coverage_item(item))


def _classification_for(
    account: str, recon_items: list[dict]
) -> ReconciliationClassification | None:
    for item in recon_items:
        if is_coverage_item(item):
            continue
        if item.get("account") == account:
            token = item.get("classification")
            if token in {
                "timing_cutoff",
                "categorical_misclassification",
                "missing_je",
                "stale_reference",
                "accrual_mismatch",
                "structural_explained",
            }:
                return token
    return None


def _summarize_counts(controls: list[ControlResult], coverage: int) -> ControlSummary:
    compared = sum(1 for c in controls if c.status in {"tied_out", "has_exceptions"})
    with_exceptions = sum(1 for c in controls if c.status == "has_exceptions")
    not_evaluated = sum(
        1
        for c in controls
        if c.status in {"mapping_required", "source_missing", "not_compared"}
    )
    return ControlSummary(
        controls=controls,
        compared=compared,
        with_exceptions=with_exceptions,
        not_evaluated=not_evaluated,
        coverage_account_count=coverage,
        scope_note=messages.CONTROL_SCOPE_INSTALL_FUEL,
        legacy=False,
    )


def build_legacy_control_summary(recon_items: list[dict] | None) -> ControlSummary:
    """Historical reports: never invent Tied out from file-presence + no card."""
    items = [i for i in (recon_items or []) if isinstance(i, dict)]
    exception_groups: set[str] = set()
    for item in items:
        if is_coverage_item(item):
            continue
        for src in item.get("sources") or []:
            name = _filename(src.get("source_file") if isinstance(src, dict) else None)
            kind = match_file_type(name) if name else None
            if kind in SUPPORTED_CONTROL_KEYS:
                exception_groups.add(kind)

    controls: list[ControlResult] = []
    for key in SUPPORTED_CONTROL_KEYS:
        if key in exception_groups:
            status = "has_exceptions"
            reason = None
        else:
            status = "not_compared"
            reason = messages.CONTROL_HISTORICAL_INSUFFICIENT
        controls.append(
            ControlResult(
                key=key,  # type: ignore[arg-type]
                label=CONTROL_LABELS[key],
                status=status,  # type: ignore[arg-type]
                mapping_mode="none",
                next_action=_NEXT_ACTION[status],
                incomplete_reason=reason,
            )
        )
    summary = _summarize_counts(controls, coverage_account_count(items))
    summary.legacy = True
    return summary


def build_control_summary(
    *,
    period: date | None,
    source_files: list[str],
    per_file_rows: dict[str, list[dict]],
    gl_amounts: dict[str, float],
    amount_scopes: dict[str, str],
    file_total_mappings: dict[str, str],
    mapping_pending_files: set[str],
    recon_items: list[dict] | None,
    empty_files: set[str] | None = None,
    mapping_modes: dict[str, str] | None = None,
) -> ControlSummary:
    """Derive named-control statuses from mapped amounts. No LLM."""
    items = [i for i in (recon_items or []) if isinstance(i, dict)]
    empty = empty_files or set()
    modes = mapping_modes or {}
    files_by_control: dict[str, list[str]] = {k: [] for k in SUPPORTED_CONTROL_KEYS}
    other_supporting: list[str] = []

    for raw in source_files:
        name = _filename(raw)
        if not name:
            continue
        kind = match_file_type(name)
        if kind == "general_ledger" or _is_gl_label(name):
            continue
        if kind in SUPPORTED_CONTROL_KEYS:
            files_by_control[kind].append(name)
        else:
            other_supporting.append(name)

    gl_names = set(gl_amounts)

    def contributions_from(filenames: list[str]) -> dict[str, float]:
        totals: dict[str, float] = defaultdict(float)
        for fname in filenames:
            for row in per_file_rows.get(fname, []):
                acct = str(row.get("account") or "").strip()
                if not acct:
                    continue
                try:
                    totals[acct] += float(row.get("amount") or 0)
                except (TypeError, ValueError):
                    continue
        return {k: round(v, 2) for k, v in totals.items()}

    all_non_gl_files = [
        _filename(f)
        for f in source_files
        if _filename(f)
        and not _is_gl_label(_filename(f))
        and match_file_type(_filename(f)) != "general_ledger"
    ]

    controls: list[ControlResult] = []
    for key in SUPPORTED_CONTROL_KEYS:
        files = files_by_control[key]
        label = CONTROL_LABELS[key]
        if not files:
            controls.append(
                ControlResult(
                    key=key,  # type: ignore[arg-type]
                    label=label,
                    status="source_missing",
                    mapping_mode="none",
                    next_action=_NEXT_ACTION["source_missing"],
                    incomplete_reason="No supporting file for this control was uploaded.",
                    period=period,
                )
            )
            continue

        source_file = files[0]
        if len(files) > 1:
            controls.append(
                ControlResult(
                    key=key,  # type: ignore[arg-type]
                    label=label,
                    status="not_compared",
                    period=period,
                    mapping_mode="none",
                    next_action=messages.CONTROL_NEXT_COMBINE_SOURCES,
                    incomplete_reason=messages.CONTROL_MULTIPLE_SOURCES,
                )
            )
            continue
        pending = [f for f in files if f in mapping_pending_files]
        if pending:
            controls.append(
                ControlResult(
                    key=key,  # type: ignore[arg-type]
                    label=label,
                    status="mapping_required",
                    source_file=source_file,
                    period=period,
                    amount_scope=amount_scopes.get(source_file),
                    mapping_mode=modes.get(source_file, "none"),  # type: ignore[arg-type]
                    next_action=_NEXT_ACTION["mapping_required"],
                    incomplete_reason=messages.CONTROL_UNCONFIRMED_MAPPING,
                )
            )
            continue

        if all(f in empty for f in files):
            controls.append(
                ControlResult(
                    key=key,  # type: ignore[arg-type]
                    label=label,
                    status="not_compared",
                    source_file=source_file,
                    period=period,
                    amount_scope=amount_scopes.get(source_file),
                    mapping_mode=modes.get(source_file, "none"),  # type: ignore[arg-type]
                    next_action=_NEXT_ACTION["not_compared"],
                    incomplete_reason=messages.CONTROL_EMPTY_SOURCE,
                )
            )
            continue

        contrib = contributions_from(files)
        other_files = [f for f in all_non_gl_files if f not in files]
        other_contrib = contributions_from(other_files)
        overlap = sorted(acct for acct in contrib if acct in other_contrib)

        mapping_mode = modes.get(source_file)
        if mapping_mode is None:
            mapping_mode = "file_total" if source_file in file_total_mappings else "row"

        comparisons: list[ControlComparison] = []
        any_incomplete = False
        any_exception = False

        if not contrib:
            controls.append(
                ControlResult(
                    key=key,  # type: ignore[arg-type]
                    label=label,
                    status="not_compared",
                    source_file=source_file,
                    period=period,
                    amount_scope=amount_scopes.get(source_file),
                    mapping_mode=mapping_mode,  # type: ignore[arg-type]
                    next_action=_NEXT_ACTION["not_compared"],
                    incomplete_reason=messages.CONTROL_EMPTY_SOURCE,
                )
            )
            continue

        for acct, src_amt in sorted(contrib.items()):
            gl_amt = gl_amounts.get(acct)
            in_gl = acct in gl_names
            if acct in overlap:
                any_incomplete = True
                difference = None
                if gl_amt is not None:
                    difference = round(src_amt - gl_amt, 2)
                comparisons.append(
                    ControlComparison(
                        gl_account=acct,
                        supporting_amount=src_amt,
                        gl_amount=gl_amt,
                        difference=difference,
                        complete=False,
                        incomplete_reason=messages.CONTROL_OVERLAPPING_SOURCES,
                    )
                )
                continue
            if not in_gl or gl_amt is None:
                any_incomplete = True
                comparisons.append(
                    ControlComparison(
                        gl_account=acct,
                        supporting_amount=src_amt,
                        gl_amount=None,
                        difference=None,
                        complete=False,
                        incomplete_reason=messages.CONTROL_MISSING_GL,
                    )
                )
                continue

            difference = round(src_amt - gl_amt, 2)
            delta_pct = (difference / gl_amt) if gl_amt != 0 else None
            material = _is_material(difference, delta_pct)
            if material:
                any_exception = True
            comparisons.append(
                ControlComparison(
                    gl_account=acct,
                    supporting_amount=src_amt,
                    gl_amount=gl_amt,
                    difference=difference,
                    classification=(
                        _classification_for(acct, items) if material else None
                    ),
                    complete=True,
                )
            )

        if any_incomplete:
            status = "not_compared"
            reason = messages.CONTROL_PARTIAL_SCOPE
            if overlap:
                reason = messages.CONTROL_OVERLAPPING_SOURCES
            elif any(
                c.incomplete_reason == messages.CONTROL_MISSING_GL for c in comparisons
            ):
                reason = messages.CONTROL_MISSING_GL
            if any_exception:
                # Findings from the evaluated portion stay visible.
                pass
        elif any_exception:
            status = "has_exceptions"
            reason = None
        else:
            status = "tied_out"
            reason = None

        controls.append(
            ControlResult(
                key=key,  # type: ignore[arg-type]
                label=label,
                status=status,  # type: ignore[arg-type]
                source_file=source_file,
                period=period,
                amount_scope=amount_scopes.get(source_file),
                gl_targets=[c.gl_account for c in comparisons],
                mapping_mode=mapping_mode,  # type: ignore[arg-type]
                comparisons=comparisons,
                next_action=_NEXT_ACTION[status],
                incomplete_reason=reason,
            )
        )

    return _summarize_counts(controls, coverage_account_count(items))


def control_context_from_parse_preview(parse_preview: dict[str, Any] | None) -> dict:
    preview = parse_preview or {}
    return {
        "source_files": list(preview.get("control_source_files") or []),
        "per_file_rows": dict(preview.get("control_per_file_rows") or {}),
        "gl_amounts": {
            str(k): float(v)
            for k, v in (preview.get("control_gl_amounts") or {}).items()
        },
        "amount_scopes": dict(preview.get("control_amount_scopes") or {}),
        "file_total_mappings": dict(preview.get("file_total_decisions") or {}),
        "mapping_pending_files": set(preview.get("control_mapping_pending") or []),
        "empty_files": set(preview.get("control_empty_files") or []),
        "mapping_modes": dict(preview.get("control_mapping_modes") or {}),
        "period": preview.get("control_period"),
    }


def summary_from_parse_preview(
    parse_preview: dict[str, Any] | None,
    recon_items: list[dict] | None,
) -> ControlSummary:
    ctx = control_context_from_parse_preview(parse_preview)
    period_raw = ctx.get("period")
    period: date | None
    if isinstance(period_raw, date):
        period = period_raw
    elif period_raw:
        try:
            period = date.fromisoformat(str(period_raw)[:10])
        except ValueError:
            period = None
    else:
        period = None
    if not ctx["source_files"] and not ctx["per_file_rows"]:
        return build_legacy_control_summary(recon_items)
    return build_control_summary(
        period=period,
        source_files=ctx["source_files"],
        per_file_rows=ctx["per_file_rows"],
        gl_amounts=ctx["gl_amounts"],
        amount_scopes=ctx["amount_scopes"],
        file_total_mappings=ctx["file_total_mappings"],
        mapping_pending_files=ctx["mapping_pending_files"],
        recon_items=recon_items,
        empty_files=ctx["empty_files"],
        mapping_modes=ctx["mapping_modes"],
    )
