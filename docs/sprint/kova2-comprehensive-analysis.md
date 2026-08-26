# Kova 2 — comprehensive analysis (six items)

*Planning only. No implementation until the single checkpoint at the end is approved.*  
*Date: 26 August 2026.*  
*Parent: [field-service-close-triage.md](field-service-close-triage.md) Bucket 2.*  
*Code read on `cursor/annual-prepayment-hint-d72a` (Kova 1 recon stack: AND-gate, coverage, deposit/fee, cutoff allowlist, annual 12×). PAYROLL tag lives on PR #5 (`cursor/payroll-pattern-match-d72a`), still off this stack and off `origin/main`.*  
*GitHub `main` has not absorbed the Kova 1 PRs as of this writing. This document treats those PRs as the current product.*

This is **one analysis**. Not an implementation prompt. Not a seventh classification. Not a deferred-revenue waterfall. Not A2X.

---

## Direct ranking (read this first)

Do **not** treat the six items as equal.

| Rank | Item | Why this place |
|------|------|----------------|
| **1** | Revenue-scaled materiality (onboarding) | Only item that stays inside today’s engine. Unblocks ICP flux. PAYROLL tag (PR #5) is dead until thresholds actually fire at shop scale. Independent of bank. |
| **2** | Bank / processor three-way (MVP, not A2X) | The research wedge. Needs a **new matcher** before `groupby`. Do after #1 so the close story is “cash residue + honest flux,” not “cash matcher on a $50k flux gate.” |
| **3** | RMR account-count vs GL | Alarm-useful; smaller than bank; still a **grain** change (counts before roll-up). Do not mix with waterfall. |
| **4** | Truck-stock / van inventory | Research says most ICP shops expense parts. Building it commits the product to an inventory engine. Later, maybe never. |
| **5** | Central-station wholesale accrual | Alarm-only vendor schedule. Third-vertical / add-on. Not the next slice. |
| **6** | WIP / professional services | Second vertical. Helix hours file is not a %complete engine. Scope note only. |

Kova 1 JSONB hint + force-class + isolated fixture is the right pattern for **recon speech acts on account totals**. It is **not** enough for items 1 (bank matcher), 2 (inventory rollforward), 4 (count grain), or 6 (job-level WIP). Item 5 (flux scale) is not a hint at all. Item 3 *might* look like `accrual_mismatch` if someone uploads a one-line vendor total — that is a fake, not the item.

---

## Scope lock

- Six `ReconciliationClassification` values only. New engines emit **existing** classes (or coverage), not a seventh.
- Golden rule: pandas matches, counts, ratios, floors. Claude narrates. Guardrail still checks `numbers_used` only — so any new figure (fee dollars, implied monthly, account **count**, scaled floor) must already sit on the item.
- Highest migration on disk: `0009_add_report_type_and_quarterly.sql`. Next write is `0010_{snake_case}.sql`. Flux scale and bank attestation **cannot** share one file (triage already reserved `0010` scale, `0011` attestation).
- Do not ingest ASC 606 SSP, ServiceTitan double-recognition at row grain, or a deferred-revenue rollforward in any of these six.

---

## Kova 1 pattern (what “follow the pattern” means)

Deposit/fee (PR #9) and annual 12× (PR #13):

1. Pandas bool on `ReconciliationHints` (JSONB on `reports.reconciliations` — **no migration**).
2. Interpreter **forces** the class over Claude.
3. Isolated `ReconciliationItem` fixture; Sentinel/Vandelay often cannot demonstrate the happy path.
4. Prompt template copies pandas numbers; never divides.

Use that pattern only when the signal is an **account-total ratio or flag**. Stop using it when the work is matching identities, preserving extra columns, or rolling a balance-sheet quantity.

---

## 1. Bank / processor three-way (the wedge)

### What the chain is

Field-service close cash is not “GL cash = bank.” It is three books:

1. **FSM / job software** — “this job was collected” (gross). Often Jobber / ServiceTitan / Housecall Pro export, or a card-batch CSV.
2. **QuickBooks Undeposited Funds (or merchant clearing)** — money recognized, not yet in the bank.
3. **Bank or processor settlement** — net deposit after fees, refunds, chargebacks. Stripe/Shopify/PayPal payout, or a bank CSV.

Month-end residue: unbooked fees, batches that straddle cutoff, undeposited ≠ 0. Practitioners reconcile this **daily**; the product should explain the **residue**, not replace Bank Feed.

Kova 1 already covers one **account-total** slice: `is_processor_fee_gap` (`hint_computer.py::_is_processor_fee_gap`) when both sides exist, not a deposit, and `|delta_pct| ∈ [3%, 8%]`. Interpreter forces `structural_explained`. That is **not** three-way matching. It never sees a batch id, never checks that GL is Undeposited Funds, never ties a payout to a bank line. Sentinel Bank Charges $95 is GL-only and under the AND-gate — not this item.

### Does today’s `SourceFileType` extend?

`backend/domain/contracts.py::SourceFileType`:

```
general_ledger | payroll | supplier_invoices | contracts
```

Detection is **filename**, not content: `orchestrator.py::_FILE_TYPE_PATTERNS` / `_detect_file_type`. Unknown files **default to `supplier_invoices`**. A `bank_statement.csv` or `stripe_payouts.xlsx` is therefore a vendor file today. `consolidator.py::_is_gl_label` is a second, independent GL heuristic. Contracts have a third (`hint_computer.py::_is_contracts_roster_file`). Frontend payroll-only special case: `MappingReview.tsx`.

Adding `bank_statement` and/or `processor_settlement` is a **Pydantic literal + filename patterns + AccountMapper prompt rules**. That change **does not need a SQL migration** (`SourceFileType` lives in parse_preview JSONB, migration `0005`). It is **necessary but not sufficient**. Without new golden fields and a matcher, the new types still die in `groupby("account")`.

### Consolidator vs a batch matcher

Join grain today (`consolidator.py::consolidate`):

1. Parser already `groupby("account")` (`parser.py::parse_file_silently`) → one amount per account per file.
2. Consolidator keeps `account, category, amount, source_file`, fuzzy-canonicalizes names (`_build_canonical_map`, WRatio ≥ 90), rolls up, GL vs non-GL at **account/category**.
3. `_build_item` hard-codes `ReconciliationSource.row_count = 1`.

Golden schema (`contracts.py::GoldenField` / `GoldenSchemaRow`): `account, account_code, amount, date, parent_category, department, description`. `normalizer.py::apply_plan` **drops every other column**. `validator.py` pandera `strict=True` on those seven. Discovery sees 100 rows × 10 columns (`file_reader.py::read_raw_cells`).

What a matcher needs and **today drops**: `batch_id` / `payout_id` / bank reference, transaction count, settlement date as distinct from txn date, gross / fee / net components. `description` is not a join key. `monthly_entries` unique `(company_id, account_id, period)` (`0001` + `0007`) **cannot** store per-batch rows.

**Verdict:** JSONB hints cannot perform matching. A new **deterministic matcher** must run **before** account aggregation (new module, e.g. `backend/tools/batch_matcher.py` or `backend/agents/cash_matcher.py` — name is later). Output of that matcher can still be JSONB cards using the **existing six classes**:

| Matcher state | Class |
|---------------|--------|
| Gross vs net, fee explained | `structural_explained` |
| Payout dated after period_end | `timing_cutoff` |
| Processor batch not in GL | `missing_je` |
| Bank deposit not in GL / UF | `missing_je` |
| Posted to the wrong clearing account | `categorical_misclassification` |

Claude classifications are `dict[account → class]` (`NarrativeJSON.reconciliation_classifications`). Several batches on one Undeposited Funds line **cannot** be independently classified without a match/batch id on the item (or nested payload). That is a contracts change, still JSONB, still no seventh class.

Account-total fee-band (Kova 1) stays as a **fallback** when the user did not upload a settlement file.

### Schema / migration

| Change | Migration? |
|--------|------------|
| New `SourceFileType` values | **No** (Pydantic) |
| Matcher results on `reports.reconciliations` JSONB | **No** |
| Extra golden fields (`batch_id`, `gross`, `fee`, `net`) | **No SQL**; **yes** pandera / `GoldenField` / discovery prompt — this is the real schema of the *file*, not Postgres |
| Persist line-level matches for audit | **Yes**, later — new tables, **not** `monthly_entries`. Do not do this in v1. |
| Bank attestation checkbox (triage Bucket 1 leftover) | **`0011_add_bank_attestation.sql`** if persisted; display-only needs none. Do **not** reuse `0010`. |

v1 recommendation: ephemeral matcher from the three uploads; persist only classified cards in existing JSONB. No `0010` for this item.

### Demo data

| Set | Three-way? |
|-----|------------|
| Sentinel | **No.** Tracked: GL Mar + Feb only on this branch. Archive names supplier/payroll/contracts/install; **no bank, no processor.** Bank Charges $95 is GL-only. |
| Vandelay | **Two-sided processor, not three-way.** `vandelay_shopify_payouts_mar_2026.xlsx` + `vandelay_amazon_settlement_mar_2026.xlsx` vs GL. **No bank statement, no Undeposited Funds detail.** Filename `shopify_payouts` does not match current patterns → `supplier_invoices`. Useful as a **processor vs GL** fixture, not FSM→UF→bank. |
| DRONE | Single-file P&L. No. |
| Isolated fixture | **Required** for the matcher (three hand-crafted frames: processor batches, GL UF lines, bank deposits), same reason as deposit/fee. |

### Overbuild risk (keep the wedge small)

The research’s best differentiator is **processor-clearing exceptions on messy Excel**, not a bank-rec product. A2X / Bookkeep / Link My Books already post payouts into QBO. If implementation starts: coding every bank line, multi-currency, many-to-many splits, auto-JE, connectors — stop. That is a different company.

**MVP boundary (one processor, one UF account, one bank, one period):**

- Match **batch/reference id first**; exact net amount + date window only as fallback.
- Pandas computes gross, fee, net, unmatched counts. Claude does not subtract.
- Emit the five states in the table above. No “remaining 11 months.” No SSP.

### Affected files (when later built — do not apply now)

`contracts.py` (SourceFileType, GoldenField, ReconciliationItem identity), `orchestrator.py::_detect_file_type`, `account_mapper.py` + `account_mapping_prompt.txt`, `normalizer.py` / `validator.py`, **new matcher module**, `consolidator.py` (must **not** be the matcher), `hint_computer.py` (optional post-match hints), `interpreter.py` (force class; classify by match id not only account), `narrative_prompt.txt`, `FileUpload.tsx` / copy, tests + isolated fixture. Frontend cards can stay account-grouped if the payload nests batches.

### Size / risks / tests

- **Size:** **büyük**, **çok-PR** (not Kova 1). Suggested cut: PR-A types+golden fields+fixture; PR-B matcher+classes; PR-C prompt/UI copy. Do not ship A without B.
- **Depends on:** Kova 1 fee hint (already on this stack) so account-total fallback exists. Independent of flux `0010`. Independent of RMR counts.
- **Risk:** Default-to-supplier_invoices silently mis-labels bank files; consolidator would “tie out” payout totals to a COGS/sales line and tell a fee story without matching. Guardrail will not catch a wrong class.
- **Tests:** isolated three-file fixture; Vandelay payouts as **negative** (no bank → matcher does not pretend three-way); never claim Sentinel demonstrates this.

---

## 2. Truck stock / van inventory

### How it hits the GL at ICP scale

Sector research (`close-process-by-sector.md`): 5–40 person dealers **often do not count** van parts; they expense on purchase. The GAAP object is a **balance-sheet inventory asset** (or supplies) with a cycle-count rollforward:

`opening + receipts − consumption − count adjustments = GL inventory`

That is not a P&L file total. A “truck stock vs COGS” dollar tie-out would **impersonate** a recon and silently commit Month Proof to inventory.

Possible source files (none are a type today): cycle-count spreadsheet, FSM parts-used export, vendor receipts (already `supplier_invoices`), fuel card (expense, not stock). Vandelay `vandelay_inventory_purchases_mar_2026.xlsx` is **purchases**; filename contains `purchase` → `supplier_invoices`. That is AP vs COGS, which Kova 1 already classes as `missing_je` / `accrual_mismatch`. It is **not** a count.

### Fit to six classes + coverage

| Fake mapping | Why it is wrong |
|--------------|-----------------|
| GL-only Inventory / Parts → `coverage` | Honest if no count file; does not reconcile stock. |
| Purchases file vs COGS → existing supplier path | Right for **buy**, wrong for **on-hand**. |
| Count qty × cost vs GL → new engine | Needs opening, qty, location, SKU. `monthly_entries` one `actual_amount` per account/period **cannot** hold opening+receipts+count. |

JSONB hint on account totals cannot represent a quantity rollforward. Coverage/exception model stays P&L-shaped.

### Files / schema / size

- **Files (if ever):** new `SourceFileType` (`inventory_count` — Pydantic only), golden fields for qty/SKU, new rollforward helper (not consolidator), BS-capable store (new tables or a new JSONB schedule — **migration** if persisted). `account_categories` stays immutable; do not add INVENTORY as a GAAP category.
- **Schema now:** **do not migrate.** `0001 monthly_entries` unique key is the blocker.
- **Size:** **büyük / new engine**, **çok-PR**, later vertical (closer to manufacturing than field-service ICP).
- **Depends on:** nothing in this six. Must not block #1–#3.
- **Tests:** Vandelay purchases = **negative** (still supplier_invoices). True cycle-count = new fixture + qty math in pandas. Sentinel/DRONE: no.

**JSONB pattern?** **No.** Insufficient.

---

## 3. Central-station wholesale cost accrual (alarm-specific)

### What it is

Alarm dealers pay a **central station** (or radio network) a wholesale monitoring cost, often with a **minimum volume** and a per-account rate. Close wants: accrue the month’s wholesale COGS even if the vendor invoice arrives next month; flag if active RMR count × rate ≠ GL monitoring COGS.

There is **zero** backend mention of central station / wholesale monitoring (`DEFAULT_GL_CATEGORIES` is generic COGS). No source type analog. Inbox would be a vendor schedule (accounts, rate, minimum) plus the supplier invoice — closer to “named accrual” than to bank matching.

### Urgency vs third vertical

**Defer to third-vertical / alarm add-on. Not next.**

Reasons, in order:

1. ICP 5–40 shops that skip rollforwards also often book this invoice when it lands (`missing_je` / `accrual_mismatch` on today’s supplier file). The **miss** is real but the **engine** is a new schedule.
2. It needs **account counts** (item 4) or it double-counts work: rate × count is pandas, not Claude, but count grain is item 4’s blocker.
3. HVAC-in-the-same-wave does **not** have this vendor. Building it now narrows the first wave.
4. A fake “if COGS is big, accrue” hint would violate golden rule and invent wholesale.

If a dealer later inboxes a one-page “central station March bill vs roster count” Excel, a **named** `accrual_mismatch` with pandas `count × rate` (after item 4 exists) is the honest slice. Until then, supplier vs GL COGS is enough.

### Files / schema / size

- **Files:** none now. Later: contracts-like roster columns + supplier file; `hint_computer` named accrual; prompt template under **existing** `accrual_mismatch` (expense), not class 6.
- **Migration:** **No** for a hint. **Yes** only if we persist a vendor-rate table — do not.
- **Size:** **orta** after item 4 exists; **sadece not** until then. Not a Kova 1 mikro-fix pretending to be wholesale.
- **Depends on:** RMR **counts** (item 4) if the story is rate × accounts. Independent of bank matcher.
- **Tests:** no Sentinel/Vandelay/DRONE file. Isolated fixture only. Do not retag Sentinel Equipment COGS $1,700 (CableMax timing) as wholesale.

**JSONB pattern?** Only the **named accrual after counts exist**. The vendor minimum-volume schedule is **not** an account-total hint.

---

## 4. RMR account-count vs GL (alarm-specific)

### What it is (and is not)

**Is:** roster **headcount and rates** vs GL monitoring revenue. Typical misses: cancelled still “Active,” suspended still billed, missed rate increase. Adjacent to today’s `stale_reference` (Sentinel Service Revenue GL `$3,540` vs contracts `$3,825`, Δ `$285` — **dollar** stale list).

**Is not:** deferred-revenue **rollforward** (opening + billings − recognized = close). That remains Bucket 2 “sadece not” / later waterfall. Annual cash booked 100% to revenue is **already Kova 1** (`looks_like_annual_prepayment`, same-item 12×). Do not reopen that as count recon. ServiceTitan invoice+payment double recognition is **row identity after groupby** — still forbidden here.

### Why dollars are not enough

`stale_reference` prompt **talks** about customer count / rates (`narrative_prompt.txt`) but structured fields are dollars only. Parser `groupby("account")` then consolidator roll-up. `row_count` is hardcoded `1`. Normalizer drops Status, Monthly Fee as its own field, Customer ID. Guardrail supplementation (`interpreter.py::_run_with_guardrail`) adds `gl_amount`, `non_gl_total`, `delta`, source amounts — **not counts**. If Claude writes “3 cancelled customers,” that number is **invented** unless pandas emitted it.

Count-grain needs **before** account aggregation: customer key, status, monthly rate, billed flag. Then pandas: `active_count`, `billed_count`, `count_delta`, `rate_delta`, `implied_revenue = count × rate`. Prompt copies those. Class stays **`stale_reference`** (list out of date), not `missing_je`, not `accrual_mismatch`.

Cutoff allowlist (PR #11) already stopped `Last Billed` from stealing this card to `timing_cutoff`. Count work must **not** re-widen date scanning.

### Files / schema / size

- **Files:** `normalizer.py` / `GoldenField` (status/rate/count — or a **contracts-only sidecar** so P&L files stay seven columns), `parser.py` (do not group away identity on contracts files), `consolidator.py::_build_item` (stop hard-coding `row_count=1` for contracts), `hint_computer.py` (e.g. `roster_count_delta`), `contracts.py::ReconciliationHints`, `interpreter.py` force `stale_reference` when count hint is on, `narrative_prompt.txt`, `guardrail` payload. Optional UI line on `AnomalyCard` / recon panel — not required for v1.
- **Migration:** **No** if counts live on the recon JSONB item. **Do not** put counts in `monthly_entries`.
- **Size:** **orta**, **2 PR** (preserve columns + pandas counts; then hint/force/prompt). Bigger than annual 12×, much smaller than bank matcher.
- **Depends on:** cutoff allowlist (done). Independent of flux `0010`. Weakly useful to item 3 (wholesale = count × vendor rate).
- **Tests:** Sentinel-shaped roster is the **right** demo **if** the xlsx is restored (archive: 85 rows, `Customer Name`, `Customer ID`, `Service Plan`, `Monthly Fee`, `Start Date`, `Status`, `Last Billed`; three cancelled → $285). On this branch the workbook is **missing**; tests use synthetic frames. Isolated fixture with **count 82 vs 85** plus dollar $3,540 vs $3,825. Negative: annual 12× Software `$13,200` must not become a count card.

**JSONB pattern?** **Partially.** Force-class + isolated fixture **yes**. Account-total-only hint **no** — must compute counts **before** `groupby`. Same *product* pattern, different *grain*.

---

## 5. Revenue-scaled materiality (onboarding)

### What exists

Flux (`comparison.py::calculate_variance`), **not** recon `_is_material`:

| | Dollar | Percent | Who |
|--|--------|---------|-----|
| Tier 1 | `$50,000` AND | `10%` | every category except the set below |
| Tier 2 | `$10,000` AND | `3%` | `category in {REVENUE, PAYROLL, DEFERRED_REVENUE}` |

Both gates must clear. Severity is %-only (`>30` high, `>15` medium). `history_count` is unused. `_TIER2_CATEGORIES` includes `PAYROLL` and `DEFERRED_REVENUE`, which are **not** seeded in `account_categories` (`0001`: REVENUE, COGS, OPEX, G&A, R&D, OTHER_INCOME, OTHER). So wages stay **OPEX/G&A → Tier 1 $50k**. A ~$150–250k/month shop never flags ordinary opex flux. That is DRONE-scale, not ICP.

PR #5 `is_payroll_account()` (substring on canonical GL name) would put wages in Tier 2 **once thresholds are reachable**. On this analysis branch that helper is **absent**. Merge PAYROLL **with or immediately before** this item.

Recon materiality is separate and **already AND-gated** (`consolidator.py::_is_material`: `|$500|` OR (`|$100|` AND `>5%`)). **Do not** retune those constants in this item. Do not let Claude pick floors.

### What onboarding collects today

- `companies`: `id, owner_id, name, sector, currency, created_at` (`0001`). No scale column. Migrations `0002`–`0009` do not alter `companies`.
- `CompanySetupForm.tsx` POST `{ name, sector }` only. Industry is a free-text input, not an enum.
- `CreateCompanyRequest` / `create_company` in `routes.py`: same two fields; currency hardcoded `"USD"`; idempotent by owner.
- `useCompany.ts` Company: `id, name, sector, currency`.
- `ProfilePage.tsx`: read-only name / sector / currency. No edit of scale.
- `domain.entities.Company` dataclass exists; **no runtime import** — repos return `dict` (CLAUDE.md hybrid policy). Do not introduce a dataclass “for consistency” as the work; add a **column** and pass a float/band through `ComparisonAgent.run`.

`onboarding_done` lives in **Supabase Auth user metadata**, not `companies`. Scale must **not** go there (RLS/company isolation, comparison runs server-side on `company_id`).

### Concrete pandas formula (Claude never sees this)

Collect a **band**, not a free-typed dollar (users lie less on bands; pandas still does the math).

| Band | Representative monthly revenue `R` |
|------|-------------------------------------|
| Under $100k | `$50,000` |
| $100k–$250k | `$175,000` |
| $250k–$500k | `$375,000` |
| $500k+ | `$2,000,000` (preserves today’s DRONE-shaped gates) |

Derive dual thresholds so **today’s constants are the $2M point**:

```
dollar_t1 = max(500,  0.025 * R)   # 2.5% → R=$2M → $50,000
pct_t1    = 10
dollar_t2 = max(250,  0.005 * R)   # 0.5% → R=$2M → $10,000
pct_t2    = 3
```

Worked ICP example, band `$100k–$250k`, `R=$175,000`:

- Tier 1 (OPEX/G&A/COGS): flag if `|Δ| > $4,375` **and** `|%| > 10%`
- Tier 2 (REVENUE, payroll-tagged names, and only then a real deferred line): `|Δ| > $875` **and** `|%| > 3%`

Flag rule stays AND (same as now). Severity bands stay 15/30 **percent** (scale-invariant). Missing scale on existing companies: **keep current $50k/$10k constants** (fail-safe, not a silent $0 floor). Profile must allow filling the band later. Do **not** ask Claude to “use a smaller threshold for small companies.”

Optional later: recon `_DELTA_DOLLAR_*` also scaled. **Out of this item** — mixing recon cards with flux onboarding is how this becomes a rewrite.

### Files / schema / size

**Migration required:** `0010_add_company_monthly_scale.sql`  
Shape (spec, do not write now): `companies.monthly_revenue_band TEXT` with a check constraint on the four labels, **or** `NUMERIC` typical monthly revenue. Band is enough. RLS unchanged (`owner_id = auth.uid()`).

**Production files (counted on disk):**

1. `supabase/migrations/0010_add_company_monthly_scale.sql`
2. `backend/api/routes.py` (`CreateCompanyRequest`, `create_company`, `GET /companies/me`)
3. `backend/adapters/supabase_repos.py` / `domain/ports.py` (dict fields)
4. `backend/agents/comparison.py` (`calculate_variance` takes derived gates; `ComparisonAgent.run` reads company)
5. `backend/agents/orchestrator.py` if it constructs comparison without company scale
6. `frontend/src/components/CompanySetupForm.tsx`
7. `frontend/src/hooks/useCompany.ts`
8. `frontend/src/pages/ProfilePage.tsx` (edit/backfill)
9. `tests/agents/test_comparison.py` (rewrite $50k cases as “unscaled / $500k+ band”)
10. PAYROLL: `backend/tools/account_tags.py` + comparison call site if PR #5 not merged yet

UI: `design_rulebook.md` / `general_rulebook.md` when the form is built. Reuse the setup form; do not a second onboarding.

**Size:** **orta**, **tek PR** (two if PAYROLL is still separate). Cross-layer (SQL + API + React + pandas) — triage was right that this is **not** a mikro-fix. It is **not** a new engine. Honest relative size: larger than `_is_material` AND-gate; smaller than coverage cards; much smaller than bank matcher. File count ~10 plus tests.

**Depends on:** PAYROLL helper to make Tier 2 wages real. Independent of items 1–4 and 6.

**Risks:** existing companies with NULL band → must not zero-out gates. Sector free-text is unrelated; do not parse “security” to pick thresholds. Do not log the raw revenue number in dataframe dumps (PII-adjacent); band label is fine.

**Tests:** unit `calculate_variance` per band (ICP vs $500k+). No Sentinel xlsx required. Do not use DRONE as the only band.

**JSONB pattern?** **No.** This is comparison constants + `companies` column, not a recon hint.

---

## 6. WIP (professional services — later vertical)

### Scope estimate only — not an implementation plan

ICP is field service. Construction scored out because close **is** the WIP schedule. Professional services is the **documented second vertical** (`close-process-by-sector.md`): March labor, April invoice; timesheet × rate ≠ invoice (write-down is normal); retainers are liabilities.

What the **current engine already does** if Helix-shaped files are uploaded:

- Hours/revenue dollar totals vs GL → existing recon (`timing_cutoff` / `stale_reference` / `missing_je`)
- Annual SaaS prepaid → Kova 1 `looks_like_annual_prepayment`
- Subcontractor AP → supplier `missing_je`
- Demo file present: `docs/demo_data/helix/helix_project_hours_mar_2026.xlsx` (+ GL, payroll, vendor). That is **hours as amounts**, not %complete.

What it **cannot** do without a new engine: job-level unbilled vs write-off **judgment**, fixed-fee percent complete, multi-element ASC 606. `monthly_entries` has no job dimension. `comparison.py` / `consolidator.py` have no WIP functions.

**Size if the second vertical is opened:** **büyük / new engine**, job grain + collectability is human. Do not start from this analysis. JSONB account-total hints are **insufficient**.

**Depends on:** a product decision to sell PS, not on items 1–5.

---

## Priority (full rationale)

**Value × (1 / architectural risk) × independence**, not “research romance.”

1. **Revenue-scaled materiality** — Highest *product* value for the shops the wedge is sold to. Flux is Day 4 of close; at $50k floors Day 4 is empty. Only item with a single migration (`0010`) and no new matcher. Unblocks PR #5. Do first so later bank cards sit next to a flux story that is also at shop scale.

2. **Bank / processor three-way MVP** — Highest *positioning* value. Explicitly **not** first: it is the only item that can swallow the company (A2X lane). Start only with a **follow-on spec** that freezes MVP boundary (one processor, id-first match, five states, isolated three-file fixture). Account-total fee hint stays as fallback.

3. **RMR account-count** — Highest *Sentinel demo* value after dollars. Grain change is real but local to contracts files. Keep waterfall out. Natural second recon slice after cash MVP, or a parallel track if staffing allows — **do not** parallelize with bank in one PR.

4. **Truck stock** — Low value at ICP (they expense it). High commitment. Park.

5. **Central-station wholesale** — Alarm-only; wants counts from #3. Third vertical / add-on.

6. **WIP / PS** — Second vertical. Helix is a demo of the **current** engine, not a reason to build %complete.

**Do not** order by “research mentioned it first.” Triage already said the flagship is three-way **and** that account-level fee-band was the honest Kova 1 slice. That slice shipped. The next *honest* shippable piece inside the current engine is **scale**, then a **bounded** matcher.

Dependencies: (5) independent; (1) independent of (5) but should follow it in the *roadmap* so the close narrative is coherent; (4) benefits from (3); (3) benefits from (4) counts; (2) and (6) independent parks.

---

## JSONB + force-class + fixture — apply or not

| Item | Follow Kova 1 recon pattern? |
|------|------------------------------|
| 1 Bank three-way | **Results** yes (classes + JSONB cards). **Matching** no — new engine before `groupby`. |
| 2 Truck stock | **No.** Inventory rollforward. |
| 3 Central-station | **Not yet.** Maybe later as named `accrual_mismatch` once counts exist. |
| 4 RMR counts | **Yes for class/force/fixture.** **No** for “just another account-total bool.” |
| 5 Flux scale | **No.** `0010` + form + `calculate_variance`. |
| 6 WIP | **No.** Job engine / later vertical. |

---

## What this document does not approve

- Writing `0010` or `0011` now.
- New `SourceFileType` now.
- Hardcoded `$10k/10%` as a “temporary” flux retune (triage forbade this).
- Seventh class, bank line rec product, waterfall ingest, SSP, ServiceTitan double-count.
- Treating Vandelay Shopify payouts as three-way cash.
- Treating Vandelay inventory **purchases** as a cycle count.
- Treating Helix hours as WIP %complete.

---

## Single approval checkpoint

Approve **the ranking and the boundaries**, not six separate builds:

1. **Next implementation slice = item 5** (revenue band on `companies` via `0010_add_company_monthly_scale.sql`, form + Profile backfill, pandas-derived dual gates, fail-safe to today’s constants, merge/include PAYROLL tag). One medium PR. No matcher. No 7th class.
2. **Immediately after, a dedicated spec (not code) for item 1 MVP** — three source roles, id-first match, five states, isolated fixture, no A2X. Implementation of that spec is a **later** multi-PR engine.
3. **Item 4** (RMR counts) is the next *recon-grain* slice; not in the same PR as (1) or (2).
4. **Items 2, 3, 6 stay parked** as written (inventory engine / alarm add-on / second vertical).

No code from this document until this checkpoint is explicit. If the ranking is rejected, say which item moves — do not “do a bit of all six.”
