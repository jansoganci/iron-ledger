# Pre-analysis — Customer deposit vs processor fee/netting

*Planning only. No implementation until this document is approved.*  
*Date: 25 August 2026.*  
*Parent: [field-service-close-triage.md](field-service-close-triage.md) Bucket 1 item 3.*  
*Depends on: class-6 GÜNCELLEME (PR #6) for Sentinel recount; coverage cards (PR #4) for GL-only behaviour.*  
*Process: (1) this pre-analysis → approval, (2) implementation as one piece, (3) verification vs this file.*

This is **one piece**. Not PAYROLL. Not `_is_material`. Not grouping-by-canonical. Not three-way FSM ↔ processor ↔ bank matching (Bucket 2). Not a seventh classification.

---

## Direct answer

**Today the two situations are not distinguished.** They are not even handled the same way. They are handled **hardly at all**, and the one pandas signal that exists points at the **wrong** class.

| Situation | What it is | What the product should say | What happens today |
|-----------|------------|-----------------------------|--------------------|
| Customer deposit | 50% install peşinat; iş bitene kadar liability, gelir değil | Timing / unearned revenue. Expect the rest next month. Do **not** call it a fee. | Weak ratio hint (`is_round_fraction`) that **does not fire** on the real Sentinel install file. If it did fire, fallback would stamp **`accrual_mismatch`** (vendor prepaid-expense template). Prompt `timing_cutoff` can still be guessed by Claude from dates. |
| Processor / undeposited netting | GL brüt, banka/payout net; kart-ACH kesintisi | `structural_explained`. Not a liability. No “expect reversal as deferred revenue.” | **No pandas hint.** Fallback cannot emit class 6. Prompt has a class-6 template but “unsure exception → `missing_je`.” |

Conflating them is still the worst narrative failure. The current code does not conflate them in production because **neither path really fires**. The risk is in the *next* implementation if deposit and fee are both hung off `is_round_fraction` / `accrual_mismatch` / a class-6 subtype.

---

## Scope lock

- Six `ReconciliationClassification` values only.
- Discriminators live on `ReconciliationHints` (JSONB), same pattern as `is_gl_only` / `card_kind`.
- Pandas computes every number and every hint. Claude writes two **different** templates. Guardrail still checks `numbers_used` only.
- No new `SourceFileType` (no bank, no processor). Account-level two-sided delta only.
- Do not relabel GL-only coverage as fees. Do not relabel the four Sentinel exceptions as class 6.

---

## 1. Is the customer-deposit pattern detected in pandas?

**Partially designed, not detected on the real file, and wired to the wrong fallback class.**

### Consolidator

`consolidator.py` never looks at payment type, balance remaining, “50% Deposit”, or job status. It sums `account` / `amount` / `source_file`. Sentinel install rows (`Payment Type = 50% Deposit`, `Balance Remaining = 4000 / 3000`) are flattened to one account total: **Installation Revenue $16,500**.

### Hint

`hint_computer.py::_is_round_fraction`: `non_gl_total / gl_amount ≈ 0.50 ± 5%`. Docstring: “50% deposit or advance — timing signal.”

On Sentinel (Reconstruction A, PR #4 stack): GL $15,000 vs payments $16,500 → ratio **1.10**, not 0.50. Hint is **false**. Unit test `test_is_round_fraction_false_installation_demo` already records this: `11000/15000 = 0.733` is also false. The 50% pattern exists **per job**, not at the account total the consolidator emits.

`hint_computer` already receives `source_raw_dfs`. It does **not** scan `Payment Type`, `Balance Remaining`, or “deposit” in those frames. That is the unused signal.

### Fallback vs prompt

| Layer | Deposit behaviour |
|-------|-------------------|
| `_classify_from_hints` | `is_round_fraction` → **`accrual_mismatch`** (after coverage / source-only / period-boundary / similar-amount). |
| `narrative_prompt.txt` `accrual_mismatch` | Annual software invoice → prepaid **asset**, amortize. Vendor expense. **Opposite** of a customer liability. |
| `narrative_prompt.txt` `timing_cutoff` | “Expect this to clear next month.” Closer, but never says unearned revenue / not yet earned. |
| `narrative_prompt.txt` `structural_explained` | Fees / netting. Must not be used for deposits. |

On the live Sentinel item, `crosses_period_boundary` is **true** (balance due April), so fallback returns **`timing_cutoff`** and never reaches `is_round_fraction`. Deposit is classified as cutoff **by accident of dates**, not because pandas recognized a peşinat.

**Conclusion.** Deposit is not a first-class pandas pattern today. It is a ratio that misses the demo file, a fallback that would call it a vendor accrual if the ratio ever hit, and otherwise Claude + date hint.

---

## 2. Is there a processor / fee-netting hint? (re-verify Bank Charges)

**No fee hint. The Sentinel $95 line is still not a two-sided fee gap.**

`ReconciliationHints` fields: `crosses_period_boundary`, `is_round_fraction`, `similar_amount_in_other_account`, `is_source_only`, `is_gl_only`, `delta_matches_known_vendor`. None is a fee band, gross-vs-net, or merchant-processing flag.

`_classify_from_hints` has **no** `structural_explained` branch. Last resort is `stale_reference`.

### Sentinel — still valid

From the 25 Aug 2026 recount (same five-file set as PR #6):

- Only processor-shaped GL line: **Bank Charges $95**, description “Merchant processing fees”.
- PR #2 AND-gate: `|delta| < $100` → **not an item**.
- Even at $100+: GL-only → PR #4 `card_kind=coverage`, not class 6. No bank/payout file in the set, so it cannot be two-sided netting.
- Four two-sided exceptions: 0 fee/netting (COGS invoice, install deposits, wages bonus, cancelled contracts).

### Vandelay (in `docs/demo_data/vandelay/` on this docs lineage)

Fees are **separate OPEX accounts**, not a sales-vs-bank netting on one revenue line:

- `Amazon Seller Fees` GL $13,845 = settlement `FEE-AMZ` $13,845 (match).
- `Shopify Payments Fees` GL $5,420 vs payouts `FEE-MAR` $5,500 (Δ $80, under $100).
- `Product Sales — Shopify` GL $184,500 vs payouts Gross including 2 Apr payout $4,200 → timing, not a fee band on purpose.
- `Bank Charges` $95 again.

The hackathon class-6 example (BlueLine bank $57.5k vs sales $61k) is **not** in this repo’s demo files.

### Harvest (in-tree, not Sentinel)

`harvest_delivery_settlements_mar_2026.xlsx` has Gross / Platform Commission / Net Payout columns. GL has `Delivery Platform Fees $8,940`. That netting lives **inside one settlement file**, which consolidator does not compare column-to-column. Turning that into class 6 without a new grain is Bucket 2 (three-way / intra-file netting). Out of this piece.

**Conclusion.** Account-level two-sided fee gap: **no current signal, no current fixture that produces one.** Bank Charges $95 diagnosis is still correct.

---

## 3. Recommended split — two hints, two existing classes

**Two pandas bools. Not one class with a subtype. Not both under `accrual_mismatch`.**

| Hint (new or retargeted) | When pandas may set it | Fallback class | Prompt speech act |
|--------------------------|------------------------|----------------|-------------------|
| `is_customer_deposit` (replace or wrap `is_round_fraction`) | Two-sided. Ratio ~50% **or** involved source file has deposit/balance-remaining language on that account. | `timing_cutoff` | Liability until work is done; not a fee; expect remaining payment / recognition next period. |
| `is_processor_fee_gap` | Two-sided only. `delta_pct` in a named pandas fee **band** (constant in Python, never “2.9%” in the prompt). Not a deposit hint. Not GL-only. | `structural_explained` | Gross vs net / platform deduction. No deferred-revenue story. No action. |

**Why two hints, not “use the classes as-is.”** Classes are the label Claude prints. Without a hint, Claude is told not to speculate and defaults exception → `missing_je`. Classes already exist; the missing piece is the pandas discriminator — same reason coverage needed `is_gl_only` / `card_kind` rather than hoping Claude would skip `missing_je`.

**Why not park deposits under `accrual_mismatch`.** That class already means “annual vendor invoice expensed in full” (`delta_matches_known_vendor` + prepaid-asset template). Customer unearned revenue is a different balance-sheet side. Reusing the class repeats the coverage-under-class-6 mistake: one badge, two meanings.

**Why not park deposits under `structural_explained`.** Class 6 means “not an error, no action, fees/netting.” A 50% peşinat booked as revenue **is** an error (or at least a cutoff to watch). “No action required” is wrong if the shop recognized the full job as income.

**Why not a seventh class.** Locked. Two speech acts already have homes: cutoff vs explained.

Keep `is_round_fraction` as the implementation of the ratio half of `is_customer_deposit`, or rename in the same PR. Stop mapping it to `accrual_mismatch`.

Fallback order (after coverage / source-only):

1. `is_processor_fee_gap` → `structural_explained`
2. `is_customer_deposit` / `is_round_fraction` → `timing_cutoff` (**not** accrual)
3. `crosses_period_boundary` → `timing_cutoff`
4. `similar_amount_in_other_account` → `categorical_misclassification`
5. `delta_matches_known_vendor` → `accrual_mismatch` (wire this; today fallback ignores it)
6. else → `stale_reference`

Fee band and 50% ratio do not overlap. Timing-before-fee would steal a true fee gap that also has a stray date column; **fee-before-dates** is the safer order once the hint is tight and two-sided-only. Wide date scanning (Bucket 1 item 4) is a separate slice; do not wait for it if the fee hint is narrow.

---

## 4. Does this break the six-class taxonomy?

**No.** Same move as coverage: extra JSONB fields, Literal unchanged.

| | Coverage (PR #4) | This slice |
|--|------------------|------------|
| New class? | No | No |
| Discriminator | `card_kind` + `is_gl_only` | `is_customer_deposit` + `is_processor_fee_gap` |
| Exception class used | none (null) | `timing_cutoff` / `structural_explained` |
| Frontend | separate badge/section | existing badges; **copy** must follow the template for that class (deposit ≠ “platform fees”) |

Do **not** add `subtype: deposit | fee` under one classification. Coverage rejected parenting two speech acts under class 6; do not do it here either.

---

## 5. Files / functions

| File | Change? |
|------|---------|
| `backend/domain/contracts.py` `ReconciliationHints` | **Yes.** Add `is_customer_deposit: bool = False` and `is_processor_fee_gap: bool = False` (or keep `is_round_fraction` as the deposit ratio and add only the fee bool — pick one naming scheme in the implementation prompt). No change to `ReconciliationClassification`. |
| `backend/tools/hint_computer.py` | **Yes.** Compute both. Deposit: existing ratio **plus** optional scan of involved `source_raw_dfs` headers/values for deposit / balance remaining (column names only + boolean/category match; **do not log cell PII**). Fee: two-sided; `abs(delta_pct)` in a pandas constant band; skip if deposit hint is on; skip `is_gl_only` / `is_source_only`. |
| `backend/agents/interpreter.py` `_classify_from_hints` | **Yes.** Order in §3. Remove `is_round_fraction` → `accrual_mismatch`. |
| `backend/prompts/narrative_prompt.txt` | **Yes.** Two templates. (a) deposit → cutoff / liability, not fee, not prepaid expense. (b) class 6 **only** when `is_processor_fee_gap`. Unsure two-sided + no hint → `stale_reference` (already recommended in PR #6). Never “2.9% + 30¢” in the prompt. |
| `backend/agents/consolidator.py` | **No** grouping/materiality change. It already emits two-sided items; hints run after. |
| `backend/tools/guardrail.py` | **No.** Fee dollars in prose must already be recon `delta` / source amounts so `numbers_used` matches. |
| `tests/tools/test_hint_computer.py` | **Yes.** Ratio true/false (existing). Sentinel-shaped install totals must stay false on ratio-only; true if deposit-column signal is added. Fee band two-sided true; GL-only Bank Charges $95 false; 50% ratio must not set fee. |
| `tests/agents/test_interpreter_classify.py` | **Yes.** Fallback: deposit → `timing_cutoff`; fee → `structural_explained`; neither → not class 6. |
| Frontend / excel | **No** required in this piece if templates ride existing class badges. Optional copy QA only. |

**Do not touch:** AccountMapper, `account_categories`, `comparison.py`, coverage `card_kind`, `_is_material`, bank matcher.

---

## 6. Schema / migration

**None.** `reports.reconciliations` is JSONB. New hint bools default `False`; old rows omit them. Highest migration stays `0009`. Same as coverage. Do not add `0010` for this.

---

## 7. Test / fixture plan

| Dataset | Customer deposit? | Processor two-sided fee gap? | Use as |
|---------|-------------------|------------------------------|--------|
| **Sentinel** five-file (git `595e0fd`, install + GL) | **Yes, at row level.** Account-total ratio **no.** Fallback today: `timing_cutoff` via dates. | **No.** Bank Charges $95 dropped / GL-only. | Deposit detection tests. Regression: do not classify the 16 coverage or the other 3 exceptions as class 6. |
| **Vandelay** (in-tree) | No | **No** as designed. Fees are separate accounts that match or sit under $100. Shopify sales Δ is the 2 Apr payout (timing). | Negative tests: matching fee **accounts** must not become `structural_explained` on **sales**. |
| **DRONE** | Not in this tree’s `docs/demo_data/` (single-file P&L historically). | No | Out. Variance-only. |
| **Harvest** settlements | No | Intra-file Gross vs Net / commissions. Not consolidator-shaped. | Do **not** pretend this slice reads commission columns. Later grain. |
| **BlueLine $61k vs $57.5k** | — | Documented only in `docs/06-reports/hackathon_findings_report.md`. **Files absent.** | If class 6 must be demoed, **add a small golden fixture** (two DataFrames, same account, Δ in the fee band). Do not invent a bank `SourceFileType`. |

Implementation tests can be hand-crafted `ReconciliationItem`s (how `test_hint_computer.py` already works). A committed two-row fee fixture is required before claiming “class 6 fires in demo.” Sentinel alone will still show **0** class-6 cards after this slice — that is expected (PR #6).

---

## 8. Risk and rollback

| Risk | Why | Mitigation |
|------|-----|------------|
| Fee band false-positive on timing (Vandelay Apr payout ~2%) | A 1–8% band looks like Shopify fees **and** like one late payout | Two-sided + band is not enough: require the deposit hint off; prefer fee **before** dates only if band is combined with a name/column signal (`fee`, `commission`, `payout net`) or a second source that is a payout file. If unsure, **do not** set the fee hint. |
| Deposit ratio false-positive | Any 50% gap (not a peşinat) | Prefer deposit-column / “50% Deposit” signal; keep ratio as fallback only when two-sided. |
| Claude still writes class 6 on coverage or deposits | Prompt still has the fee template | Interpreter: ignore Claude class 6 unless `is_processor_fee_gap`. Same pattern as coverage clearing `missing_je`. |
| Claude writes prepaid-asset copy on a deposit | Today’s `accrual_mismatch` template | Fallback must not map deposit → accrual. Prompt: deposit template is cutoff/liability only. |
| Sentinel card count surprise | People expect class 6 to eat the old 28 | It will not. Coverage already took 16. Remaining 4 are not fees. |
| PII in deposit-column scan | Customer names sit next to Payment Type | Match column **headers** and a closed list of payment-type tokens. Do not log values. |
| Guardrail | Claude invents 2.9% | Prompt ban (Bucket 1 item 9). Prose uses pandas `delta` only. |

**Rollback:** revert the hint fields + fallback order + prompt templates. JSONB old reports without the new bools render as today. No `DOWN` migration.

---

## Before / after (if later approved — do not apply now)

**Sentinel Installation Revenue** (GL $15,000, payments $16,500, two 50% deposits, balance due April):

| | Today | After this slice |
|--|-------|------------------|
| Hints | `crosses_period_boundary=True`, `is_round_fraction=False` | Also `is_customer_deposit=True` if column signal is built; still `is_processor_fee_gap=False` |
| Fallback | `timing_cutoff` (dates) | `timing_cutoff` (deposit hint, not accrual) |
| Narrative | Cutoff template, or Claude unsure → `missing_je` | Liability / remaining balance template. Not “platform fees.” Not “amortize a prepaid.” |

**Sentinel Bank Charges $95:**

| | Today | After |
|--|-------|-------|
| Item | None (AND-gate) | None. Do not resurrect as class 6. |

**Hand-crafted two-sided fee fixture** (GL sales $61,000, payout net $57,500, same account):

| | Today | After |
|--|-------|-------|
| Fallback | `stale_reference` (or Claude `missing_je`) | `structural_explained` |
| Narrative | Missing JE / stale list | Fees deducted before deposit. No action. Not a customer prepayment. |

---

## Approval checkpoint

Approve or amend before any implementation prompt:

1. Two hints (`is_customer_deposit` / `is_processor_fee_gap`), two existing classes (`timing_cutoff` / `structural_explained`). No seventh class. No subtype under class 6. No deposit → `accrual_mismatch`.
2. Sentinel Bank Charges $95 stays out. Class 6 is allowed to remain **zero** on Sentinel until a dedicated two-sided fixture exists.
3. Consolidator untouched. No bank `SourceFileType`. No migration.
4. Interpreter clears Claude’s `structural_explained` unless the fee hint is on (coverage-style).

No implementation until this checkpoint is explicit.
