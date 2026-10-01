# Payroll mapping fix — live retest, 2026-10-01

**Verdict: READY** (for the payroll mapping fix and the three controls on Redhawk Mar 2026)
**Payroll:** Tied out. Technician Wages 6,200.00 / 6,200.00, Admin Wages 1,400.00 / 1,400.00, Owner Salary 5,500.00 / 5,500.00, difference 0.00. No Missing JE.

## Environment
Frontend `localhost:5173`, backend `localhost:8000`, Supabase project `lxvxqpgixwwpeileggds`, Redhawk demo company, `demo@redhawkdemo.com`, Mar 2026.
Uncommitted working tree (payroll mapping fix + `delete_monthly` FK fix). Files uploaded unmodified from `docs/demo_data/redhawk/`. "Replace this report" confirmed.
LLM live. This round: 4 Haiku discovery + 1 Haiku vendor mapping + Opus narrative/upgrade. (An earlier attempt the same day, run `149f3628…`, stalled in the browser tab before the mapping screen — 4 + 1 Haiku calls, no result; the polling of that tab stopped, a reload dropped the run. Not reproduced on this attempt.)

## Results
| Check | Result | Evidence |
|---|---|---|
| Payroll shown as 5 separate rows, none preselected ("-- choose --"), status New | PASS | screenshots/01_mapping_payroll_five_rows.jpg |
| GL target list = this period's GL accounts only (no role names) | PASS | dropdown options in the mapping step (Admin Wages … Vehicle & Fuel; 16 GL accounts) |
| Roles chosen by tester: Install/Lead Install/Service → Technician Wages, Office Administrator → Admin Wages, Owner / Operations → Owner Salary | PASS | screenshots/01 |
| Contracts file total stays Service Revenue ($3,825.00); 5 saved vendor names reused ("Saved") | PASS | screenshots/01 |
| Consolidation after confirm: 16 accounts (was 21 with role names as accounts) | PASS | backend log `consolidation_complete` |
| Payroll Tied out, 3 GL targets, difference 0 | PASS | screenshots/03_report_close_controls.jpg |
| Vendors Tied out (5 targets, difference 0) | PASS | screenshots/03 |
| Contracts Has exceptions: 3,825.00 vs 3,540.00, difference 285.00 | PASS | report text |
| No Missing JE and no role names as accounts (web report) | PASS | report: 7 GL accounts not compared, 1 to review |
| Excel: same statuses/amounts, no Missing JE, no role names | PASS | monthproof_2026-03-01_close_package.xlsx (Reconciliations sheet) |
| "Bank and card reconciliation is done outside Month Proof" present; no month-closed claim ("does not mean the month is closed") | PASS | report + xlsx |

## Notes (not failures)
- Gross profit moved from $14,405 to $18,905 and Total OPEX from $32,150 to $36,650 versus the earlier run (net income unchanged at ($17,745)). The earlier figures counted role names as separate COGS accounts; they now roll into the GL wage accounts. Worth a finance glance before sharing.
- Excel viewer rendering and the stale-export scenario were not part of this retest.
