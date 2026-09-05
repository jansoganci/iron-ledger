# Month Proof — full product test plan

*Written 30 August 2026. Executable by an agent or person with repo access and
nothing else — every step states the exact action and the exact expected
result. Fill in the Result column as you go.*

**Session note (30 Aug evening, cloud agent):** Section A API checks and B1–B2
were completed on a **different** machine that had `.env` + a running backend.
This VM does not. Results below distinguish **prior-session observed** from
**not run / blocked here**. Do not treat blocked rows as product failures.

**Do not treat any step as passed because "it looked right". Every expected
value below is a specific number, class name, or UI state.**

---

## 0. Prerequisites — read this before running anything

### 0.1 Live environment state (verified 30 August 2026)

| Item | State | Impact on this plan |
|---|---|---|
| Migrations applied live | **`0001`–`0009` only** | **`0010` is NOT applied.** `companies.monthly_revenue_band` does not exist on the live database. |
| `reports.reconciliations` | `jsonb` ✓ | Sections B/C/D fine |
| RLS | Enabled on all 7 public tables | ✓ |
| Seed data | **No DRONE Inc.** — 1 unrelated company, 0 accounts, 0 entries, 0 reports | You must create a company yourself (Section A) |
| Edge functions | None defined, none deployed | Nothing to test |
| Storage bucket | `financial-uploads` (private) ✓ | Uploads will work |

### 0.2 BLOCKER — apply migration `0010` first

**Section A cannot pass until this is done, and Sections B/C/D may 500 on
company lookup.** The backend reads `company.get("monthly_revenue_band")` in
`ComparisonAgent.run`, and `POST /companies` sends the column on insert.

```bash
supabase db push          # applies 0010_add_company_monthly_scale.sql
```

Then re-verify:

```sql
select column_name from information_schema.columns
 where table_schema='public' and table_name='companies'
   and column_name='monthly_revenue_band';   -- must return 1 row
```

- [x] `0010` applied and column confirmed — **Result: PASS (prior session, 30 Aug 2026).** Live project had `monthly_revenue_band` on `companies`; demo company Redhawk Alarm & Security LLC stored `'under_100k'`. **This cloud-agent VM could not re-query the live DB** (no `SUPABASE_*` / `.env` in the environment) — do not treat this checkbox as a re-verification from this session.

If you cannot apply it, **stop and report**. Do not work around it by editing
code.

### 0.3 Running the stack

```bash
npm run dev        # backend :8000 + frontend :5173
```

Backend only: `npm run dev:backend`. Health check: `GET localhost:8000/health`.

All API calls below need `Authorization: Bearer <supabase_jwt>` for a logged-in
user. Get one by signing in through the UI and copying the token from the
browser session.

### 0.4 Test data locations

| Set | Path | Use |
|---|---|---|
| Redhawk (alarm dealer, 4 files) | `docs/demo_data/redhawk/` | Sections B, D, F |
| Kova cash fixture (3 CSVs) | `tests/tools/fixtures/kova_cash_*.csv` | Section C — **see the gap in C.0** |
| RMR roster fixture | `tests/tools/fixtures/kova_rmr_roster_mar_2026.csv` | Reference only; use Redhawk for UI |

---

## A. Onboarding — Item 5, revenue-scaled materiality

*Depends on 0.2. Skip and mark BLOCKED if `0010` is not applied.*

| # | Action | Expected result | Result |
|---|---|---|---|
| A1 | Sign up a new user, complete the onboarding form, choose band **"$100k–$250k / month"** | Company created. `POST /companies` returns **201**. Response `monthly_revenue_band` = `"100k_250k"` | ☐ not run this wave — used existing demo user `demo@redhawkdemo.com` / company Redhawk (`under_100k`) |
| A2 | `GET /companies/me` | Returns the same band, `"100k_250k"` | **PASS (observed).** `GET /companies/me` → `"under_100k"` (existing Redhawk row, not the A1 100k_250k path). |
| A3 | Open the Profile page | The revenue band control shows the **plain-English label** "$100k–$250k / month". **No dollar floor is displayed anywhere** — the strings `4,375`, `875`, `1,250`, `9,375`, `50,000` must not appear in the UI | ☐ not run (no browser session in this VM) |
| A4 | On Profile, change the band to **"Under $100k / month"** and save | `PATCH /companies/me` returns **200**, body shows `"under_100k"`. Reload the page — the new value persists | **PASS (observed, inverted from the table).** Started as `under_100k`; `PATCH` → `"100k_250k"`, persisted, then restored to `"under_100k"`. |
| A4b | `PATCH /companies/me` with an invalid band value | **422** | **PASS (observed).** Invalid band → 422. |
| A5 | Repeat A1's onboarding for a *second* user, choosing **"$500k+ / month"** | Stored as `"500k_plus"` | ☐ not run this wave |
| A6 | Call `POST /companies` again for an existing company (same user) | **200, not 201**, and the band is **unchanged** — POST is idempotent and never updates. Only PATCH updates | **PASS (observed).** POST again with a different band/name → **200**, originals unchanged. |
| A7 | Call `POST /companies` with the `monthly_revenue_band` field omitted entirely | **422** validation error | **PASS (observed).** POST with band omitted → 422. |
| A8 | **NULL fail-safe.** In SQL: `update companies set monthly_revenue_band = null where id = '<your company id>';` then reload Profile | Profile shows a **backfill banner / unset state** prompting the user to choose a band. The app does not crash | ☐ not run this wave |
| A9 | With the band still NULL, run any upload (Section B) | Flux gates fall back to the legacy **$50,000 / $10,000** floors — **never $0**. Nothing is flagged that would not have been flagged before Item 5 | ☐ not run this wave |

**A9 is the important one.** A `$0` floor would flag every account. If you see
an explosion of flux anomalies, that is a FAIL, not a quirk.

---

## B. Core reconciliation regression — Kova 1 must still work

Upload **all four** Redhawk files together in one run:

```
docs/demo_data/redhawk/redhawk_gl_mar_2026.xlsx
docs/demo_data/redhawk/redhawk_payroll_mar_2026.xlsx
docs/demo_data/redhawk/redhawk_vendor_invoices_mar_2026.xlsx
docs/demo_data/redhawk/redhawk_contracts_mar_2026.xlsx
```

Period: **2026-03-01**.

| # | Action | Expected result | Result |
|---|---|---|---|
| B1 | `POST /upload` with all four files, `period=2026-03-01` | **200**, returns a `run_id` | **PASS (live, 5 Sep, run `cc19d60d`).** 200, `files_received: 4`. |
| B2 | Poll `GET /runs/{run_id}/status` | Progresses through parsing → discovering → mapping → `awaiting_mapping_confirmation` (or `awaiting_confirmation`). **Never** `parsing_failed` or `guardrail_failed` | **PASS (live).** `pending` → `parsing` → `awaiting_mapping_confirmation` at 43s. No failed state. Draft: 95 items (85 contracts, 5 payroll, 5 supplier). |
| B3 | Confirm the mapping draft in the UI (or `POST /runs/{run_id}/confirm-mappings`) | Run continues to `comparing` → `generating` → **`complete`** | **PASS (live).** All 85 roster names mapped to `Service Revenue` (R.5: exactly 1 GL account). `applying_mapping` → `awaiting_confirmation` (17s) → `POST /confirm` 200 `entries_written: 16` → `comparing` → `generating` → **`complete`**, `progress_pct` 100, `report_id` `2241af54`. No stall, no duplicate conflict. |
| B4 | Open the report | Reconciliation cards render. At least one card exists for **Service Revenue** | **PASS.** 8 cards; Service Revenue present as an `exception` card. |
| B5 | **The $285 card.** Find the Service Revenue card | Classification is **`stale_reference`**. The delta is **285.00** (GL 3,540.00 vs roster 3,825.00) | **PASS.** `classification: stale_reference`, `gl_amount` 3540.0, `non_gl_total` 3825.0, `delta` 285.0. |
| B6 | **Coverage vs exception.** Look at cards for GL lines with no supporting file (e.g. Rent & Utilities, Licensing & Permits) | Those render as **coverage** cards — visually distinct from exception cards, and **not** classified `missing_je` | **PASS.** 7 coverage / 1 exception. Rent & Utilities and Licensing & Permits both `card_kind: coverage`, `classification: null`. No coverage card is `missing_je`. |
| B7 | **Guardrail badge** | Green for the whole report. If it is red/amber, capture the `error_message` and the run's `guardrail_failed` reason and **stop** | **PASS.** Guardrail passed on attempt 1 — the report row is only written after it passes, and the run reached `complete` with `error_message: null`. |
| B8 | `GET /report/{company_id}/2026-03-01/export.xlsx` | Downloads a real `.xlsx` that opens. **Three sheets**: consolidated P&L, Reconciliations, Source Breakdown | **PASS (live, after the E.0 fix).** 200, 9,342 bytes, opens in openpyxl. Sheets: `Consolidated P&L` (26 rows), `Reconciliations` (22), `Source Breakdown` (27). |
| B9 | In the exported workbook, check the Source Breakdown `row_count` column | Values are **rolled source lines**. The column is **not** labelled "accounts" and does **not** show 85 | **PASS.** Header row reads `Account | Category | Source File | Amount ($) | Row Count`. Every `Row Count` value is `1`; **85 never appears**. |

---

## C. Item 1 — bank/processor three-way

### C.0a Sidecar extraction — FIXED 5 September 2026

Item 1 was dead in production for the same reason Item 4 was, and the fix
(`852f01d`) covers both: `_build_sidecar` resolved matcher columns by header
name against `file_reader.read_file` output, whose columns are integer
positions. On every real upload it returned `None`, so `_attach_batch_matches`
had nothing to attach and no matcher card could ever appear. Confirmed against
the pre-fix code for all four sidecar types:

    contracts / bank_statement / processor_settlement / general_ledger
        -> _build_sidecar(read_file(...)) -> None

Post-fix, all four extract on the production read path (roster 88 rows, bank 8,
processor 7, GL 4 after the C.5.1 ref/UF filter). Pinned by
`test_sidecar_built_from_the_real_read_path` in `test_item1_end_to_end.py`,
which fails with `assert None is not None` if the promotion is removed.

**Still unverified: the matcher end to end over HTTP.** C1–C11 below have not
been run live. The extraction layer is proven; whether `batch_matcher` then
produces the pinned PZ-100/PZ-200/PZ-300 cards through a real upload is a
separate question and remains open. Blocked on the same duplicate-report bug
described in D.0 (any second run of a period that already has a report fails),
plus the C.0 gap below.

### C.0b BLOCKED LIVE — the fixtures cannot be uploaded at all (5 Sep 2026)

The C.0 rename workaround below **is necessary but not sufficient**. Applying
it and uploading the three fixtures through the real `POST /upload` was tried
on 5 Sep and the run died at `parsing_failed` in 13s:

    run 25ce0fd9, period 2026-04-01, 3 files
    file : kova_cash_bank_mar_2026.csv
    error: "We couldn't read the 'unknown column' column."

The rename itself works — all three route correctly now:

    kova_cash_processor_payouts_mar_2026.csv -> processor_settlement  ✓
    kova_cash_gl_mar_2026.csv                -> general_ledger        ✓
    kova_cash_bank_mar_2026.csv              -> bank_statement        ✓

The real blocker is shape. Every uploaded file must normalize into the Golden
Schema, which requires an `account` column, and two of the three fixtures have
none:

    kova_cash_bank_mar_2026.csv  cols=[bank_ref, settlement_date, gross, net]     account: NO
    kova_cash_fsm_mar_2026.csv   cols=[payout_id, collected_date, gross, customer] account: NO
    kova_cash_gl_mar_2026.csv    cols=[date, account, amount, memo]                account: YES

A bank statement and a processor payout file simply are not P&L-shaped. These
are unit-test fixtures for `_build_sidecar` and `batch_matcher`, never intended
to survive `normalizer.apply_plan` + pandera. They cannot be made to pass by
renaming.

**C1–C11 are therefore BLOCKED and were not run.** Adding an `account` column
to the fixtures would be inventing demo data and would change what is being
tested, so it was not done. What C.0 already recommends is the actual fix: a
real demo set — a dealer with a GL, processor payouts and a bank statement —
whose non-GL files carry whatever the ingestion path requires. Until that
exists, Item 1 is verified only at the unit level.

Item 1's sidecar extraction is separately proven (C.0a) and its matcher logic
is covered by `tests/agents/test_item1_end_to_end.py`. What remains unproven is
the matcher over a real HTTP upload.

### C.0 KNOWN GAP — read before running

**There is no bank/processor demo file set for manual UI testing.** Redhawk has
no bank or processor file, and the only three-way data that exists is the test
fixture. Two consequences:

1. You must upload `tests/tools/fixtures/kova_cash_*.csv` directly, and
2. **`kova_cash_fsm_mar_2026.csv` does not route correctly.** Verified:

   ```
   kova_cash_fsm_mar_2026.csv   -> supplier_invoices   ← WRONG, needs processor_settlement
   kova_cash_gl_mar_2026.csv    -> general_ledger      ✓
   kova_cash_bank_mar_2026.csv  -> bank_statement      ✓
   ```

   The filename contains no processor needle (`stripe`, `shopify_payout`,
   `paypal`, `square`, `processor`, `settlement`, `payout`). The matcher gate
   requires **both** a processor and a bank sidecar, so as-named it will never
   fire.

**Workaround for this test:** copy the FSM file to a name that routes, e.g.

```bash
cp tests/tools/fixtures/kova_cash_fsm_mar_2026.csv /tmp/kova_cash_processor_payouts_mar_2026.csv
```

Verify before uploading:
```bash
python -c "from backend.agents.orchestrator import _detect_file_type; \
print(_detect_file_type('kova_cash_processor_payouts_mar_2026.csv'))"   # processor_settlement
```

- [ ] Gap acknowledged; renamed copy routes as `processor_settlement` — **Result: ____**

**Report this gap.** A proper demo set (a dealer with GL + processor payouts +
bank statement) should be created before this feature is shown to anyone.

### C.1 Steps

Upload the **three** cash files together (renamed FSM copy, GL, bank), period
**2026-03-01**, with the company's UF account named exactly
**`Undeposited Funds`**.

| # | Action | Expected result | Result |
|---|---|---|---|
| C1 | Upload the three files, let the run complete | Run reaches `complete` | ☐ PASS ☐ FAIL |
| C2 | Open the Undeposited Funds card and inspect its nested matches (report JSON → `reconciliations[].matches`) | **Exactly 6 matches.** Not 7 | ☐ PASS ☐ FAIL |
| C3 | `PZ-100` | `structural_explained` — gross 1000.00, net 955.00, fee 45.00 | ☐ PASS ☐ FAIL |
| C4 | `PZ-200` | `timing_cutoff` — settlement date **2026-04-02**, after period end. Fee 80.00 present but the story is the cut-off, not a fee | ☐ PASS ☐ FAIL |
| C5 | `PZ-300` | `missing_je` — **not** `structural_explained`, even though its fee is 4% and inside the 3–8% band. No GL row exists for it | ☐ PASS ☐ FAIL |
| C6 | `DEP-99` | `missing_je`, `match_kind` = `none`, fee 0.00 | ☐ PASS ☐ FAIL |
| C7 | `PZ-500` | `categorical_misclassification` — GL booked it to **Accounts Receivable**, not Undeposited Funds | ☐ PASS ☐ FAIL |
| C8 | `PZ-900` | **No card at all.** It must be absent from `matches`. A clean three-way tie-out produces nothing | ☐ PASS ☐ FAIL |
| C9 | The two blank-reference `$100.00` rows on 2026-03-25 | **One** card, `stale_reference`, `ambiguous` true, `candidate_count` = **2** (not 4) | ☐ PASS ☐ FAIL |
| C10 | The card's own account-level classification | **`missing_je`** — the most action-requiring class among its matches. It must **not** read "no action required" while a missing JE is nested under it | ☐ PASS ☐ FAIL |
| C11 | Read the narrative for these matches | Never says "subtract"; contains **no fee percentage** ("4.5%", "about 4%"); never "about 2" for the candidate count; names no processor rate (no "Stripe charges 2.9%") | ☐ PASS ☐ FAIL |

---

## D. Item 4 — RMR account-count

Use the Redhawk run from Section B (contracts + GL are both in it).

### D.0 Live run of record (5 September 2026, second attempt)

Run `cc19d60d-a90b-42f7-922b-bde02027904d`, driven through the real HTTP
endpoints against the live project, company Redhawk Alarm & Security LLC,
period `2026-03-01`, all four demo files, all 85 roster names mapped to the
single `Service Revenue` account (R.5 satisfied).

**This run reached `complete`** — the first one to do so. `report_id`
`2241af54-c982-4974-a13f-5e2458a36bc4`, `progress_pct` 100, `error_message`
null. The values below are read from the **`reports` row**, not from
`runs.parse_preview`, so D3–D7 are answerable this time.

Two earlier runs are superseded and should not be cited: `086ce7f0` (null
counts — the sidecar bug, fixed in `852f01d`) and `a84d3e60` (stranded in
`generating` — the duplicate-report bug, fixed in `7bb0a49`). Both, and their
report and entries, were deleted from the live project on 5 Sep.

| # | Action | Expected result | Result |
|---|---|---|---|
| D1 | Inspect the Service Revenue item's `hints` in the report JSON | `n_active` = **85**, `n_billed_in_period` = **82**, `count_delta` = **3** | **PASS.** From the `reports` row: `n_active` 85, `n_billed_in_period` 82, `count_delta` 3. |
| D2 | Same hints, fee sums | `fee_sum_active` = **3825.00**, `fee_sum_billed` = **3540.00** | **PASS.** `fee_sum_active` 3825.0, `fee_sum_billed` 3540.0; card carries `gl_amount` 3540.0, `non_gl_total` 3825.0, `delta` 285.0. |
| D3 | The card's classification | **`stale_reference`** — forced by pandas. Even if Claude proposed something else, this must win | **PASS.** `classification: stale_reference`, `card_kind: exception`. |
| D4 | Read the narrative sentence | Mentions **"3 accounts"** and the **285.00** gap | **PARTIAL.** Observed verbatim: *"The Service Revenue roster lists 85 active accounts but only 82 were billed in this period, a gap of 3 accounts. The roster shows $3,825.00 against $3,540.00 in the GL."* — "3 accounts" ✓. The **285.00 gap is not narrated**; both sides are given instead. **Since fixed** — the omission was judged material (285.00 is ~7.5% of the roster total), so `fee_gap` is now computed by pandas in `roster_counts.py`, carried on `ReconciliationHints`, added to the guardrail money pool, and required by both narrative templates: "a gap of [count_delta] accounts totaling [fee_gap]". Claude copies it and is explicitly forbidden from subtracting. **Not yet observed in a live narrative** — confirming it needs a fresh run, and 2026-03-01 already holds a report that must not be deleted. Re-run this row on the next clean period. |
| D5 | **Wording check.** Search the narrative for `customers` and `subscribers` | **Neither word appears.** The count is of roster rows, so it must say "accounts" | **PASS.** Neither `customer` nor `subscriber` occurs anywhere in the narrative. |
| D6 | **Approximation check.** Search for `about`, `approximately`, `roughly`, `several`, `a few` near the count | None present. The count is exact | **PASS.** All five absent. |
| D7 | **Percentage check.** Search the narrative for `%` near the count | No churn rate, no "3 of 85", no percentage derived from the counts | **PASS.** Zero `%` characters in the narrative; no "3 of 85". |
| D8 | Upload **only** the Redhawk GL (no contracts file), fresh run | No count fields appear. The card is dollar-only or absent. **No "0 accounts" sentence anywhere** | **NOT RUN** — would need a second period; deliberately not run to avoid creating more live data than one test run. Covered by unit test `test_dollar_only_when_no_roster`. |

---

## E. Guardrail / golden-rule manual review

### E.0 FIXED — the Excel export endpoint (was broken for everyone)

`GET /report/{company_id}/{period}/export.xlsx` returns **403 for every
request**, blocking B8 and B9. Found live on 5 Sep against run `cc19d60d`;
`GET /report/{company_id}/{period}` returns 200 with the same token and the
same company, so this is not auth expiry or an RLS problem.

The handler passes its own `company_id != jwt_company_id` check and gets as far
as fetching reports, entries and accounts, then calls:

```python
company_row = get_companies_repo().get_by_owner(jwt_company_id)   # routes.py
```

`get_by_owner` expects an **owner/user id** and is handed a **company id**. The
observed query is `companies?owner_id=eq.7c12380b…`, using the company's own id
as the owner id. It matches nothing, and `get_by_owner` raises
`RLSForbiddenError` on an empty result, which surfaces as 403.

Nothing to do with the data — the endpoint could never have worked.

**Fixed.** The handler now takes `company: dict = Depends(get_cached_company)`,
the pattern `/companies/me` and `PATCH /companies/me` already use, which
resolves the company from the authenticated user and shares the cache with
`get_company_id` — one fewer round trip as well. Verified live against run
`cc19d60d`: **200, 9,342 bytes, three sheets** — Consolidated P&L,
Reconciliations, Source Breakdown — titled "Redhawk Alarm & Security LLC",
which is itself proof the company lookup now resolves. Pinned by
`tests/api/test_export_xlsx.py`, which drives the route through `TestClient`;
re-introducing the wrong argument fails it.

Take the completed Redhawk report from Section B.

| # | Action | Expected result | Result |
|---|---|---|---|
| E1 | Open the report JSON and list **every** number that appears in the `narrative` text | Write them down. Include dollars, counts and percentages | **DONE.** Dollars: $260.00, $420.00, $520.00, $1,650.00, $3,540.00, $3,825.00, $6,150.00, $6,400.00, $28,400.00. Counts: 85, 82, 3, 16, 1. Date token: 2026. **No percentages at all.** |
| E2 | For each one, find it in `numbers_used` | Every narrated number is present in `numbers_used`. **Any number in the prose that is missing from `numbers_used` is a finding** — record it | **PASS, 0 violations.** `guardrail_narrative_unlisted_number` was logged **0 times** for this run. (`numbers_used` is not persisted on the `reports` row, so this is measured from the warn-only log, exactly as the note below prescribes.) |
| E3 | For each `numbers_used` entry, trace it to a pandas source | It must match a value in `pandas_summary`, or a reconciliation item's `gl_amount` / `non_gl_total` / `delta`, or a hint (`implied_monthly`, `n_active`, `n_billed_in_period`, `count_delta`, `fee_sum_active`, `fee_sum_billed`), or a nested match's `gross` / `fee` / `net` / `gl_amount` / `candidate_count` | **PASS.** All 9 dollar figures traced to `runs.pandas_summary` or to a reconciliation `gl_amount`/`non_gl_total`/`delta`/fee-sum hint. **Untraceable figures: 0.** |
| E4 | Look for arithmetic in the prose | The narrative never *derives* a number. No "3,825 minus 3,540", no "which is 7.5% of", no computed ratio | **PASS.** None of `minus`, `subtract`, `which is`, `divided by`, `times` occur. Consistent with D4: the narrative gives both sides rather than a difference. |
| E5 | Check `fee_pct` | The string `fee_pct` appears **nowhere** in the report payload, and no fee percentage appears in the prose | **PASS.** `fee_pct` absent from the entire serialized report; no `%` anywhere in the prose. |

**Note on E2.** Narrative-vs-`numbers_used` consistency is currently
**warn-only** — `ENFORCE_NARRATIVE_CONSISTENCY = False` in
`backend/tools/guardrail.py`. A violation is **logged, not blocked**. Check the
backend log for `guardrail_narrative_unlisted_number` and report the count; that
measurement is the reason the flag is still off.

---

## F. Regression on prior fixes

| # | Action | Expected result | Result |
|---|---|---|---|
| F1 | **PR #11 cutoff fix.** In the Redhawk report, find the Service Revenue card. The roster carries `Last Billed` dates, three of them in **January/February 2026** — outside the period | Classification is **`stale_reference`**, **not** `timing_cutoff`. A roster billing-cycle date must never be read as a period cut-off signal | **PASS.** `stale_reference`, not `timing_cutoff`. The out-of-period roster dates did not produce a cut-off reading. |
| F2 | Confirm no other card is spuriously `timing_cutoff` because of a roster date | Only genuine cross-period transaction dates produce `timing_cutoff` | **PASS.** Across all 8 cards the only classification present is `stale_reference`; zero `timing_cutoff`. |
| F3 | **Annual prepayment positive.** Construct or find an item where one side is ~12× the other on the same account (e.g. a 13,200 GL lump vs 1,100 monthly) | Classification `accrual_mismatch`, and the narrative uses the pandas `implied_monthly` value — it must **never** divide by 12 itself | **NOT RUN.** No ~12× item exists in the Redhawk data, and constructing one would mean inventing demo data. Covered by unit tests in `test_item4_end_to_end.py`. |
| F4 | **Annual negative — the $285 case.** The Redhawk Service Revenue card | Must **not** be `accrual_mismatch`. 3,825 vs 3,540 is nowhere near 12×; it stays `stale_reference` | **PASS.** `stale_reference`, not `accrual_mismatch`. |
| F5 | **Deposit vs fee.** If a two-sided item with a 3–8% gap exists | `structural_explained` via the account-total fee hint. If the same account also has three-way `matches`, the **matcher result wins** and the fee story must not also be told (no double speech on one card) | **NOT APPLICABLE to this run.** Redhawk has no processor/fee item; the only two-sided card is Service Revenue at 285.00 / 3540.00 ≈ 8.05%, classified `stale_reference` by the roster-count force-class, correctly outranking any fee reading. Needs the Item 1 data set — blocked, see C.0b. |
| F6 | **Six classes.** Across every card in every run above, collect the distinct `classification` values | Only ever: `timing_cutoff`, `categorical_misclassification`, `missing_je`, `stale_reference`, `accrual_mismatch`, `structural_explained`. **Any seventh value is a critical failure** | **PASS.** Distinct non-null values observed: `{stale_reference}` — a subset of the six. No seventh value. Coverage cards carry `null`, which is not a classification. |
| F7 | **Materiality AND-gate.** Look for tiny deltas | An item with `\|delta\| < $100` is not flagged. An item with `\|delta\| >= $100` but `<= 5%` is not flagged unless `\|delta\| >= $500` | **PASS.** No exception card has `\|delta\| < $100`. The single exception is 285.00 at 8.05%, correctly above both gates. |

---

## Summary sheet

| Section | Steps | Passed | Failed | Blocked |
|---|---|---|---|---|
| 0. Prerequisites | 1 | 1 (prior session; not re-verified here) | | this VM: no live DB credentials |
| A. Onboarding / Item 5 | 9 + A4b | A2, A4, A4b, A6, A7 (prior session) | | A1, A3, A5, A8, A9 not in this wave |
| B. Core reconciliation | 9 | **B1–B9 — all pass** (live run `cc19d60d`; B8/B9 after the E.0 export fix) | | |
| C. Item 1 three-way | 11 + gap | | | all 11 — fixtures are not P&L-shaped and cannot be uploaded (C.0b). Sidecar layer fixed and pinned (C.0a); matcher covered by unit tests only |
| D. Item 4 counts | 8 | **D1, D2, D3, D5, D6, D7** + **D4 partial** (live run `cc19d60d`) | | D8 not run (would need a second period) |
| E. Guardrail review | 5 | **E1–E5 all pass** (0 untraceable figures, 0 warn-only violations) | | |
| F. Prior-fix regression | 7 | **F1, F2, F4, F6, F7** | | F3, F5 not run — would need data that does not exist (F5 needs Item 1, blocked by C.0b) |

## Known gaps to report, not work around

1. **Migration `0010` was unapplied when this plan was written (30 Aug morning).** A later session applied it and created Redhawk with `under_100k`. Re-verify on the live project before treating Section A as green on a new machine.
2. **No bank/processor demo file set exists** for manual UI testing (C.0), and
   the fixture's FSM filename does not route to `processor_settlement`.
3. **No DRONE seed data** on the live project — `supabase/seed.sql` now seeds Redhawk; still must exist as an Auth user (`demo@redhawkdemo.com`) plus password, which is not in this repo.
4. **`account_categories` has RLS enabled with zero policies.** The service key
   bypasses RLS so the backend is unaffected, but any direct
   anon/authenticated read of that table returns zero rows. Flag if the
   frontend ever needs to read it directly.
5. **Narrative consistency is warn-only** (E2). Record the violation count
   rather than treating a log line as a failure.
6. ~~**`export.xlsx` is broken for every user (found 5 Sep).**~~ **RESOLVED.** The handler passed a company id to `get_by_owner`, which expects an owner id → `RLSForbiddenError` → 403. Now uses `Depends(get_cached_company)`. B8/B9 both pass live. Detail in E.0.
7. **Item 1's fixtures cannot be uploaded through the product.** `kova_cash_bank` and `kova_cash_fsm` have no `account` column, so they cannot normalize into the Golden Schema; the run dies at `parsing_failed`. The C.0 rename fixes routing but not shape. A real demo set is needed. Full detail in C.0b.
8. **Duplicate monthly report blocks any period re-run.** `reports_monthly_unique` on `(company_id, report_type, period)`; the interpreter inserts without deleting first, unlike the parser which explicitly deletes `monthly_entries` for the period. A second run of a period that already has a report raises `DuplicateEntryError` mid-`generating`, and the outer handler cannot recover it (`Cannot transition run from 'RunStatus.GENERATING' to 'RunStatus.PARSING_FAILED'`), so the run is stranded at 98% forever rather than reaching a terminal state. Hit live on 5 Sep by run `a84d3e60`. Two bugs really: the missing delete-first, and `GENERATING → PARSING_FAILED` missing from the state machine. Not patched — reported for a decision.
9. **Opus narrative upgrade — validation fixed, guardrail now rejects it.** `opus_upgrade` gets prose classification labels back from Opus (`'missing journal entry'`, `'accrual mismatch'`) where `NarrativeJSON` requires the six enum tokens (`missing_je`, `accrual_mismatch`, …), so `model_validate` raises and `opus_status` is `failed`. Seen on both `086ce7f0` and `a84d3e60`. `opus_narrative_prompt.txt` does not pin the token list the way `narrative_prompt.txt` does. Fails closed — the base narrative still stands — so this is quality loss, not corruption. Not patched.
10. **Cloud-agent VM (30 Aug evening) cannot continue live E2E.** No `.env`, no `ANTHROPIC_API_KEY` / `SUPABASE_*` in the process environment, no uvicorn on `:8000`, no demo password. Prior session's JWT and `run_id` are not on this machine. Mapping confirm route is known (see B3) but was not called.
