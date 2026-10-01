# Slice 2 acceptance evidence — 2026-09-19

Synthetic QA plus local tests. Canonical Redhawk fixtures under
`docs/demo_data/redhawk/` were not modified. No company, user, or run was
written to the configured remote Supabase project. This is not a live
month-end run.

| File | What it is |
|---|---|
| `redhawk_amounts.json` | Pandas totals from the Redhawk workbooks |
| `redhawk_close_package.xlsx` | `build_close_package` after the four fixes |
| `synthetic_mixed_controls.xlsx` | Two payroll files (one empty) + clean vendor + missing-GL contracts |
| `missing_evidence_controls.xlsx` | All three controls source_missing |
| `historical_legacy_controls.xlsx` | Pre-`close_controls_v1` list shape; no invented filenames |
| `excel_cell_inspection.json` | Cell values, wrap flags, column widths, row heights |
| `screenshots/` | Login/register/landing from the blocked live path; Excel HTML reconstructions |

Excel PNGs named `excel-*-reconciliations.png` are HTML reconstructions that
apply the exporter's column widths and wrap flags to the real cell values.
Microsoft Excel automation remains blocked by macOS Accessibility.

## Correction verification (same day)

| Fix | Local result | Live authenticated journey |
|---|---|---|
| 1 Authenticated Excel download | PASS — `apiFetchBlob` + JWT + Blob + revoke; TestClient 200/403 | BLOCKED — no authorized test tenant |
| 2 Evidence headers and readability | PASS — separate Control summary / Comparison evidence; widths persist | BLOCKED |
| 3 Name files that prevent comparison | PASS — `payroll_a.xlsx, payroll_b.xlsx` in report contract and Excel | BLOCKED |
| 4 Stale export mixing | PASS — 409 `REPORT_STALE_EXPORT`; unchanged timestamps still 200 | BLOCKED |

Redhawk contracts (pandas): supporting 3,825.00; GL Service Revenue 3,540.00;
difference 285.00.

Verdict remains **NOT READY** until a live authenticated mapping → report →
download walkthrough is authorized.
