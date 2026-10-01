# Close Checklist Slice 2 — Live acceptance test plan

**Product decision:** 2026-09-17  
**Test date:** 2026-09-20  
**Status:** Partially executed; blocked at Analyze
**Acceptance verdict:** Not ready

This is the executable test plan for the live authenticated walkthrough. It is
separate from the 2026-09-19 evidence, which remains historical. The test covers
the first Dil 2 delivery only: Payroll, Vendors, and Contracts. Installation,
fuel, bank line matching, sign-off, `closed`, SQL, and period locking are out.

## Test environment

| Field | Value |
|---|---|
| Frontend/backend | `http://localhost:5174` / `http://localhost:8000` (health reachable) |
| Supabase project | Existing Redhawk demo environment via normal app auth |
| QA user | `demo@redhawkdemo.com` (secret omitted) |
| QA company | Existing Redhawk demo company; no new company created |
| Period | March 2026 |
| LLM mode | Live or mocked; record provider/model and approved call limit |
| Browser | Record browser and version |
| Workbook viewer | Excel, Apple Numbers, or LibreOffice; record version |

Do not use the production or an unidentified Supabase project. Do not place
passwords, API keys, tokens, customer data, or raw PII in this file or in
screenshots.

## Files and expected amounts

Use the canonical Redhawk files without modifying them:

- `docs/demo_data/redhawk/redhawk_gl_mar_2026.xlsx`
- `docs/demo_data/redhawk/redhawk_payroll_mar_2026.xlsx`
- `docs/demo_data/redhawk/redhawk_vendor_invoices_mar_2026.xlsx`
- `docs/demo_data/redhawk/redhawk_contracts_mar_2026.xlsx`

Deterministic Redhawk expectation, calculated with pandas:

| Check | Supporting | GL | Difference | Expected result |
|---|---:|---:|---:|---|
| Contracts → Service Revenue | 3,825.00 | 3,540.00 | 285.00 | Has exceptions |
| Payroll | Role-level amounts | Matching wage accounts | 0.00 on clean rows | Tied out where full scope is confirmed |

Create synthetic copies or fixtures only for the edge cases below. Keep them
separate from `docs/demo_data/redhawk/`.

## Execution order

1. Confirm the environment is authorized and record it above.
2. Sign in through the normal browser UI.
3. Create or select the QA company and choose March 2026.
4. Upload the GL and the three Redhawk supporting files.
5. Complete the mapping review. Record whether mapping was live or mocked.
6. Generate the report and wait for the terminal report state.
7. Refresh and reopen the report.
8. Read the report as an office manager in 60 seconds.
9. Download Excel using the visible report button.
10. Open the actual workbook in the recorded viewer.
11. Run the stale-export scenario through the supported regeneration flow.
12. Save screenshots and workbook evidence under this dated directory.

## Scenario matrix

Record `PASS`, `FAIL`, or `BLOCKED` and link evidence for every row.

| ID | Scenario | Expected result | Result | Evidence / notes |
|---|---|---|---|---|
| L1 | Sign in and protected report route | Authorized user reaches the app; unauthenticated protected routes do not expose data | PASS | Authenticated browser reached Upload, Dashboard, and Reports; Reports showed 0 reports. |
| L2 | Redhawk upload and mapping | Files parse; mapping choices are explicit; no raw PII is shown to the LLM or report | BLOCKED | Four Redhawk files loaded successfully. `localhost:5174` was blocked by CORS (`400 Disallowed CORS origin`). Retrying from the already-running `localhost:5173` bypassed CORS but returned “Something went wrong”; no mapping review or report was created. |
| L3 | Clean payroll comparison | Evidence rows are visible even when no exception card exists; status is Tied out only after full scope |  |  |
| L4 | Contract mismatch | Service Revenue is the target; 3,825.00 vs 3,540.00 and 285.00 are shown; status is Has exceptions |  |  |
| L5 | Missing supporting source | Status is Source missing or Not compared, never Tied out |  |  |
| L6 | Missing GL evidence | Status is Not compared with a clear next action |  |  |
| L7 | Empty supporting file | Empty source cannot pass; reason is visible |  |  |
| L8 | Two files for one control | Status is Not compared; every filename is listed; combine/remove-duplicates instruction is shown |  |  |
| L9 | Account-less monthly-fee roster | File-total target requires explicit confirmation; customer names are not sent as GL accounts |  |  |
| L10 | Contracts with two real GL targets | Row mapping is retained; file-total is rejected |  |  |
| L11 | Ambiguous contracts schema | Clear mapping/schema error; no report or background processing starts |  |  |
| L12 | Invalid mapping confirmation | Blank, missing, extra, or invalid decisions return an error with no side effects |  |  |
| L13 | Excel download | Button uses authenticated API; valid workbook downloads with a sensible filename |  |  |
| L14 | Excel parity | Statuses, filenames, targets, amounts, reasons, and next actions match the web report |  |  |
| L15 | Excel visual layout | Headers, wrapping, widths, heights, currency, and long text are readable in the actual viewer |  |  |
| L16 | Stale export | Server rejects stale export clearly; it never mixes newer P&L with stored controls |  |  |
| L17 | Unchanged export | Current report exports successfully and remains internally consistent |  |  |
| L18 | Bank and scope wording | Bank remains outside Month Proof; installation/fuel remain scope notes; no period-closed claim |  |  |
| L19 | 60-second read | User can identify checked controls, open work, missing evidence, evidence source, and next action |  |  |

## Edge-case fixture notes

- **L8:** two payroll files for the same period; test both duplicated content and
  one populated plus one empty file.
- **L9:** use a customer roster with `Monthly Fee`, `Status`, and `Last Billed`;
  confirm one GL target explicitly.
- **L10:** include a real `Account`/GL-account column with at least two targets.
- **L11:** remove the supported roster fields or provide an ambiguous amount
  scope.
- **L16:** generate a report, change the period data through the supported
  workflow, then attempt to export the old report. Do not edit terminal records
  in place.

## Evidence checklist

- [ ] Browser screenshots for sign-in, mapping, report, error, and download.
- [ ] Downloaded `.xlsx` from the actual report button.
- [ ] Screenshots or PDF render from the actual workbook viewer.
- [ ] API response/status evidence for stale export and invalid mappings.
- [ ] Record of live versus mocked LLM steps and call count/spend.
- [ ] Record of any QA company, files, runs, and reports created.
- [ ] No secrets or raw PII in saved evidence.

## Acceptance rule

The delivery is **READY** only when L1–L19 have no unresolved blocking `FAIL`
or `BLOCKED` result, the authenticated mapping → report → download journey has
completed, and the actual workbook is visually usable. Passing these controls
does not close the accounting period.

## Final result

**Verdict:** NOT READY — live journey blocked  
**Verification date:** 20 September 2026  
**Blocking items:** The original frontend port had a CORS mismatch. After using the allowed `localhost:5173`, the Analyze request still returned “Something went wrong”; the next diagnostic is the backend `/upload` error (likely storage/database/background-task configuration). No report, mapping review, Excel export, or stale-export test was created.  
**Evidence directory:** This directory  

## Continuation checkpoint

Stop point: 20 September 2026, after the second Analyze attempt.

- Browser session: authenticated Redhawk demo user; frontend `localhost:5173`.
- Fixture state: four March 2026 Redhawk files were loaded successfully in the UI.
- Do not re-upload or click Analyze again until the backend `/upload` failure is diagnosed.
- Next action: inspect the local backend trace/log for the failed authenticated upload, then resume at L2.
- No code, schema, deployment, or Supabase data changes were made by this test.
