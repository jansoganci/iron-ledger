# Field-service close research — architecture triage

*Planning only. No implementation until this document is approved.*  
*Date: 24 August 2026.*  
*Source report: field-service SMB month-end close practices (undeposited funds, deferred RMR, alarm-specific accruals, materiality).*  
*Architecture: IronLedger codebase, product name Month Proof. Same repo, not a second product.*

Phase gate: **spec → approval → implementation.** This file is the spec-side triage. Do not start an implementation prompt from it until the buckets are accepted.

---

## How to read this

Three buckets, nothing in between.

- **Bucket 1** — additive now. Uses the existing six classifications, pandas for every number, Claude for prose only. No new engine, no new `SourceFileType`, no bank matcher.
- **Bucket 2** — true and useful later. Needs a new data shape, a new engine, or a later vertical. Not this slice.
- **Bucket 3** — market / positioning. Never becomes code.

Each item: **finding → file/function → scope** (`mikro-fix` | `yeni tablo alanı` | `yeni component` | `sadece not`).

Next migration number if anything in Bucket 1 is persisted: **`0010_{snake_case}.sql`**. Hints live in `reports.reconciliations` JSONB, so a new hint field is Pydantic-only unless we also persist a first-class column.

---

## Architecture lock (do not re-litigate)

Verified in this repo before triage:

- Golden rule: pandas computes, Claude narrates, `backend/tools/guardrail.py` verifies. Claude never arithmetic.
- Six classifications only (`backend/domain/contracts.py::ReconciliationClassification`): `missing_je`, `stale_reference`, `categorical_misclassification`, `timing_cutoff`, `accrual_mismatch`, `structural_explained`. A seventh class is a product change, not a mikro-fix.
- **AccountMapper already runs before consolidate.** Vendor / employee / customer names are mapped to GL account names, then `consolidator.py` joins on `account`. Do not treat “real files lack a GL Account column” as a new engine. That gap is closed.
- `SourceFileType`: `general_ledger`, `payroll`, `supplier_invoices`, `contracts`. No bank, no processor, no inventory.
- Bank transaction matching was explicitly cut (different data shape).
- Interpreter fallback (`interpreter.py::_classify_from_hints`) never emits `structural_explained`. `is_round_fraction` (documented as a 50% deposit / timing signal) currently falls through to `accrual_mismatch`.

---

## Bucket 1 — do now, no new engine

These correct the current model. They stay inside the six classes.

### 1. Consolidator materiality is not the documented AND-gate

**Finding.** Module docstring: flag if `|delta| > $100 AND |delta_pct| > 5%`, OR `|delta| > $500`. `_is_material` ignores percent and collapses to `>= $100`:

```python
return abs_delta >= _DELTA_DOLLAR_HARD or abs_delta >= _DELTA_DOLLAR_MIN
```

`_DELTA_PCT_MIN` is unused. This is the main reason a 41-line GL can emit ~32 recon items.

**Affects.** `backend/agents/consolidator.py::_is_material` (and tests under `tests/agents/test_consolidator.py`).

**Scope.** `mikro-fix`. Implement the documented rule in pandas only. Do not let Claude decide materiality.

---

### 2. Comparison flux floors are DRONE-scale

**Finding.** Practitioners for a ~$150–250k/month shop use roughly **$5–15k dollar floors with 5–10% bands**, tighter **2–5%** on revenue, payroll, deferred revenue, and cash. Current code: Tier 1 `$50k AND 10%`, Tier 2 `$10k AND 3%` (`REVENUE` / `PAYROLL` / `DEFERRED_REVENUE`).

**Affects.** `backend/agents/comparison.py::calculate_variance` constants `_TIER1_*`, `_TIER2_*`, `_TIER2_CATEGORIES`.

**Scope.** `mikro-fix` for constant retune (proposed starting point for this vertical: Tier 1 `$10k AND 10%`, Tier 2 `$5k AND 5%` on revenue; payroll/cash via **account-name** match, not a new category seed).

**Do not.** Insert `PAYROLL` / `DEFERRED_REVENUE` into `account_categories` just to make the constant fire. Parser seed is `REVENUE, COGS, OPEX, G&A, R&D, OTHER_INCOME, OTHER`. Those two Tier-2 names never match today. Per-company configurable thresholds are Bucket 2 (`0010` + settings UI).

---

### 3. Split “deposit-as-liability” from processor clearing

**Finding.** Customer prepayment / %50 install deposit is a **liability** until work is done (`accrual_mismatch` or a liability-flavored `timing_cutoff` narrative). Processor / Undeposited Funds gap is **not** a liability: FSM books gross, bank pays net of fees. Conflating them produces the worst failure mode for a narrative product.

**Affects.**

- `backend/tools/hint_computer.py` — keep `is_round_fraction` for the 50% deposit pattern; add a pandas hint e.g. `looks_like_processor_fee` when GL is the lower side and `delta_pct` sits in a named fee band (constant, not a Jobber marketing rate in prose).
- `backend/domain/contracts.py::ReconciliationHints` — new optional bool (JSONB, no migration).
- `backend/agents/interpreter.py::_classify_from_hints` — deposit pattern should not silently become `accrual_mismatch`; processor-fee hint should reach `structural_explained` (today that class is unreachable in the fallback).
- `backend/prompts/narrative_prompt.txt` — two templates: (a) customer deposit / prepaid agreement = liability; (b) gross-vs-net fee = structural, no “expect reversal as deferred revenue.”

**Scope.** `mikro-fix`. Fee **dollar** amounts used in prose must be computed in pandas and placed in `numbers_used`. Do not bake “2.9% + 30¢” into the prompt (guardrail will fail or Claude will invent).

**Not in this item.** Full three-way batch matching FSM ↔ processor ↔ bank (Bucket 2).

---

### 4. `crosses_period_boundary` is too wide (cutoff mis-fire)

**Finding.** Completed-but-unbilled jobs and month-end card batches are real close items. The current hint scans **any** date-like column in involved files. A contracts roster with renewal / next-bill dates can force `timing_cutoff` and outrank `stale_reference` on the RMR tie-out.

**Affects.** `backend/tools/hint_computer.py::_crosses_period_boundary`; fallback order in `interpreter.py::_classify_from_hints`.

**Scope.** `mikro-fix`. Restrict to transaction-date-like headers (date, txn_date, invoice_date, payment_date, deposit_date). Exclude renewal, due, next_bill, end_date. Still pandas-only.

---

### 5. Annual prepay booked straight to revenue (common SMB miss)

**Finding.** GAAP wants prepaid monitoring/maintenance as a liability released over the term. 5–40 employee dealers often skip the rollforward, especially on monthly billing. The catchable error is **annual (or quarterly) cash booked 100% to revenue**. ServiceTitan double-recognition of a membership is **not** this item (row-level; Bucket 2).

**Affects.** Existing hint `delta_matches_known_vendor` (`delta × 12`) in `hint_computer.py`; `narrative_prompt.txt` `accrual_mismatch` template; interpreter fallback already has an accrual branch.

**Scope.** `mikro-fix` (prompt + hint wiring). Do **not** ingest a deferred-revenue waterfall. Do **not** assume the dealer maintains a rollforward. Detect absence / lump-sum; do not compute SSP.

---

### 6. Bank rec is daily/weekly — product still does not match lines

**Finding.** Practitioners reconcile cash continuously; month-end is the residue (unbooked fees, cross-period batches, undeposited sweep). The product must not pretend cash is done, and must not start a bank matcher.

**Affects.** `frontend/src/components/ReportSummary.tsx` (or close checklist copy); `backend/tools/excel_export.py` attestation line. Optional persist: `0010_add_bank_attestation.sql` on `reports` or `runs`.

**Scope.** `mikro-fix` if display-only. `yeni tablo alanı` if the checkbox is stored. Wording: residue (fees, straddling batches, undeposited ≠ 0) is in-scope as **account-level** recon when those files exist; line-level matching stays out.

---

### 7. Named tie-outs: subcontractor accrual (not a new class)

**Finding.** Work completed, vendor invoice not in GL = `missing_je` / `accrual_mismatch` on the supplier file we already accept.

**Affects.** Grouping labels in `frontend/src/components/ReconciliationPanel.tsx`; optional sheet copy in `backend/tools/excel_export.py`. No new classification.

**Scope.** `yeni component` (label/group only) **or** `sadece not` until the checklist UI slice is approved. Engine already covers the math.

---

### 8. Owner-facing KPI strip from pandas (not a new statement)

**Finding.** Owner package wants P&L vs prior, short narrative, field-service KPIs (GM, labor/revenue, materials/install). Full Balance Sheet + Cash Flow are **not** additive (`monthly_entries` has one amount per account/period, no BS rollforward).

**Affects.** `comparison.py` / `PandasSummary` derived ratios (pandas); `ReportSummary.tsx`; maybe a fourth Excel sheet.

**Scope.** `yeni component` for the strip. BS/CF → Bucket 2.

---

### 9. Prompt hygiene: no vendor percentages in templates

**Finding.** Unverified rates (Jobber 2.9%, “5–10% of accounts”, “one full day recon”) must not ship in `backend/prompts/` or UI copy. Guardrail does not validate prompt constants; if Claude echoes them they either fail the guardrail or look authoritative.

**Affects.** `backend/prompts/narrative_prompt.txt` (and any new hint comments that get copied into prompts).

**Scope.** `mikro-fix` / policy. Pandas may use an internal fee **band** constant labeled unverified; prose must use pandas outputs only.

---

## Bucket 2 — later phase or later vertical

Correct research. Building now would violate “no new engine” and the existing cut list.

| Finding | Why it waits | File / function (when later) | Scope |
|---------|--------------|------------------------------|--------|
| Three-way undeposited: FSM gross → GL UF → bank net, per batch | Needs `SourceFileType` bank/processor, batch id, txn count (normalizer drops this), settlement date. Not fuzzy account join. | New matcher; not `consolidator._build_canonical_map` | new engine (not a listed scope token — treat as later spec) |
| ServiceTitan membership recognized twice (invoice + payment) | Information is gone after account-level `groupby` | Would need row identity in `monthly_entries` | new engine |
| Truck-stock / van inventory cycle count | Opening + receipts + consumption + count; BS asset. Not a P&L file total. | Would impersonate a tie-out and silently commit to inventory | new engine |
| Central-station wholesale monitoring COGS accrual | Alarm-specific vendor schedule + minimum-volume; no analog in current four file types | New source type + named accrual | `sadece not` now; later `yeni tablo alanı` if a dedicated file is inboxed |
| RMR account-count vs GL (suspended still billed, missed rate increase) | Needs roster **counts** and rates, not only dollar totals; FSM vs QBO identity | Adjacent to `stale_reference` but a different grain | later; do not fake with dollar-only join |
| Deferred revenue **rollforward schedule** ingest | Waterfall / ASC 606 out of scope by decision | — | `sadece not` |
| ASC 606 SSP split install vs monitoring | Dealers don’t do it; detect blend via `categorical_misclassification` when amounts match across accounts | Already a class example | `sadece not` (no SSP engine) |
| WIP / % complete on multi-day installs | Same reason construction scored out | — | new engine |
| Professional services as close #2 (unbilled labor / utilization) | Different problem shape: WIP cash lock, not processor mess | Would need a WIP recon model | later vertical |
| Per-company materiality config | `companies` JSONB + settings UI | `0010_add_materiality_settings.sql`, `comparison.py`, `consolidator.py` | `yeni tablo alanı` |
| Persist bank attestation | Optional if Bucket 1 display-only is not enough | `0010_add_bank_attestation.sql` | `yeni tablo alanı` |
| Balance sheet + cash flow in the package | Schema cannot roll balances | `monthly_entries` model | new engine |
| Gross margin **by service line** | `department` exists on golden row, not persisted | entries + report | `yeni tablo alanı` |
| PTO accrual JE (QBO accrues per hour worked only) | Real close entry; needs hours/policy, not a GL-vs-file total | — | `sadece not` until payroll file carries PTO columns |
| Unbilled/WIP as first-class cutoff **at job grain** | File-total timing is Bucket 1; job-level WIP is not | — | new engine |
| Consumer financing / lease accounting | Small dealers offload; ≤12-month expedient | — | `sadece not` |
| Warranty / service-call cost reserve | Weak sources; open question | — | `sadece not` |
| False-alarm fines, permits, NFPA 72 attachments | Billing completeness, not GL tie-out | — | `sadece not` |
| Prevailing wage / union payroll | Govcon/commercial construction, not residential alarm/HVAC | — | `sadece not` (do not over-build) |

**Flagship vs slice.** The research’s best wedge is the three-way processor recon. Account-level fee-band → `structural_explained` (Bucket 1) is the honest slice. Per-deposit matching is a different product.

---

## Bucket 3 — market / positioning only

No files. No functions. Scope always `sadece not`.

- RMR purchase multiples 25–50x; attrition bands (sub-5% vs 10–15%) and “books quality affects exit.”
- M&A diligence constructing deferred-revenue schedules dealers never kept.
- Public-company 10-K SSP language (Monitronics/Brinks) as contrast, not SMB practice.
- Software-vendor marketing stats: “5–10% of accounts missed rate increase,” “recon searches consume an entire day,” “1–4% data-entry error” — **unverified vendor claims**. Repeat in a pitch deck only with that label; never in prompts.
- Field Promax undeposited article: workflow consistent with Intuit; treat dated benchmarks as SEO-grade.
- Small-dealer deferred-revenue / SSP practice is **inferential** (vendor marketing + M&A + old large-company filings). Strong hypothesis, not established fact.
- Security/alarm as first vertical because it stacks cash mess + RMR + job-costed installs — corroborates [docs/06-reports/close-process-by-sector.md](../06-reports/close-process-by-sector.md); does not change ranking by itself.
- HVAC in the same first wave as alarm (same three problems). Professional services later and **weaker fit** for a recon-first engine.

---

## Explicit non-goals for the next implementation prompt

When (if) implementation is approved, the first prompt must **not** include:

- Bank/processor transaction matching or a new `SourceFileType`
- A seventh reconciliation classification
- Inventory / truck-stock valuation
- ASC 606 waterfall or SSP allocation
- Seeding `PAYROLL` / `DEFERRED_REVENUE` categories “for consistency”
- Rebuilding AccountMapper
- Claude-computed fee estimates

Suggested implementation order **after approval** (not this task):

1. `_is_material` AND-gate (exception count becomes believable)
2. Date-hint restriction + deposit vs fee classification/prompt split
3. Comparison constant retune (and stop pretending Tier-2 payroll category exists)
4. Checklist grouping / KPI strip only after 1–3, or the UI still shows 32 cards

Reserve `0010_*.sql` for attestation and/or configurable materiality — only if those leave Bucket 1 as display-only insufficient.

---

## Mapping back to the research “Recommendations”

| Research rec | Bucket |
|--------------|--------|
| Keep three-way undeposited as flagship | Split: account-level fee hint = 1; full three-way = 2 |
| Recalibrate materiality now | 1 (constants); config = 2 |
| Split deposit-as-liability vs processor clearing | 1 |
| Extend five-tie-out with truck-stock, subcontractor, central-station, RMR count | Subcontractor label = 1; the rest = 2 |
| Design for monthly billing, minimal deferred, no SSP; catch annual-to-revenue | 1 (detect); rollforward ingest = 2 |
| Stage alarm+HVAC first, PS later | 3 (plus ranking already in close-process-by-sector.md) |

---

## Approval checkpoint

Approve or amend **Bucket 1 items 1–3** before any implementation prompt. Those three are the only changes that both (a) the research requires and (b) the architecture can absorb without a new engine.

If Bucket 1 item 3 (fee hint) is rejected as “too close to a bank matcher,” keep the **prompt split** only: never narrate a net-of-fee delta as deferred revenue. That alone is still a valid mikro-fix.
