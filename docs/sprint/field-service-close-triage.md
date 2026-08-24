# Field-service close research — architecture triage

*Planning only. No implementation until this document is approved.*  
*Date: 24 August 2026. Revised same day (2): direct answers to the two placement/root-cause questions; orchestrator `compute_hints` overwrite added to the class-6 chain; `0010` vs `0011` numbering note.*  
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

**Migration number (verified on disk, 24 Aug 2026).** Nine files in `supabase/migrations/`: `0001_initial_schema` … `0008_opus_upgrade`, highest **`0009_add_report_type_and_quarterly.sql`**. The earlier “next is `0010`” guess is **correct as a sequence number**, wrong if read as “a migration named 0010 already exists.” It does not. Next write, if any, is **`0010_{snake_case}.sql`**. Two later schema items (company monthly scale, optional bank attestation) cannot share one file — they would be `0010` then `0011`. Hints live in `reports.reconciliations` JSONB, so a new hint field is Pydantic-only unless we also persist a first-class column.

---

## Architecture lock (do not re-litigate)

Verified in this repo before triage:

- Golden rule: pandas computes, Claude narrates, `backend/tools/guardrail.py` verifies. Claude never arithmetic.
- Six classifications only (`backend/domain/contracts.py::ReconciliationClassification`): `missing_je`, `stale_reference`, `categorical_misclassification`, `timing_cutoff`, `accrual_mismatch`, `structural_explained`. A seventh class is a product change, not a mikro-fix.
- **AccountMapper already runs before consolidate.** Vendor / employee / customer names are mapped to GL account names, then `consolidator.py` joins on `account`. Do not treat “real files lack a GL Account column” as a new engine. That gap is closed.
- `SourceFileType`: `general_ledger`, `payroll`, `supplier_invoices`, `contracts`. No bank, no processor, no inventory.
- Bank transaction matching was explicitly cut (different data shape).
- Interpreter fallback (`interpreter.py::_classify_from_hints`) never emits `structural_explained`. `is_round_fraction` (documented as a 50% deposit / timing signal) currently falls through to `accrual_mismatch`. Runtime chain: consolidator shapes items → `orchestrator.py` overwrites hints via `compute_hints` → Claude + fallback. Full diagnosis: [structural_explained diagnosis](#structural_explained-diagnosis) below.

---

## Decisions locked this round (not yet implemented)

Three product decisions. Recorded here so the next approval round is about *how*, not *whether*. **No code in this turn.**

1. **PAYROLL detection is pattern-match, not Haiku.** Same mechanism as `backend/tools/pii_sanitizer.py` (`_ALWAYS_DROP`: case-insensitive substring list). A deterministic substring list (`payroll`, `wages`, `salaries`, …) tags an account as payroll-sensitive **under** an existing seeded category (G&A or OPEX). Do **not** insert a row into `account_categories` (immutable). Do **not** fold this into AccountMapper. Placement analysis: [PAYROLL pattern — where](#payroll-pattern--where).
2. **`structural_explained` fallback is in scope, but diagnose before fix.** Diagnosis is below. Fix is proposed, not applied.
3. **Flux thresholds: no hardcoded dollar/% in the next slice.** Do not write `$10k/10%` or `$5k/5%` as product constants. Onboarding must collect company monthly scale; materiality is a revenue-scaled dual threshold (dollar floor AND percent) derived from that scale. Bucket call: [Flux via onboarding — bucket](#flux-via-onboarding--bucket).

---

## Direct answers (this round)

Two questions from the assignment, answered before the long-form sections.

### Where should the PAYROLL pattern run — `consolidator.py` or a pre-AccountMapper step?

**Neither as the only site.** Both have a real plus; both fail as the *sole* site.

| | `consolidator.py` (Option A) | Pre-AccountMapper (Option B) |
|---|---|---|
| Plus | Already owns canonical GL names after fuzzy merge | Isolated `tools/` step, same shape as PII |
| Minus | Flux (`comparison.py`) never reads consolidator output; payroll-tight flux would not fire | Pre-map values are `"Jane Doe"` / vendors, not `"wages"` — wrong grain; risks tagging a whole payroll *file* |

**Correct place:** a pure helper `backend/tools/account_tags.py::is_payroll_account(name)` (case-insensitive substring list, no LLM, no I/O), called from **`comparison.py`** on the canonical GL name after mapping. Optional second call from consolidator, still on canonical names, only if recon materiality should also treat payroll tighter. Not inside `AccountMapper.build_draft`. Full plus/minus: [PAYROLL pattern — where](#payroll-pattern--where).

### Is class 6 dead because the prompt lacks a signal, or because consolidator dumps ambiguous cases into the wrong class?

**Both, at different layers. Not one or the other.**

- **Why `structural_explained` never fires, even on a true two-sided fee gap:** pandas has no fee/netting hint; the prompt says “If unsure, default to `missing_je`”; `_classify_from_hints` has no class-6 branch (last resort is `stale_reference`). `guardrail.py` does not check classifications. **This is the primary root cause for the dead class.**
- **Why Sentinel looks like 28× `missing_je`:** consolidator groups by `(canonical, category)` and flags orphans at `≥ $100`, so most items arrive one-sided. One-sided *is* `missing_je` in the taxonomy. Relabeling those orphans as `structural_explained` would be the wrong fix. **This is the amplifier, not the class-6 hole.**

Full chain (including the orchestrator overwrite of consolidator hints): [structural_explained diagnosis](#structural_explained-diagnosis).

---

## PAYROLL pattern — where

**Rule (decided).** Deterministic, case-insensitive substring match on the **canonical account name** (the GL line after mapping), analogous to PII header blacklist. Example needles: `payroll`, `wage`, `wages`, `salary`, `salaries`, `gross pay`, `direct labor` (final list is an implementation detail). Match → sub-tag `payroll` while `category` stays `OPEX` or `G&A`. `account_categories` unchanged. AccountMapper / Haiku never sees this list.

**Consumer today.** `comparison.py::calculate_variance` takes `category` from `accounts.category`. `_TIER2_CATEGORIES` includes `"PAYROLL"` and `"DEFERRED_REVENUE"`, which are **not** seeded, so the tight flux gate never fires on wages. The pattern exists to feed that gate (and any later recon severity) without a new category row.

### Option A — inside `consolidator.py`

Run the substring pass on `canonical` after `_build_canonical_map`, before roll-up / delta.

- Plus: one place already owns canonical names. Recon items could carry a `payroll` flag in JSONB with no extra hop. Fuzzy merge has already collapsed “Wages & Salaries” / “Payroll”.
- Minus: flux does **not** read consolidator output; it reads `monthly_entries` + `accounts.category`. Tagging only in consolidator does not fix `calculate_variance` unless the tag is persisted on `accounts` or passed through entries. Consolidator is a recon engine; payroll-tight flux is a comparison concern. Puts a flux rule in the wrong agent.

### Option B — preprocessing before AccountMapper

Run the list on raw `account` values (employee names, vendor names) before Haiku maps them to GL lines.

- Plus: early, isolated step; looks like PII (tools, not agents).
- Minus: **wrong grain.** Pre-map values are `"Jane Doe"`, `"AlarmTech"`. They will not contain `"wages"`. Filename/file-type (`orchestrator.py::_FILE_TYPE_PATTERNS` already has `payroll`, `gusto`, `adp`) is a file-level hint, not an account-level tag. Risk of tagging the whole payroll **file** and then treating mapped GL lines that are not wages (e.g. contractor pass-through) as payroll. Mixes with AccountMapper timing (map before groupby) and invites Haiku-adjacent bugs.

### Recommendation (for the next spec, not code)

**Neither A-as-sole-site nor B.**

Put the list in a new pure helper next to the PII analog, e.g. `backend/tools/account_tags.py::is_payroll_account(name: str) -> bool` — **no LLM, no I/O**. Call it from **`comparison.py`** when `account_name` is already the GL name (`accounts_map[...].name`). That is the function that currently passes `category="OPEX"` / `"G&A"` / `"OTHER"` into `calculate_variance`. Optional second call site: consolidator, only if recon materiality should also treat payroll tighter — still on **canonical** names, after mapper.

Do not call it from `AccountMapper.build_draft` or `parse_file_silently` pre-map.

---

## structural_explained diagnosis

Taxonomy (prompt + `ReconciliationClassification`): the delta is fully explained by fees, platform deductions, or structural netting; not an error; no action.

**When it SHOULD fire.** Two-sided recon (both GL and a source present) where pandas can support “this gap is the known netting,” e.g. FSM gross vs bank/GL net of processor fees; platform fees deducted before deposit; refunds netted. It should **not** fire on one-sided orphans (those are `missing_je`).

**Chain read (actual runtime order, not file order).**

1. `consolidator.py::_detect_deltas` shapes items (no classification).
2. `orchestrator.py` **overwrites** `item.hints = compute_hints(...)` — consolidator’s inline orphan flags are not what Claude sees; `hint_computer.py` recomputes every field.
3. `interpreter.py` sends items + hints into `narrative_prompt.txt`; Claude writes `reconciliation_classifications`.
4. After a passing guardrail: Claude’s class wins; else `_classify_from_hints`.
5. `guardrail.py` only checks `numbers_used`. It cannot create or block a class.

### Guardrail is not the blocker

`verify_guardrail` only checks `numbers_used` against pandas leaves + recon amounts (`max(1% of |ref|, $1_000)`). Classification strings are not numeric. A `structural_explained` label cannot fail the guardrail. Reinforced retry does not re-classify.

### Where the class is supposed to be chosen

Two writers, in order (`interpreter.py` after a successful guardrail pass):

1. Claude: `narrative.reconciliation_classifications[account]` from `narrative_prompt.txt`.
2. Else if the item has no classification: `_classify_from_hints(hints)`.

Consolidator **does not classify**. It emits `ReconciliationItem` with hints; `classification` defaults to `None`.

### Prompt: class 6 exists, but the default kills it

`narrative_prompt.txt` defines `structural_explained` (fees, platform deductions, netting). Hard rule immediately below: **“If unsure, default to missing_je.”** `missing_je` is also defined as “`is_source_only` or `is_gl_only` **or** delta equals a single invoice.” Claude is told “Do not speculate beyond what the hints support.”

Hints in `ReconciliationHints`: `crosses_period_boundary`, `is_round_fraction`, `similar_amount_in_other_account`, `is_source_only`, `is_gl_only`, `delta_matches_known_vendor`. **None maps to structural netting / fees.** There is no `looks_like_processor_fee` (or similar). So even a two-sided fee gap has no pandas signal the prompt is allowed to trust → unsure → `missing_je`.

### Fallback: class 6 is unreachable in Python

Priority in `_classify_from_hints`:

1. `is_gl_only` or `is_source_only` → `missing_je`
2. `crosses_period_boundary` → `timing_cutoff`
3. `similar_amount_in_other_account` → `categorical_misclassification`
4. `is_round_fraction` → `accrual_mismatch` (hint_computer docstring says timing/deposit)
5. else → `stale_reference`

No branch returns `structural_explained`. `delta_matches_known_vendor` exists on the hint object and is described in the prompt’s `accrual_mismatch` example, but the fallback **does not read it**. In the fallback, class 6 is a dead path. If Claude omits a two-sided item, the Python last resort is `stale_reference` — still not class 6.

### Consolidator: inflates the missing_je shape

`_detect_deltas` groups by `(canonical, category)`. If GL and the department file disagree on **category**, the group splits into two one-sided orphans. Each orphan gets `is_gl_only` or `is_source_only`. Those hints are exactly `missing_je` in both the prompt and the fallback.

`_is_material` is effectively `>= $100` (percent gate unused), so small one-sided leftovers become recon items. Sentinel “41 accounts, 32 recon, 28 `missing_je`” is consistent with **orphan flooding**, not with 28 true structural fee gaps that were mislabeled.

### Root cause (not a single line)

- Consolidator: category-split grouping + `$100` floor → many one-sided items whose only hints are `is_*_only`.
- Hints: no fee/netting signal, so a true two-sided structural gap is indistinguishable from “unsure.”
- Prompt: class 6 is documented, then overridden by “unsure → missing_je.”
- Fallback: class 6 has no branch; last resort is `stale_reference`, never `structural_explained`.
- Guardrail: innocent.

**Direct answer to “prompt or consolidator?”** Primary = prompt + missing pandas hint + fallback hole (class 6 cannot fire). Amplifier = consolidator orphans (most of the 28 `missing_je` are this shape; fixing only the fallback will not turn them into `structural_explained`, and should not). A two-sided processor-fee gap that survived grouping would still be classified `missing_je` (Claude, “unsure”) or `stale_reference` (fallback) — never `structural_explained` — until a fee hint exists.

### Fix proposal (do not apply yet)

1. Keep six classes. Do not add a seventh.
2. Pandas: fee-band / netting hint on **two-sided** items only (`hint_computer.py` + `ReconciliationHints`). Numbers for any “expected fee” in prose stay in pandas / `numbers_used`.
3. Fallback: if that hint is set → `structural_explained`. Do not route one-sided orphans there.
4. Prompt: remove or narrow “unsure → missing_je”; unsure + two-sided + no other hint → `stale_reference`. One-sided stays `missing_je`. `structural_explained` only when the fee/netting hint is on.
5. Separately (already Bucket 1 item 1): `_is_material` AND-gate, and consider grouping deltas by `canonical` only so category mismatch becomes one two-sided item (`categorical_misclassification` via `similar_amount_in_other_account`), not two `missing_je`s.

Order if later approved: materiality/grouping first (exception count), then hint + fallback + prompt (class 6 can actually fire). Classifying 28 orphans as structural would be the wrong fix.

---

## Flux via onboarding — bucket

**Decision.** No hardcoded `$10k/10%` / `$5k/5%` in the next implementation. Requirement: onboarding collects **monthly scale** (revenue band or typical monthly revenue). `calculate_variance` derives a dual threshold (dollar floor AND percent) from that scale. Tighter bands on payroll (pattern-tag) and revenue stay rule-based in pandas.

**What exists today.** `companies` has `name`, `sector`, `currency` (`0001_initial_schema.sql`). `CompanySetupForm` posts `{ name, sector }` only (`frontend/src/components/CompanySetupForm.tsx`). No scale field. `comparison.py` uses global `_TIER1_DOLLAR = 50_000` / `_TIER1_PCT = 10` and `_TIER2_DOLLAR = 10_000` / `_TIER2_PCT = 3` — leave them untouched this slice.

**Bucket call: Kova 2**, not Kova 1.

Why not Kova 1:

- Schema: needs `0010_add_company_monthly_scale.sql` (or equivalent) on `companies`. That is `yeni tablo alanı`.
- API / UI: `POST /companies`, `Company` entity, `CompanySetupForm`, Profile. Onboarding is a product surface, not a one-function constant edit.
- “No new engine”: a column + form is not a bank matcher, but it **is** a cross-layer change (migration, repo, API, React). Treating it as a mikro-fix would smuggle a settings product into the recon slice.
- Existing companies: scale is missing; flux would have no input until backfill or a forced re-onboarding.

**Kova 1 remains** only for: `_is_material` (recon, not flux), and the **payroll substring helper** so that *when* scale exists, tighter payroll bands have a deterministic tag. Do **not** retune `_TIER1_DOLLAR` to a new magic number in this slice.

**Suggested later shape (spec only):** onboarding asks for a band (e.g. under $100k / $100–250k / $250–500k / $500k+ monthly revenue), pandas maps band → `{dollar_floor, pct, tight_pct}` in `comparison.py`. Claude never sees the band math.

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

### 2. Flux floors — requirement only; no new constants this slice

**Finding.** Current `comparison.py` Tier 1 `$50k AND 10%` / Tier 2 `$10k AND 3%` is DRONE-scale and too high for a ~$150–250k/month shop. `_TIER2_CATEGORIES` includes `PAYROLL` / `DEFERRED_REVENUE`, which are not seeded, so the tight gate never fires on wages.

**Decision.** Do **not** replace those constants with another hardcoded pair (`$10k/10%`, `$5k/5%`, etc.). Scale is collected at onboarding; pandas derives dual thresholds. See [Flux via onboarding — bucket](#flux-via-onboarding--bucket): **Kova 2** (`0010` + `CompanySetupForm`).

**This slice (Kova 1) only:** payroll substring tag helper (see [PAYROLL pattern — where](#payroll-pattern--where)) so comparison *can* treat wages tighter once scale exists. Leave `_TIER1_*` / `_TIER2_*` untouched until that Kova 2 lands.

**Affects (later).** `comparison.py::calculate_variance`; `companies` via `0010_add_company_monthly_scale.sql`; `CompanySetupForm.tsx`; `POST /companies`.

**Scope now.** `sadece not` + payroll helper as `mikro-fix` when implementation is approved. Full scale-derived flux = `yeni tablo alanı` (Kova 2).

---

### 3. Split “deposit-as-liability” from processor clearing

**Finding.** Customer prepayment / %50 install deposit is a **liability** until work is done (`accrual_mismatch` or a liability-flavored `timing_cutoff` narrative). Processor / Undeposited Funds gap is **not** a liability: FSM books gross, bank pays net of fees. Conflating them produces the worst failure mode for a narrative product.

**Affects.**

- `backend/tools/hint_computer.py` — keep `is_round_fraction` for the 50% deposit pattern; add a pandas hint e.g. `looks_like_processor_fee` when GL is the lower side and `delta_pct` sits in a named fee band (constant, not a Jobber marketing rate in prose).
- `backend/domain/contracts.py::ReconciliationHints` — new optional bool (JSONB, no migration).
- `backend/agents/interpreter.py::_classify_from_hints` — see diagnosis: add a `structural_explained` branch **only** when a fee/netting hint is set; do not reclassify one-sided orphans. `is_round_fraction` should not silently map to `accrual_mismatch`.
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

**Affects.** `frontend/src/components/ReportSummary.tsx` (or close checklist copy); `backend/tools/excel_export.py` attestation line. Optional persist: **`0011_add_bank_attestation.sql`** on `reports` or `runs` (after Kova 2 flux `0010` on `companies`).

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
| Onboarding monthly scale → derived flux dual threshold | `companies` via **`0010_`** (after verified `0009`); `CompanySetupForm`; pandas in `comparison.py`. No magic-number retune. | `yeni tablo alanı` |
| Persist bank attestation | Optional if Bucket 1 display-only is not enough | `0011_add_bank_attestation.sql` (do not reuse flux `0010`) | `yeni tablo alanı` |
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
- Hardcoded flux replacements (`$10k/10%`, `$5k/5%`, …) instead of onboarding scale
- Rebuilding AccountMapper
- Claude-computed fee estimates
- Folding payroll detection into AccountMapper / Haiku

Suggested implementation order **after approval** (not this task):

1. `_is_material` AND-gate (exception count becomes believable)
2. Date-hint restriction + deposit vs fee classification/prompt split (`structural_explained` only with a pandas fee hint; do not relabel consolidator orphans)
3. Payroll substring helper in `backend/tools/` called from `comparison.py` (no category seed, no Haiku)
4. Checklist grouping / KPI strip only after 1–3, or the UI still shows 32 cards

Do **not** in that prompt: hardcoded flux `$10k`/`$5k`; `0010` onboarding scale (separate Kova 2 spec); bank matcher.

Reserve the next migration number(s) for Kova 2: **`0010_add_company_monthly_scale.sql`** (flux) and, if attestation is persisted, **`0011_add_bank_attestation.sql`**. Do not collide two unrelated schema changes into one `0010`. Confirmed: highest on disk is `0009_add_report_type_and_quarterly.sql`.

---

## Mapping back to the research “Recommendations”

| Research rec | Bucket |
|--------------|--------|
| Keep three-way undeposited as flagship | Split: account-level fee hint = 1; full three-way = 2 |
| Recalibrate materiality now | Recon `_is_material` = 1; flux constants = **do not retune**; scale via onboarding = 2 (`0010`) |
| Split deposit-as-liability vs processor clearing | 1 |
| Extend five-tie-out with truck-stock, subcontractor, central-station, RMR count | Subcontractor label = 1; the rest = 2 |
| Design for monthly billing, minimal deferred, no SSP; catch annual-to-revenue | 1 (detect); rollforward ingest = 2 |
| Stage alarm+HVAC first, PS later | 3 (plus ranking already in close-process-by-sector.md) |

---

## Approval checkpoint

Approve or amend before any implementation prompt:

1. PAYROLL helper location: `backend/tools/account_tags.py` + `comparison.py` (not pre-AccountMapper, not consolidator-only). See Direct answers.
2. `structural_explained` diagnosis: primary = no fee hint + fallback hole + prompt “unsure → missing_je”; amplifier = consolidator orphans. Orchestrator overwrites consolidator hints before Claude. Fix proposal accepted or narrowed (prompt-only vs hint+fallback+prompt).
3. Flux scale via onboarding stays **Kova 2** (`0010_add_company_monthly_scale.sql` after verified `0009`); this slice does not write new flux magic numbers. Bank attestation persist, if any, is `0011`.

If item 2 is accepted only as prompt wording (no fee hint yet), still do not default unsure two-sided items to `missing_je`.

No implementation until this checkpoint is explicit.
