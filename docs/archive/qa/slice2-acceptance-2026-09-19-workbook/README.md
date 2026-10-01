# Slice 2 acceptance follow-up — 2026-09-19

Does **not** overwrite `docs/qa/slice2-acceptance-2026-09-19/`.
Canonical Redhawk binaries were not modified. No company, user, run, or
report was written to any Supabase project. No paid LLM call.

This folder is **not** a live month-end run.

## Environment (no secrets)

| Item | Finding |
|---|---|
| `APP_ENV` | `development` |
| API | `localhost:8000` (not running during this check) |
| Configured Supabase host | remote `*.supabase.co` (not local Kong) |
| MCP-visible projects | `ornet-crm`, `RealDesk CRM` — neither is Month Proof, neither matches the configured host |
| Named test tenant in repo docs | none |
| Browser automation tools | not available in this session |
| Excel PDF export | failed (localized Excel parameter error) |
| Workbook renderer used | Apple Numbers → PDF → page PNGs |

## Pandas (not LLM)

From `docs/demo_data/redhawk/` March 2026:

- supporting Monthly Fee (active): **3,825.00**
- GL Service Revenue: **3,540.00**
- difference: **285.00**
- n_active 85 / n_billed_in_period 82 / count_delta 3

## Files

| File | What it is |
|---|---|
| `redhawk_amounts.json` | Pandas totals |
| `redhawk_close_package.xlsx` | Current exporter, Redhawk-shaped controls |
| `synthetic_mixed_controls.xlsx` | Two payroll files + vendor tie-out + missing-GL contracts |
| `missing_evidence_controls.xlsx` | All three controls source_missing |
| `historical_legacy_controls.xlsx` | Legacy list shape; no invented filenames |
| `pdf/` | Numbers-exported PDFs of those workbooks |
| `screenshots/*-p2.pdf.png` | Reconciliations pages from those PDFs |

## Scenario results this round

| Scenario | Result | How verified | Real vs mocked |
|---|---|---|---|
| Clean payroll evidence without exception card | PASS | Numbers Reconciliations: three $0 rows | Local workbook, not live UI |
| Contracts 3,825 / 3,540 / 285 | PASS | Pandas + Numbers evidence row | Local |
| Missing supporting source | PASS | Numbers missing workbook | Local |
| Missing GL evidence | PASS | Mixed workbook, Monitoring Revenue | Local |
| Two files for one control | PASS | `payroll_a.xlsx, payroll_b.xlsx`, Not compared, combine instruction | Local |
| Historical no invented filenames | PASS | Legacy workbook | Local |
| Bank / install-fuel not sign-off | PASS | Scope sentences; no “period closed” | Local |
| Three sheets preserved | PASS | P&L, Reconciliations, Source Breakdown | Local |
| Authenticated browser download | BLOCKED | No authorized tenant; no browser tools | — |
| Live mapping → report journey | BLOCKED | Writes to configured remote project not authorized | — |
| Stale export in live QA company | BLOCKED | Same | TestClient 409 remains local-only |
| 60-second office-manager read | BLOCKED | Agent read of Numbers page only; no human tester | Agent-led |

## Actual workbook visual (Numbers)

PASS for layout of local packages:

- Distinct **Control summary** and **Comparison evidence** headers.
- Evidence columns: Control, Source file, GL account, Supporting amount, GL amount, Difference, classification/reason.
- Long filenames wrap rather than clip. Mid-word wraps remain a readability note, not a mislabeled-column defect.
- Currency values match pandas. Numbers displayed them with the Mac locale separators.

Excel itself could not be scripted to PDF in this environment. HTML reconstructions from the earlier folder are **not** used as the visual acceptance for this round.

## Created remote QA data

None. Cleanup not required.

## LLM

0 calls, $0.
