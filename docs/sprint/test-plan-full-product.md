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
| B1 | `POST /upload` with all four files, `period=2026-03-01` | **200**, returns a `run_id` | **PASS (prior session).** Four Redhawk files uploaded; run created. **This VM cannot continue that run** — no backend, no JWT, no run_id in this environment. |
| B2 | Poll `GET /runs/{run_id}/status` | Progresses through parsing → discovering → mapping → `awaiting_mapping_confirmation` (or `awaiting_confirmation`). **Never** `parsing_failed` or `guardrail_failed` | **PASS (prior session).** Status reached `awaiting_mapping_confirmation`. 81/85 contract roster names low-confidence/unmapped — expected for arbitrary customer names. |
| B3 | Confirm the mapping draft in the UI (or `POST /runs/{run_id}/mapping/confirm`) | Run continues to `comparing` → `generating` → **`complete`** | **BLOCKED (this session).** Correct route is `POST /runs/{run_id}/confirm-mappings` with body `{ "decisions": { "<source_pattern>": "<gl_account_name>" } }` (`ConfirmMappingsRequest` in `backend/api/routes.py`). Pool must contain the GL names. **Not called** — this VM has no `.env`, no uvicorn on :8000, no demo password, so no JWT. |
| B4 | Open the report | Reconciliation cards render. At least one card exists for **Service Revenue** | ☐ PASS ☐ FAIL |
| B5 | **The $285 card.** Find the Service Revenue card | Classification is **`stale_reference`**. The delta is **285.00** (GL 3,540.00 vs roster 3,825.00) | ☐ PASS ☐ FAIL |
| B6 | **Coverage vs exception.** Look at cards for GL lines with no supporting file (e.g. Rent & Utilities, Licensing & Permits) | Those render as **coverage** cards — visually distinct from exception cards, and **not** classified `missing_je` | ☐ PASS ☐ FAIL |
| B7 | **Guardrail badge** | Green for the whole report. If it is red/amber, capture the `error_message` and the run's `guardrail_failed` reason and **stop** | ☐ PASS ☐ FAIL |
| B8 | `GET /report/{company_id}/2026-03-01/export.xlsx` | Downloads a real `.xlsx` that opens. **Three sheets**: consolidated P&L, Reconciliations, Source Breakdown | ☐ PASS ☐ FAIL |
| B9 | In the exported workbook, check the Source Breakdown `row_count` column | Values are **rolled source lines**. The column is **not** labelled "accounts" and does **not** show 85 | ☐ PASS ☐ FAIL |

---

## C. Item 1 — bank/processor three-way

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

| # | Action | Expected result | Result |
|---|---|---|---|
| D1 | Inspect the Service Revenue item's `hints` in the report JSON | `n_active` = **85**, `n_billed_in_period` = **82**, `count_delta` = **3** | ☐ PASS ☐ FAIL |
| D2 | Same hints, fee sums | `fee_sum_active` = **3825.00**, `fee_sum_billed` = **3540.00** | ☐ PASS ☐ FAIL |
| D3 | The card's classification | **`stale_reference`** — forced by pandas. Even if Claude proposed something else, this must win | ☐ PASS ☐ FAIL |
| D4 | Read the narrative sentence | Mentions **"3 accounts"** and the **285.00** gap | ☐ PASS ☐ FAIL |
| D5 | **Wording check.** Search the narrative for `customers` and `subscribers` | **Neither word appears.** The count is of roster rows, so it must say "accounts" | ☐ PASS ☐ FAIL |
| D6 | **Approximation check.** Search for `about`, `approximately`, `roughly`, `several`, `a few` near the count | None present. The count is exact | ☐ PASS ☐ FAIL |
| D7 | **Percentage check.** Search the narrative for `%` near the count | No churn rate, no "3 of 85", no percentage derived from the counts | ☐ PASS ☐ FAIL |
| D8 | Upload **only** the Redhawk GL (no contracts file), fresh run | No count fields appear. The card is dollar-only or absent. **No "0 accounts" sentence anywhere** | ☐ PASS ☐ FAIL |

---

## E. Guardrail / golden-rule manual review

Take the completed Redhawk report from Section B.

| # | Action | Expected result | Result |
|---|---|---|---|
| E1 | Open the report JSON and list **every** number that appears in the `narrative` text | Write them down. Include dollars, counts and percentages | ☐ done |
| E2 | For each one, find it in `numbers_used` | Every narrated number is present in `numbers_used`. **Any number in the prose that is missing from `numbers_used` is a finding** — record it | ☐ PASS ☐ FAIL |
| E3 | For each `numbers_used` entry, trace it to a pandas source | It must match a value in `pandas_summary`, or a reconciliation item's `gl_amount` / `non_gl_total` / `delta`, or a hint (`implied_monthly`, `n_active`, `n_billed_in_period`, `count_delta`, `fee_sum_active`, `fee_sum_billed`), or a nested match's `gross` / `fee` / `net` / `gl_amount` / `candidate_count` | ☐ PASS ☐ FAIL |
| E4 | Look for arithmetic in the prose | The narrative never *derives* a number. No "3,825 minus 3,540", no "which is 7.5% of", no computed ratio | ☐ PASS ☐ FAIL |
| E5 | Check `fee_pct` | The string `fee_pct` appears **nowhere** in the report payload, and no fee percentage appears in the prose | ☐ PASS ☐ FAIL |

**Note on E2.** Narrative-vs-`numbers_used` consistency is currently
**warn-only** — `ENFORCE_NARRATIVE_CONSISTENCY = False` in
`backend/tools/guardrail.py`. A violation is **logged, not blocked**. Check the
backend log for `guardrail_narrative_unlisted_number` and report the count; that
measurement is the reason the flag is still off.

---

## F. Regression on prior fixes

| # | Action | Expected result | Result |
|---|---|---|---|
| F1 | **PR #11 cutoff fix.** In the Redhawk report, find the Service Revenue card. The roster carries `Last Billed` dates, three of them in **January/February 2026** — outside the period | Classification is **`stale_reference`**, **not** `timing_cutoff`. A roster billing-cycle date must never be read as a period cut-off signal | ☐ PASS ☐ FAIL |
| F2 | Confirm no other card is spuriously `timing_cutoff` because of a roster date | Only genuine cross-period transaction dates produce `timing_cutoff` | ☐ PASS ☐ FAIL |
| F3 | **Annual prepayment positive.** Construct or find an item where one side is ~12× the other on the same account (e.g. a 13,200 GL lump vs 1,100 monthly) | Classification `accrual_mismatch`, and the narrative uses the pandas `implied_monthly` value — it must **never** divide by 12 itself | ☐ PASS ☐ FAIL |
| F4 | **Annual negative — the $285 case.** The Redhawk Service Revenue card | Must **not** be `accrual_mismatch`. 3,825 vs 3,540 is nowhere near 12×; it stays `stale_reference` | ☐ PASS ☐ FAIL |
| F5 | **Deposit vs fee.** If a two-sided item with a 3–8% gap exists | `structural_explained` via the account-total fee hint. If the same account also has three-way `matches`, the **matcher result wins** and the fee story must not also be told (no double speech on one card) | ☐ PASS ☐ FAIL |
| F6 | **Six classes.** Across every card in every run above, collect the distinct `classification` values | Only ever: `timing_cutoff`, `categorical_misclassification`, `missing_je`, `stale_reference`, `accrual_mismatch`, `structural_explained`. **Any seventh value is a critical failure** | ☐ PASS ☐ FAIL |
| F7 | **Materiality AND-gate.** Look for tiny deltas | An item with `\|delta\| < $100` is not flagged. An item with `\|delta\| >= $100` but `<= 5%` is not flagged unless `\|delta\| >= $500` | ☐ PASS ☐ FAIL |

---

## Summary sheet

| Section | Steps | Passed | Failed | Blocked |
|---|---|---|---|---|
| 0. Prerequisites | 1 | 1 (prior session; not re-verified here) | | this VM: no live DB credentials |
| A. Onboarding / Item 5 | 9 + A4b | A2, A4, A4b, A6, A7 (prior session) | | A1, A3, A5, A8, A9 not in this wave |
| B. Core reconciliation | 9 | B1, B2 (prior session, run waiting on mapping) | | B3–B9 this VM (no API) |
| C. Item 1 three-way | 11 + gap | | | all — no API |
| D. Item 4 counts | 8 | | | all — no API |
| E. Guardrail review | 5 | | | all — no report payload |
| F. Prior-fix regression | 7 | | | all — no report payload |

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
6. **Cloud-agent VM (30 Aug evening) cannot continue live E2E.** No `.env`, no `ANTHROPIC_API_KEY` / `SUPABASE_*` in the process environment, no uvicorn on `:8000`, no demo password. Prior session's JWT and `run_id` are not on this machine. Mapping confirm route is known (see B3) but was not called.
