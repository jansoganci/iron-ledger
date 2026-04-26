# Three-Sector Demo Plan

> **Active execution doc.** AccountMapper sprint is paused (see `account_mapper_sprint_plan.md`). The hackathon demo will showcase Month Proof across **three distinct industries** using curated multi-file datasets that flow through the existing (smoke-tested) pipeline with **zero new code**.

**Demo headline:** *"One product, three sectors — Field Services, Retail/E-commerce, Professional Services. Same multi-file consolidation engine. Same reconciliation classifier. Same plain-language report."*

**Deadline:** 2026-04-26 demo. Doc written 2026-04-25.

---

## 1. Why this works

The existing pipeline already does the hard part:
- Multi-file ingestion (`run_multi_file_parser_until_preview`)
- Cross-source consolidation (`ConsolidatorAgent`, fuzzy match @ 90% WRatio)
- Reconciliation detection with 4 classifications (`missing_je`, `categorical_misclassification`, `stale_reference`, `timing_cutoff`)
- Guardrail-verified Claude narrative
- Excel export

Smoke test on 2026-04-24 confirmed all of the above on Sentinel Secure (Field Services). **The pipeline is sector-agnostic** — it doesn't care if accounts come from a security vendor or an SaaS company. What it requires is that **each input file has an `Account` (or close variant) column whose values are valid GL account names**, so the consolidator can join across files.

That requirement is the only thing this plan addresses. We curate two more industry datasets that conform to it.

---

## 2. The three sectors

| # | Sector | Demo company name | Status | Files |
|---|---|---|---|---|
| 1 | **Field Services / Equipment** | Sentinel Secure LLC | ✅ Already curated | 5 files in `docs/demo_data/sentinel/` |
| 2 | **Retail / E-commerce** | Vandelay Trading Co. | ⏳ To create | 4 files (this doc) |
| 3 | **IT / Professional Services** | Helix Consulting Partners | ⏳ To create | 4 files (this doc) |

We are **not** demoing Drone Inc. (single-file variance). It already exists and works, but it is a different product story. The three-sector demo focuses entirely on the multi-file consolidation narrative.

---

## 3. The contract every demo file must honor

Every non-GL file must contain a column named **`Account`** (case-insensitive variants OK; Discovery agent will map them) whose values are valid GL account names from the same sector's GL file. The consolidator joins on this.

Why this matters: the consolidator's fuzzy match at 90% threshold canonicalizes "Service Revenue" / "Service revenue" / "Services Revenue" but **will not** match "Stephen Sanchez" → "Service Revenue". Every file's `Account` column must speak GL.

**The curation work is filling in this column manually**, not generating new data shapes.

### Required columns per file

| File type | Required columns | Notes |
|---|---|---|
| GL export | `Account`, `Category`, `Amount`, optionally `Date`, `Description` | Source of truth. Every other file's `Account` must exist here (or fuzzy-match). |
| Department file (any) | `Account`, `Amount` (minimum) | Plus any sector-specific descriptive columns (Vendor, Customer, Employee — these become provenance, not the join key). |

### Reconciliation patterns to engineer in the data

To make the demo span all 4 classification types, each sector's data must contain at least:

| Classification | What it requires in the data |
|---|---|
| `missing_je` | A row in a department file with an `Account` value that exists in GL but the GL has no matching amount (or vice versa: GL has a row with no source backing). |
| `categorical_misclassification` | The same dollar amount appearing in two files but under different `Account` names (e.g., supplier file books $2,400 to "Marketing", GL books $2,400 to "Professional Fees"). |
| `stale_reference` | A reference total (sum of contracts, sum of headcount × rate) differs from GL by a clear delta. Implementation: contracts file totals to $X, GL "Service Revenue" totals to $X ± Y. |
| `timing_cutoff` | At least one date past period close (e.g., period is 2026-03-01, file has rows dated 2026-04-02). The `crosses_period_boundary` hint requires this. |

Each sector must have **all four**. Verify before running the smoke test.

---

## 4. Sector 1 — Sentinel Secure (Field Services) — REFERENCE BASELINE

Already curated. Use as the template for the other two.

### Existing files (`docs/demo_data/sentinel/`)

```
sentinel_gl_mar_2026.xlsx                    41 rows  — GL P&L export, period 2026-03-01
sentinel_supplier_invoices_mar_2026.xlsx     5 rows   — vendor invoices, has Vendor + Account-like columns
sentinel_payroll_mar_2026.xlsx               10 rows  — employee gross pay roster
sentinel_contracts_mar_2026.xlsx             86 rows  — recurring service contracts roster
sentinel_installation_payments_mar_2026.xlsx 5 rows   — one-time installation payments
```

### What the smoke test produced (run on 2026-04-24)

- 32 reconciliation items
- 28 `missing_je` + 4 `categorical_misclassification`
- Run reached `complete`, guardrail green
- Narrative generated (5,508 chars), all numbers verified

### Gaps to close before final demo

- `stale_reference` and `timing_cutoff` are not yet firing in this dataset. Per the audit (item #3), the contracts file totals must be tweaked vs GL "Service Revenue" to fire `stale_reference`, and at least one date pushed past 2026-03-31 to fire `timing_cutoff`.
- **Action:** before running each sector's smoke test, verify the data produces all 4 classifications. If not, edit one row to make it so. Cheaper than re-engineering the classifier.

---

## 5. Sector 2 — Vandelay Trading Co. (E-commerce / Retail)

A small Shopify + Amazon seller. ~$280K monthly revenue. Sells consumer goods (kitchen + home).

### Files to create (4)

#### 5.1 `vandelay_gl_mar_2026.xlsx` — GL export
~25 rows, P&L shape. Columns: `Account`, `Category`, `Amount`, `Date`.

Account list (use exactly these strings as the canonical chart):
| Account | Category | Sample Amount |
|---|---|---|
| Product Sales — Shopify | REVENUE | 184,500 |
| Product Sales — Amazon | REVENUE | 92,300 |
| Shipping Income | REVENUE | 4,800 |
| Returns & Refunds | REVENUE | -7,200 |
| Cost of Goods Sold | COGS | 138,400 |
| Inventory Adjustments | COGS | 2,100 |
| Shopify Payments Fees | OPEX | 5,420 |
| Amazon Seller Fees | OPEX | 13,845 |
| Advertising — Meta | OPEX | 8,200 |
| Advertising — Google | OPEX | 4,150 |
| Warehouse Rent | OPEX | 6,500 |
| Salaries & Wages | OPEX | 21,000 |
| Payroll Taxes | OPEX | 1,890 |
| Software Subscriptions | OPEX | 480 |
| Office Supplies | G&A | 215 |
| Bank Charges | G&A | 95 |
| Legal & Professional Fees | G&A | 1,200 |
| Insurance | G&A | 850 |
| Depreciation | G&A | 420 |
| (etc — round out to ~20–25 accounts) | | |

Date column: `2026-03-01` for all rows (period uniformity).

#### 5.2 `vandelay_shopify_payouts_mar_2026.xlsx` — Shopify payout report
~15 rows. Columns: `Payout Date`, `Account`, `Order ID`, `Gross`, `Fee`, `Net`, `Description`.

The `Account` column must use GL canonical names (`Product Sales — Shopify`, `Shipping Income`, `Returns & Refunds`, `Shopify Payments Fees`).

**Pattern engineering:**
- Total Shopify revenue across rows: $184,500 (matches GL exactly → no flag)
- Sum of `Shopify Payments Fees` across rows: **$5,500** (vs GL's $5,420 → $80 delta, below materiality)
- One payout dated `2026-04-02` for $4,200 of orders captured 2026-03-30 → fires `timing_cutoff`

#### 5.3 `vandelay_amazon_settlement_mar_2026.xlsx` — Amazon settlement
~12 rows. Columns: `Settlement Date`, `Account`, `Order ID`, `Amount`, `Description`.

`Account` values: `Product Sales — Amazon`, `Amazon Seller Fees`, `Returns & Refunds`.

**Pattern engineering:**
- Total Amazon revenue across rows: **$94,800** (vs GL's $92,300 → $2,500 delta → fires `stale_reference` because Amazon's record of revenue disagrees with the GL booking)
- Total Amazon Seller Fees across rows: **$13,845** (matches GL — no flag)
- One settlement row of $1,800 booked under `Amazon Seller Fees` in this file but the same $1,800 is booked under `Software Subscriptions` in GL → fires `categorical_misclassification`

#### 5.4 `vandelay_inventory_purchases_mar_2026.xlsx` — supplier purchases
~8 rows. Columns: `Vendor`, `Invoice Date`, `Account`, `Description`, `Amount`.

`Account` values: `Cost of Goods Sold`, `Inventory Adjustments`, `Warehouse Rent`.

**Pattern engineering:**
- One supplier invoice for $4,300 with `Account = Cost of Goods Sold` that has **no matching amount** in GL → fires `missing_je`
- One row dated `2026-04-05` for $2,800 → fires `timing_cutoff` (redundant with #5.2 but bulletproofs the demo)

### Vandelay smoke test acceptance
- All 4 files upload through `/upload` cleanly
- Run reaches `complete` status without manual intervention
- `reconciliations[]` contains ≥1 item of each classification: `missing_je`, `categorical_misclassification`, `stale_reference`, `timing_cutoff`
- Narrative mentions Shopify and Amazon by name
- Guardrail passes

---

## 6. Sector 3 — Helix Consulting Partners (IT / Professional Services)

A 17-person SAP/Oracle implementation consultancy. ~$420K monthly revenue. Bills T&M against fixed-fee statements of work.

### Files to create (4)

#### 6.1 `helix_gl_mar_2026.xlsx` — GL export
~25 rows, P&L shape. Columns: `Account`, `Category`, `Amount`, `Date`.

Canonical chart:
| Account | Category | Sample Amount |
|---|---|---|
| Service Revenue — T&M | REVENUE | 287,500 |
| Service Revenue — Fixed Fee | REVENUE | 124,000 |
| Reimbursable Expenses Billed | REVENUE | 8,400 |
| Subcontractor Costs | COGS | 42,000 |
| Software Licenses Resold | COGS | 18,500 |
| Salaries & Wages | OPEX | 142,800 |
| Bonuses | OPEX | 12,000 |
| Payroll Taxes | OPEX | 13,975 |
| Health Benefits | OPEX | 8,400 |
| 401k Match | OPEX | 5,712 |
| Professional Development | OPEX | 1,800 |
| Travel — Client | OPEX | 6,200 |
| Office Rent | OPEX | 8,500 |
| Software Subscriptions | OPEX | 2,400 |
| Marketing | OPEX | 1,500 |
| Legal & Professional Fees | G&A | 1,800 |
| Insurance | G&A | 1,400 |
| Depreciation | G&A | 720 |
| Bank Charges | G&A | 95 |
| (etc — round out to ~22 accounts) | | |

#### 6.2 `helix_project_hours_mar_2026.xlsx` — billable hours export
~30 rows (one per consultant per project). Columns: `Consultant`, `Project Code`, `Client`, `Account`, `Hours`, `Rate`, `Amount`, `Date Worked`.

`Account` values: `Service Revenue — T&M`, `Service Revenue — Fixed Fee`, `Reimbursable Expenses Billed`.

**Pattern engineering:**
- Sum of `Service Revenue — T&M` rows: **$291,200** (vs GL's $287,500 → $3,700 delta → fires `stale_reference`: a consultant rate updated mid-period and the project file uses the new rate but GL booked the old rate)
- Sum of `Service Revenue — Fixed Fee` rows: $124,000 (matches GL — no flag)
- One row dated `2026-04-01` for $2,800 (client work delivered last day, billed next period) → fires `timing_cutoff`

#### 6.3 `helix_payroll_mar_2026.xlsx` — payroll register
~17 rows (one per employee). Columns: `Employee`, `Employee ID`, `Role`, `Account`, `Gross Pay`, `Bonus`, `Pay Period`.

`Account` values: `Salaries & Wages`, `Bonuses`.

**Pattern engineering:**
- Sum of `Salaries & Wages`: **$142,800** (matches GL exactly)
- Sum of `Bonuses`: $9,500 (vs GL's $12,000)
- One $2,500 row with `Account = Salaries & Wages` in this file, but the same $2,500 is booked as `Bonuses` in the GL → fires `categorical_misclassification`

#### 6.4 `helix_vendor_invoices_mar_2026.xlsx` — subcontractor + software invoices
~10 rows. Columns: `Vendor`, `Invoice Date`, `Account`, `Description`, `Amount`.

`Account` values: `Subcontractor Costs`, `Software Licenses Resold`, `Software Subscriptions`, `Travel — Client`.

**Pattern engineering:**
- One $7,200 subcontractor invoice for "Tier-2 SAP Specialist (Q1)" with `Account = Subcontractor Costs` that has no matching amount in GL → fires `missing_je`
- Total `Software Subscriptions` across rows: $2,400 (matches GL — no flag, included for realism)

### Helix smoke test acceptance
- All 4 files upload cleanly
- Run reaches `complete` status without manual intervention
- `reconciliations[]` contains ≥1 of each classification
- Narrative mentions T&M billing and the consultant rate change by name (or close to it)
- Guardrail passes

---

## 7. Hour-by-hour execution plan

Total budget: ~7 hours of focused work. Stop when the three smoke tests pass.

### Hour 1 — Vandelay GL + first dept file
- Create `docs/demo_data/vandelay/` directory
- Build `vandelay_gl_mar_2026.xlsx` from the table in §5.1 (use openpyxl from a Python script to get reproducibility — see appendix)
- Build `vandelay_shopify_payouts_mar_2026.xlsx`

### Hour 2 — Vandelay remaining files + verification
- Build `vandelay_amazon_settlement_mar_2026.xlsx`
- Build `vandelay_inventory_purchases_mar_2026.xlsx`
- **Verify**: open all 4 in Excel, manually confirm:
  - Each non-GL file's `Account` values exist in `vandelay_gl_mar_2026.xlsx`
  - The dollar deltas engineered above are arithmetically present
  - At least one date is past 2026-03-31

### Hour 3 — Vandelay smoke test
- Use the same auth + curl flow we used for Sentinel:
  ```bash
  JWT=$(... # refresh JWT)
  curl -X POST http://localhost:8000/upload \
    -H "Authorization: Bearer $JWT" \
    -F "files=@docs/demo_data/vandelay/vandelay_gl_mar_2026.xlsx" \
    -F "files=@docs/demo_data/vandelay/vandelay_shopify_payouts_mar_2026.xlsx" \
    -F "files=@docs/demo_data/vandelay/vandelay_amazon_settlement_mar_2026.xlsx" \
    -F "files=@docs/demo_data/vandelay/vandelay_inventory_purchases_mar_2026.xlsx" \
    -F "period=2026-03-01"
  ```
- Poll `/runs/{id}/status` until `awaiting_confirmation`
- POST `/runs/{id}/confirm`
- Poll until `complete`
- Pull report row from Supabase, verify all 4 classifications present
- **If any classification missing → edit the data and re-run, do not modify code**

### Hour 4 — Helix GL + project_hours
- Create `docs/demo_data/helix/` directory
- Build `helix_gl_mar_2026.xlsx` from §6.1
- Build `helix_project_hours_mar_2026.xlsx` from §6.2

### Hour 5 — Helix remaining files
- Build `helix_payroll_mar_2026.xlsx` from §6.3
- Build `helix_vendor_invoices_mar_2026.xlsx` from §6.4
- Verify column-name and amount consistency same as Hour 2

### Hour 6 — Helix smoke test
- Same flow as Hour 3, against `helix_*.xlsx` files
- Confirm all 4 classifications fire
- If not, edit data, re-run

### Hour 7 — Sentinel gap closure
- Per item #3 in the audit and §4 above: edit `sentinel_contracts_mar_2026.xlsx` and `sentinel_supplier_invoices_mar_2026.xlsx` so Sentinel's reconciliations also span all 4 classifications (currently only 2)
- Re-run Sentinel smoke test → confirm all 4 fire

### Stop condition

All three sectors produce, in `reports.reconciliations[]`:
- ≥1 `missing_je`
- ≥1 `categorical_misclassification`
- ≥1 `stale_reference`
- ≥1 `timing_cutoff`

When that's true, the demo is bulletproof against the headline ("works across three industries with classification diversity"). Stop building. Do not optimize. Do not refactor.

---

## 8. Acceptance checklist (paste this into a runbook)

Before claiming "demo ready", verify:

- [ ] `docs/demo_data/sentinel/` smoke test → run reaches `complete`, all 4 classifications present
- [ ] `docs/demo_data/vandelay/` smoke test → run reaches `complete`, all 4 classifications present
- [ ] `docs/demo_data/helix/` smoke test → run reaches `complete`, all 4 classifications present
- [ ] Each sector's narrative mentions the sector by name (vendor / platform / project terminology)
- [ ] Excel export produces a usable workbook for each sector (Consolidated P&L, Reconciliations, Source Breakdown sheets)
- [ ] README.md `Demo datasets` table updated to include vandelay + helix
- [ ] Each sector's run completes in under 60 seconds (judges' attention budget)

When all boxes are checked, the demo's foundation is locked. Anything beyond this is polish, and polish is optional.

---

## 9. Appendix — Excel generation snippet (openpyxl)

Use this skeleton for each file to keep generation reproducible. **Do not hand-type rows in Excel** — typos in the `Account` column kill the consolidator's join silently.

```python
# scripts/build_vandelay_gl.py
from openpyxl import Workbook
from datetime import date

PERIOD = date(2026, 3, 1)

ROWS = [
    # (Account, Category, Amount)
    ("Product Sales — Shopify",      "REVENUE", -184500),  # negative = credit, follow GL convention
    ("Product Sales — Amazon",       "REVENUE", -92300),
    ("Shipping Income",              "REVENUE", -4800),
    ("Returns & Refunds",            "REVENUE", 7200),
    ("Cost of Goods Sold",           "COGS",    138400),
    # ... add the rest from the table in §5.1
]

wb = Workbook()
ws = wb.active
ws.title = "GL"
ws.append(["Account", "Category", "Amount", "Date"])
for account, category, amount in ROWS:
    ws.append([account, category, amount, PERIOD])

wb.save("docs/demo_data/vandelay/vandelay_gl_mar_2026.xlsx")
```

Repeat with sector-specific column shapes for each dept file. **The `Account` column values must be copy-pasted strings from the GL row list to guarantee an exact match.**

---

## 10. What this plan deliberately does NOT include

These were considered and cut for hackathon scope:

- **AccountMapper** — paused, see `account_mapper_sprint_plan.md`
- **AI-generated demo data** — Claude-generated rows risk inventing account names that don't match the GL canonical list. Hand-curated only.
- **Backup video, rehearsal scripts, presenter notes** — execution focus only; presentation polish is outside this doc's scope
- **Performance optimization** — runs already complete in ~30 seconds on Sentinel; no need to tune
- **Extending classification taxonomy beyond the existing 6** — taxonomy is fine, data must exercise it
- **PDF inputs, ERP API integrations, multi-tenant** — explicitly post-MVP per `30hr_execution_plan.md`

If something not listed in §7 starts feeling necessary, **stop and re-read this section** before adding it.

---

**Last word.** The pipeline already works. The job here is data, not code. Every hour spent in this plan is an hour spent in Excel and Python list-of-tuples, not in agent logic. If you find yourself opening `backend/agents/` for any reason other than reading existing behavior, you have wandered off the plan.
