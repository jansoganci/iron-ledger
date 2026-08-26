# Kova 2 — comprehensive analysis (six items)

*Planning only. No implementation until the single checkpoint at the end is approved.*  
*Date: 26 August 2026. Revised same day (evening): items 4–6 expanded to the same depth as 1–3 (code citations, grain, JSONB yes/no, demo, size). Items 1–3 unchanged.*  
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

*Expanded to the same depth as items 1–3. Code citations from this branch unless noted.*

### What the close actually is

Alarm RMR close is not “Service Revenue dollars vs some other dollars.” It is **how many sites are billable, at what rate**, versus what hit the GL.

Typical misses (research + Sentinel archive):

- Cancelled / suspended still `Status=Active` on the roster.
- Still “Active” but **not billed this month** (`Last Billed` in a prior month).
- Rate increase on the FSM that never reached QBO.

Designed Sentinel story (`docs/archive/implementation_blueprint.md` File 3): 85 roster rows, three stale (`Morningstar Cafe $95` + `Pine Ridge HOA $45` + `Kellerman Law $145` = **$285**). GL Service Revenue **$3,540** vs roster Active fees **$3,825**. Designed class: `stale_reference`.

That $285 is a **sum of three fees**. The *count* story is **85 Active vs 82 billed in March**. Today the product can (sometimes) surface the **dollar** gap. It cannot emit “3 accounts” without inventing it.

### Proof: there is no RMR / account-count concept in code

Searched `backend/` for `RMR`, `recurring monthly`, `subscriber`, `active_count`, `billed_count`. **Zero hits.**

The two `account_count` names that exist are **not** subscribers:

| Site | What it counts |
|------|----------------|
| `consolidator.py::consolidate` log extra `"account_count": len(consolidated)` | How many **canonical GL lines** after fuzzy merge |
| `routes.py` report payload `"account_count": len(entries_list)` | How many **`monthly_entries` rows** this period |

`ReconciliationHints` (`contracts.py`) has period-boundary, 50% fraction, similar-amount, gl-only/source-only, annual 12×, deposit, fee. **No count field. No status field. No rate field.**

`GoldenField` / `GoldenSchemaRow`: `account, account_code, amount, date, parent_category, department, description`. No `status`, `customer_id`, `monthly_fee` as its own type, no `billed_flag`.

`stale_reference` in `narrative_prompt.txt` *prose* says “customer count or rate differences.” The template still only has `[amount]`, `[GL amount]`, `[delta]`. Guardrail supplementation (`interpreter.py::_run_with_guardrail`) appends only `gl_amount`, `non_gl_total`, `delta`, and each `sources[].amount`. **Counts are not in `numbers_used`.** If Claude writes “3 cancelled customers,” that is a golden-rule violation unless pandas already put `3.0` on the item.

Excel export (`excel_export.py`) prints `src.row_count`. That is not a subscriber count (see grain below).

**Verdict of the hunt:** RMR-as-count does not exist. Adjacent class `stale_reference` exists and is dollar-only.

### Grain: why account-total consolidator cannot do this (concrete pipeline)

Sentinel contracts file is **customer grain** (85 rows). The live pipeline collapses it to **one P&L total** before any hint runs.

```
85 customer rows
  (Customer Name, Customer ID, Service Plan, Monthly Fee, Start Date, Status, Last Billed)
        │
        ▼
normalizer.apply_plan          — drops every column not in the 7 golden fields.
                                Status / Customer ID / Last Billed gone.
                                Monthly Fee survives only if Discovery maps it → amount.
                                Customer Name survives only if mapped → account.
        │
        ▼
AccountMapper.build_draft      — "Oak Street Dental" → GL "Service Revenue"
                                (account_mapping_prompt.txt contracts rules)
        │
        ▼
parser.parse_file_silently     — account_name_map applied, THEN
                                df_validated.groupby("account")["amount"].sum()
                                → preview_rows: ONE row, account=Service Revenue, amount=3825
                                (parser.py ~lines 531–552)
        │
        ▼
consolidator.consolidate
  _union / _build_canonical_map / _roll_up / _detect_deltas
  _build_item: ReconciliationSource.row_count = 1   # hardcoded
                                (consolidator.py ~275)
        │
        ▼
hint_computer.compute_hints    — sees gl_amount=3540, non_gl_total=3825, delta=285
                                No 85. No 82. No 3.
```

Two `row_count` lies stacked:

1. **Parser preview is already one row per GL name**, so even `_roll_up`’s real `len(tagged[...])` (consolidator ~199–206, used only on `source_breakdown` for `monthly_entries`) is **1** if consolidator is fed preview frames.
2. **`_build_item` ignores that anyway** and writes `row_count=1` on every `ReconciliationSource`.

Un-hardcoding `row_count` is **still the wrong grain**. If 85 customer rows all map to `Service Revenue` (Active *and* the three stale), `row_count=85` means “85 Excel lines collapsed.” It does **not** mean “82 billed this month.” The GL has **no customer count at all** — only $3,540. Count recon needs **two pandas counts from the roster**, computed **before** `groupby("account")`:

```
n_active         = count(Status == Active)                     # 85
n_billed_in_period = count(Last Billed in period month)        # 82
count_delta      = n_active - n_billed_in_period               # 3
fee_sum_active   = sum(Monthly Fee | Active)                   # 3825  (already have as dollars)
fee_sum_billed   = sum(Monthly Fee | billed in period)         # 3540 if GL is complete
```

All of that is pandas. Claude copies `count_delta` and `n_active`. Class stays **`stale_reference`** (the list is wrong), not `missing_je`, not `accrual_mismatch`, not annual 12×.

Cutoff allowlist (PR #11) already stopped `Last Billed` from stealing this card to `timing_cutoff`. Count work must **read** Last Billed / Status as **count inputs**, not as cutoff dates. Do not re-widen `_crosses_period_boundary`.

**Do not mix with deferred-revenue rollforward.** Opening + billings − recognized = close is a different grain (schedule). Annual lump 12× is already Kova 1. ServiceTitan invoice+payment double count needs row identity after groupby — still forbidden.

### JSONB hint pattern? **Hayır** (as the *only* mechanism). **Evet** (for the *result*).

Same split as item 1 (bank matcher):

| Layer | Kova 1 deposit/fee/12× pattern? |
|-------|----------------------------------|
| Computing the signal | **Hayır.** An account-total bool cannot recover 85 vs 82 after `groupby`. Need a contracts sidecar / pre-aggregate counter (new helper, e.g. `backend/tools/roster_counts.py`) on the **row-level** contracts frame (`df_detailed` already exists in `parse_file_silently` for hint_computer dates — Status is still stripped by the normalizer *before* that). |
| Emitting the speech act | **Evet.** JSONB on the existing `ReconciliationItem`: e.g. `roster_count_delta: int`, `n_active: int`, `n_billed: int` (pandas ints). Interpreter **forces** `stale_reference`. Isolated fixture. Prompt copies those ints. No 7th class. No migration. |

Do not hang this off `similar_amount_in_other_account` or `looks_like_annual_prepayment`. Those are dollar patterns.

### Schema / migration

| Change | Migration? |
|--------|------------|
| Count fields on `ReconciliationHints` / item JSONB | **No** (`reports.reconciliations`, `0007`) |
| Keep `monthly_entries` as dollar totals | **Do not** store 85 subscriber rows there (unique `company_id, account_id, period`) |
| New `SourceFileType` | **No** — `contracts` already exists (`_FILE_TYPE_PATTERNS` includes `roster`, `subscription`, `recurring`, `customer`) |
| Extra golden fields on **all** files (`status`, `customer_id`) | Avoid. Prefer a **contracts-only sidecar** so P&L/payroll stay 7-column pandera. That is a code-schema change (`GoldenField` optional, or a parallel `RosterRow` model), **not** SQL. |
| Persist a customer dimension table | **No** in v1. Ephemeral counts per run. |

Highest SQL file stays `0009` for this item. Do not steal `0010` (that is item 5).

### Demo data

| Set | Count-grain RMR? |
|-----|------------------|
| Sentinel | **Designed yes, file missing on this branch.** Archive specifies `sentinel_contracts_mar_2026.xlsx` (85 rows, columns above, $285 / 3 accounts). Tracked demo tree only has GL Mar + Feb. Tests use synthetic frames (`test_hint_computer.py` Last Billed cutoff; annual fixture hard-codes `row_count=85` as a label, not a computed count). |
| Vandelay | **No.** Shopify/Amazon/purchases — no subscriber roster. |
| DRONE | **No.** Single-file P&L. |
| Helix `retainer_contracts` (archive) | Different vertical; 12 retainers. Not this item. |
| Isolated fixture | **Required** even if the xlsx is restored: pin `n_active=85`, `n_billed=82`, `count_delta=3`, dollars 3825 vs 3540. Negative: annual Software $13,200 / $1,100 must **not** become a count card. Negative: $285 dollar delta with `count_delta=0` stays dollar `stale_reference` without a fake “0 accounts.” |

### Affected files (when later built — do not apply now)

`normalizer.py` / `validator.py` / `contracts.py` (roster sidecar or optional fields — **not** on P&L), `parser.py::parse_file_silently` (run counter **before** `groupby`, keep `df_detailed` columns), **new** `backend/tools/roster_counts.py` (pandas only), `consolidator.py::_build_item` (attach counts; stop pretending `row_count=1` is a subscriber count), `hint_computer.py` (read counts, do not scan P&L), `interpreter.py` force `stale_reference` + guardrail list includes `n_active` / `count_delta`, `narrative_prompt.txt` (copy pandas counts; never “about 3”), tests + isolated fixture. Frontend optional; not required for v1.

`consolidator.py` must **not** become a customer matcher. Identity is roster Status × period, not fuzzy GL names.

### Size / risks / tests

- **Size:** **orta**, **2 PR**. PR-A: preserve roster columns + pandas counts on the item (the grain). PR-B: hint + force-class + prompt + guardrail. Bigger than annual 12× (that was same-item dollars). Smaller than bank matcher (no new `SourceFileType`, no three files).
- **Depends on:** cutoff allowlist (done). Independent of flux `0010`. Item 3 (wholesale) **wants** these counts later (`count × vendor rate`). Independent of bank.
- **Risk:** Using `_roll_up` `row_count` as “accounts” silently counts cancelled + mapped lines and Claude will say “85 customers.” False. Another risk: counting `Last Billed` in April as cutoff again — regression on PR #11. Residual: one customer two rates (plan change mid-month) — v1 sums fees, does not split; prompt says “appears to be.”
- **Tests:** isolated 85/82/3 fixture; Sentinel $285 dollars **plus** count_delta=3; PR #11 Last Billed must stay non-cutoff; annual 12× negative.

**JSONB pattern (one line):** **Hayır** for the count itself (wrong grain). **Evet** for force-class + fixture once pandas has counted.

---


## 5. Revenue-scaled materiality (onboarding)

*This is rank 1 in the table at the top — the next implementation slice. Expanded to the same depth as items 1–3. This is **flux** (`comparison.py`), not recon `_is_material`.*

### What exists today (exact constants)

`backend/agents/comparison.py::calculate_variance`:

```
_TIER1_DOLLAR = 50_000     AND  _TIER1_PCT = 10     # every category except the set below
_TIER2_DOLLAR = 10_000     AND  _TIER2_PCT = 3      # category in {REVENUE, PAYROLL, DEFERRED_REVENUE}
flag = abs(current - avg) > dollar_gate  AND  abs(pct) > pct_gate
```

Severity is %-only (`>30` high, `>15` medium). `history_count` is accepted and **unused**. `ComparisonAgent.run` reads `accounts_map[id].category` and passes that string in — **not** the account name, on this branch.

`_TIER2_CATEGORIES` includes `PAYROLL` and `DEFERRED_REVENUE`. Seeded `account_categories` (`0001_initial_schema.sql`) are only:

`REVENUE, COGS, OPEX, G&A, R&D, OTHER_INCOME, OTHER`

Parser/Haiku never emit `PAYROLL`. Wages land in **OPEX or G&A → Tier 1 $50k**. A 5–40 person shop’s entire monthly payroll often **is** ~$40–50k; a material overtime month is a few thousand dollars. It will never clear $50k.

Recon materiality is a **different** function: `consolidator.py::_is_material` (`$500` OR (`$100` AND `>5%`)). Kova 1 already AND-gated it. **Do not retune recon dollars in this item.** Do not let Claude pick floors.

### Why PR #5 (PAYROLL tag) does not help until this lands — concrete numbers

PR #5 (`cursor/payroll-pattern-match-d72a`) adds `backend/tools/account_tags.py::is_payroll_account` (needles: `payroll`, `wages`, `salary`, `salaries`, `compensation`) and ORs that into Tier 2. On **this** analysis branch the file **does not exist**; `calculate_variance` has no `account_name` argument.

Take Sentinel-scale **Salaries & Wages** (GL **$43,500**). Suppose the 6-month average is **$38,000** (overtime / headcount). Pandas would compute:

```
abs_delta = 5_500
pct       = 5_500 / 38_000 = 14.47%
```

| Stack | Gate used | Clears dollar? | Clears %? | Flag? |
|-------|-----------|----------------|-----------|-------|
| Today (this branch) | Tier 1 $50k AND 10% (category G&A/OPEX) | $5,500 ≰ $50k | 14.47% > 10% | **No** |
| PR #5 only | Tier 2 $10k AND 3% (name match) | $5,500 ≰ $10k | 14.47% > 3% | **No** |
| This item, band $100k–$250k (`R=$175,000`) | Tier 2 `$875` AND 3% | $5,500 > $875 | 14.47% > 3% | **Yes** |

So the tag **promotes the line into a gate that is still DRONE-sized.** Typical ICP payroll noise ($3–8k) stays silent until the **dollar floor** scales. A freak $12k / 28% swing *would* clear PR #5’s $10k — that is not the month we are selling.

Revenue is already Tier 2 and **still broken at ICP**. Sentinel **Installation Revenue $15,000** vs a $10,000 history:

```
abs_delta = 5_000    pct = 50%
```

Current Tier 2: `$5,000 ≰ $10,000` → **not flagged** despite a 50% jump. After scale (`dollar_t2=$875`): flagged. Scale unblocks ICP flux **even if PAYROLL never merges.** Merge PAYROLL **with or immediately before** this item so wages use the tight **scaled** gate, not the tight **$10k** gate.

### `0010` migration — contents (spec only, do not write the file)

**Not a new table.** Add a column on **`companies`** (`0001_initial_schema.sql`: `id, owner_id, name, sector, currency, created_at`). Migrations `0002`–`0009` do not touch `companies`. Next file name **must** be:

`supabase/migrations/0010_add_company_monthly_scale.sql`

Proposed shape (band, not a free-typed dollar — users lie less; pandas still does the math):

```sql
ALTER TABLE companies
  ADD COLUMN IF NOT EXISTS monthly_revenue_band TEXT;

ALTER TABLE companies
  ADD CONSTRAINT companies_monthly_revenue_band_chk
  CHECK (
    monthly_revenue_band IS NULL
    OR monthly_revenue_band IN (
      'under_100k', '100k_250k', '250k_500k', '500k_plus'
    )
  );
```

- `NULL` allowed: existing companies / skip-the-question → **fail-safe = today’s $50k / $10k constants** (do not treat missing as $0).
- RLS unchanged: still `owner_id = auth.uid()`.
- Do **not** put scale on Auth `user_metadata` next to `onboarding_done`. Comparison runs server-side by `company_id`.
- Do **not** combine this with bank attestation. That is `0011_add_bank_attestation.sql` if ever persisted.

Alternative `NUMERIC monthly_revenue` is worse UX (people type annual, or a goal). If collected, pandas would still map to a band internally. Prefer the four labels.

`domain.entities.Company` dataclass is **unused** (repos return `dict`). Do not “introduce a dataclass for consistency.” Add the key on the dict.

### Concrete formula (pandas only — Claude never sees `R`)

Onboarding asks **typical monthly revenue**, not annual (flux is monthly; `/12` in a prompt would violate the golden rule). Four radio options, USD, same as `currency` default.

| UI label (ask this) | Stored `monthly_revenue_band` | Representative `R` used in pandas |
|---------------------|-------------------------------|-----------------------------------|
| Under $100k / month | `under_100k` | `$50,000` |
| $100k–$250k / month | `100k_250k` | `$175,000` |
| $250k–$500k / month | `250k_500k` | `$375,000` |
| $500k+ / month | `500k_plus` | `$2,000,000` |

`$500k+` uses `R=$2,000,000` so **today’s constants are that point** (DRONE-shaped shops keep current behaviour).

```
dollar_t1 = max(500,  0.025 * R)    # 2.5% of monthly revenue → R=$2M → $50,000
pct_t1    = 10                      # unchanged
dollar_t2 = max(250,  0.005 * R)    # 0.5% of monthly revenue → R=$2M → $10,000
pct_t2    = 3                       # unchanged

is_tier2  = category in {REVENUE} or is_payroll_account(name)
            # still do not expect category == "PAYROLL" or "DEFERRED_REVENUE"
flag      = abs_delta > dollar_t{1|2}  AND  abs_pct > pct_t{1|2}
```

Worked ICP, band `$100k–$250k`, `R=$175,000`:

```
dollar_t1 = max(500, 0.025 * 175000) = 4_375     # OPEX / G&A / COGS
dollar_t2 = max(250, 0.005 * 175000) = 875       # REVENUE + payroll-tagged names
```

| Example | Δ / % | Today | After this item |
|---------|-------|-------|-----------------|
| Salaries $43,500 vs $38,000 | $5,500 / 14.5% | No (even with PR #5) | **Yes** (Tier 2 $875) |
| Installation $15,000 vs $10,000 | $5,000 / 50% | No (Tier 2 $10k) | **Yes** |
| Rent $3,200 vs $3,000 | $200 / 6.7% | No | **No** (`$200 ≰ $4,375` and `% ≰ 10`) — correct, noise |
| Unset band | — | $50k / $10k | **same** fail-safe |

Helper belongs next to the constants, e.g. `comparison.py::_gates_from_band(band) -> tuple[float,float,float,float]`. `ComparisonAgent.run` already has `company_id`; it must **read the company row** (today it does not — only entries/accounts/anomalies). `orchestrator.py::run_comparison_and_report` constructs `ComparisonAgent` and calls `comparison.run(run_id, company_id, period)` — pass-through is enough if `run` loads companies.

Do **not** ask Claude to “use a smaller threshold.” Do **not** put `$4,375` in `narrative_prompt.txt`. Flagged anomalies already carry pandas `variance_pct`.

Optional later: scale recon `_DELTA_DOLLAR_*`. **Out of this item.**

### CompanySetupForm / Profile — what the user is asked

Today (`CompanySetupForm.tsx::handleSubmit`):

```
POST /companies  { name: companyName.trim(), sector }
```

`CreateCompanyRequest` (`routes.py`): `name: str`, `sector: str | None`. Currency hardcoded `"USD"`. Idempotent by owner. Industry is a **free-text** input — do not parse “security” to pick gates.

**Add one required control on the same form** (reuse, do not a second onboarding):

- Label: **“Typical monthly revenue”** (plain English; not “materiality,” not “Tier 2”).
- Helper: “Not annual. Not a target. What usually lands in a month.”
- Input: four radios / a select matching the table above. Not a dollar text box.
- POST becomes `{ name, sector, monthly_revenue_band }`.

`ProfilePage.tsx` today is read-only name / sector / currency (comment: “no backend changes required”). **Must grow an edit** for NULL backfill, or existing shops stay on $50k forever. `useCompany.ts` `Company` interface adds `monthly_revenue_band: string | null`. `GET /companies/me` must return it.

UI: `design_rulebook.md` / `general_rulebook.md` when built. One field, same card. Do not log the band next to dataframe values.

### Affected files (counted)

1. `supabase/migrations/0010_add_company_monthly_scale.sql` — **yes, this item is the `0010`**
2. `backend/api/routes.py` — `CreateCompanyRequest`, `create_company`, `GET /companies/me` (and a PATCH if Profile edits)
3. `backend/adapters/supabase_repos.py` + `domain/ports.py` — dict field
4. `backend/agents/comparison.py` — `_gates_from_band`, `calculate_variance` takes gates or band; `ComparisonAgent.run` loads company
5. `backend/agents/orchestrator.py` — only if comparison is constructed without company access (today `company_id` is already passed)
6. `frontend/src/components/CompanySetupForm.tsx`
7. `frontend/src/hooks/useCompany.ts`
8. `frontend/src/pages/ProfilePage.tsx`
9. `tests/agents/test_comparison.py` — today’s $50k cases become “NULL band / `500k_plus`”; add ICP band cases
10. PAYROLL if still unmerged: `backend/tools/account_tags.py` + comparison `account_name` (PR #5)

`guardrail.py` unchanged (still `numbers_used` vs pandas_summary). `hint_computer.py` unchanged.

### JSONB hint pattern? **Hayır.**

This is not a recon speech act. No `ReconciliationHints` bool. No force-class. No sixth-class change. It is `companies` + `calculate_variance`.

### Size / days / risks / tests

- **Size:** **orta**, **tek PR** (two only if PAYROLL is still a separate merge). Cross-layer: SQL + API + React + pandas. Triage was right: **not** a mikro-fix. **Not** a new engine.
- **vs Kova 1:** AND-gate was **one function** in `consolidator.py`. Deposit/fee was hints+prompt+fixture, no migration. This is **~10 files + `0010`**, closer to **coverage cards** than to AND-gate, far smaller than bank matcher (no new file type, no matcher). File count is the honest size; it is not “change two constants.”
- **Depends on:** PAYROLL helper to make wage Tier 2 *after* floors shrink. Independent of items 1–4 and 6. Independent of `0011`.
- **Risk:** NULL band → $0 floors would flag everything; fail-safe must be current constants. Users typing **annual** into a numeric box — that is why the UI is a **monthly band**, not a text amount. Sector free-text must not drive gates. Do not retune recon `$100/$500` in the same PR.
- **Tests:** `calculate_variance` for each band + NULL fail-safe; payroll-tagged name uses `dollar_t2` of that band; Installation $15k vs $10k flags only when scaled; Rent $200 vs $3,200 does not. **No Sentinel xlsx required** (flux reads `monthly_entries`, not the roster). Do not use DRONE as the only band. Browser: onboarding select + Profile backfill (when UI is built).

---

## 6. WIP (professional services — later vertical)

*Scope note, not an implementation plan. Same concrete bar as item 3 (central-station): files, why the schema does not fit, when it comes back.*

### What it is

Professional services is the **documented second vertical**, not the ICP (`close-process-by-sector.md`). Close pain is **unbilled labor**: March work, April invoice; timesheet × rate ≠ invoice because write-downs are normal; retainers are liabilities until earned; fixed-fee jobs want **percent complete**. Construction scored out of the product because close **is** the WIP schedule. Do not import that engine for a later vertical.

Inbox if that vertical is sold: GL, Harvest/Toggl/PSA timesheet, invoice register + AR aging, Gusto, subcontractor Excel, retainer list, SaaS list, T&E, bank.

### File type that would be required (and what we already have)

There is **no** `SourceFileType` for timesheet, WIP, or jobs. Literals remain `general_ledger | payroll | supplier_invoices | contracts`. Filename `helix_project_hours_mar_2026.xlsx` matches none of `_FILE_TYPE_PATTERNS` (`hours` is not payroll/invoice/contract/GL) → **defaults to `supplier_invoices`**. AccountMapper then treats hour rows like vendor bills.

Tracked Helix set (current engine demo, not %complete):

| File | What it actually is |
|------|---------------------|
| `docs/demo_data/helix/helix_gl_mar_2026.xlsx` | P&L |
| `docs/demo_data/helix/helix_payroll_mar_2026.xlsx` | Payroll → existing type |
| `docs/demo_data/helix/helix_project_hours_mar_2026.xlsx` | Hours as **amounts** mapped toward a GL name |
| `docs/demo_data/helix/helix_vendor_invoices_mar_2026.xlsx` | Supplier |

That is **file-total dollars vs GL**, which consolidator already does (`timing_cutoff` / `stale_reference` / `missing_je`). Annual SaaS prepaid on a software line is Kova 1 `looks_like_annual_prepayment`. Subcontractor AP is today’s supplier path. **None of this is WIP.**

A real WIP / %complete file would need **job grain**: `job_id`, contract value, cost-to-date, estimate-to-complete, `% complete`, billed-to-date, unbilled. Those are not `GoldenField`s. Discovery would drop them. Parser `groupby("account")` would sum three jobs into one revenue total and destroy the schedule.

### Why today’s schema cannot hold it

| Object | Why it fails |
|--------|----------------|
| `GoldenField` (7 columns) | No job, no %complete, no billed-to-date |
| `parser.py` `groupby("account")` | Same grain kill as RMR counts and bank batches |
| `monthly_entries` unique `(company_id, account_id, period)` | One amount per GL line per month — cannot store opening WIP + this month’s earned − billed |
| `comparison.py` / `consolidator.py` | **Zero** WIP, utilization, or unbilled functions (grep-clean) |
| Six classes | Dollar gaps can be `timing_cutoff` (billed next month) or `stale_reference` (retainer list). **Unbilled vs write-off is human judgment** — a hint cannot pick collectability |
| Guardrail | If Claude writes “40% complete,” that number is invented unless pandas emitted it from a schedule we do not ingest |

**JSONB pattern?** **Hayır.** Account-total bools cannot roll a job. Same family as inventory (item 2) and bank matching (item 1): results could theoretically sit in JSONB; the engine does not exist.

### When it should come back

**Not in the Kova 2 implementation queue.** Trigger is a product decision to **sell professional services**, after field-service cash + flux at shop scale exist. Then write a **new vertical spec** (job table or schedule ingest, %complete in pandas, human collectability). Helix hours staying in `docs/demo_data/` is **not** that trigger — it proves the current consolidator is sector-agnostic on dollars.

- **Size if opened:** **büyük / new engine**, **çok-PR**, same order as construction (which we refused).
- **Depends on:** none of items 1–5. Do not block materiality or bank.
- **Migration if opened:** yes, later — job/WIP store; **not** `0010`.
- **Tests:** Helix hours = **negative** (still dollar recon, not %complete). Isolated %complete fixture only when the vertical is real.

---

## Priority (full rationale)

**Value × (1 / architectural risk) × independence**, not “research romance.”

1. **Revenue-scaled materiality (item 5)** — Highest *product* value for the shops the wedge is sold to. Flux is Day 4 of close; at $50k floors Day 4 is empty. Concrete: Installation $15k vs $10k (50%) does not flag today. Only item with a single migration (`0010`) and no new matcher. Unblocks PR #5. Do first so later bank cards sit next to a flux story that is also at shop scale.

2. **Bank / processor three-way MVP (item 1)** — Highest *positioning* value. Explicitly **not** first: it is the only item that can swallow the company (A2X lane). Start only with a **follow-on spec** that freezes MVP boundary (one processor, id-first match, five states, isolated three-file fixture). Account-total fee hint stays as fallback.

3. **RMR account-count (item 4)** — Highest *Sentinel demo* value after dollars. Grain change is real but local to contracts files. Keep waterfall out. Natural recon slice after cash MVP — **do not** parallelize with bank in one PR.

4. **Truck stock (item 2)** — Low value at ICP (they expense it). High commitment. Park.

5. **Central-station wholesale (item 3)** — Alarm-only; wants counts from item 4. Third vertical / add-on.

6. **WIP / PS (item 6)** — Second vertical. Helix is a demo of the **current** engine, not a reason to build %complete.

**Do not** order by “research mentioned it first.” Triage already said the flagship is three-way **and** that account-level fee-band was the honest Kova 1 slice. That slice shipped. The next *honest* shippable piece inside the current engine is **scale**, then a **bounded** matcher.

Dependencies: item 5 independent; item 1 independent of 5 but should follow it on the roadmap; item 4 independent of 5, useful to item 3 later; items 2 and 6 parked.

---

## JSONB + force-class + fixture — apply or not

| Item | Follow Kova 1 recon pattern? |
|------|------------------------------|
| 1 Bank three-way | **Results** yes (classes + JSONB cards). **Matching** no — new engine before `groupby`. |
| 2 Truck stock | **Hayır.** Inventory rollforward. |
| 3 Central-station | **Not yet.** Maybe later as named `accrual_mismatch` once counts exist. |
| 4 RMR counts | **Hayır** for the count (wrong grain). **Evet** for force-class + fixture once pandas has counted. |
| 5 Flux scale | **Hayır.** `0010` + form + `calculate_variance`. |
| 6 WIP | **Hayır.** Job engine / later vertical. |

---

## What this document does not approve

- Writing `0010` or `0011` now.
- New `SourceFileType` now.
- Hardcoded `$10k/10%` as a “temporary” flux retune (triage forbade this).
- Seventh class, bank line rec product, waterfall ingest, SSP, ServiceTitan double-count.
- Treating Vandelay Shopify payouts as three-way cash.
- Treating Vandelay inventory **purchases** as a cycle count.
- Treating Helix hours as WIP %complete.
- Un-hardcoding `row_count=1` and calling that RMR.

---

## Single approval checkpoint

Approve **the ranking and the boundaries**, not six separate builds.

**Sıradaki implementation = madde 5 (revenue-scaled materiality / onboarding):** `companies.monthly_revenue_band` via `0010_add_company_monthly_scale.sql`, one monthly-revenue question on `CompanySetupForm` + Profile backfill, pandas `dollar_t1 = max(500, 0.025*R)` / `dollar_t2 = max(250, 0.005*R)`, fail-safe to today’s $50k/$10k when the band is NULL, merge/include the PAYROLL name tag so wages use the *scaled* tight gate. One medium PR. No matcher. No 7th class. No recon `$100/$500` retune.

After that ships, write a **spec** (not code) for item 1 MVP, then item 4 as its own recon-grain PRs. Items 2, 3, 6 stay parked.

No code from this document until this checkpoint is explicit. If the ranking is rejected, say which item moves — do not “do a bit of all six.”
