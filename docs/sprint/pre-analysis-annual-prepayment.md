# Pre-analysis — Annual prepayment vs `accrual_mismatch` (delta × 12)

*Planning only. No implementation until this document is approved.*  
*Date: 26 August 2026.*  
*Parent: [field-service-close-triage.md](field-service-close-triage.md) Bucket 1 item 5.*  
*Code read on this branch (`main` + prior **docs** PRs). Fallback wiring after deposit/fee (PR #9) is cited as stacked state, not as code on this branch.*  
*Process: (1) this pre-analysis → approval, (2) implementation as one piece, (3) verification vs this file.*

This is **one piece**. Not PAYROLL. Not deposit vs fee. Not cutoff allowlist. Not a deferred-revenue **rollforward ingest** (Bucket 2). Not a seventh classification.

---

## Direct answer

**A pandas “× 12” hint exists. It does not implement the scenario in the assignment, and it is unsafe to leave as-is.**

| Question | Answer |
|----------|--------|
| Is there a mechanism? | Yes: `ReconciliationHints.delta_matches_known_vendor` in `hint_computer.py`. Formula: **`abs(delta) × 12 ≈ some *other* account’s consolidated total ±10%`**. |
| Does it mean “this GL lump is 12 months of that source”? | **No.** It never compares this item’s GL amount to this item’s monthly source. It never uses `comparison.py` history. The name “known vendor” is a lie — there is no vendor match. |
| Is it bound to `accrual_mismatch`? | **Prompt yes; fallback depends on the stack.** Prompt class 5 is the prepaid-asset template. On **this branch / `main`**, `_classify_from_hints` does **not** read `delta_matches_known_vendor` (only `is_round_fraction` → `accrual_mismatch`). After **PR #9**, fallback maps the hint → `accrual_mismatch`. Merge still does **not** force it over Claude (unlike deposit/fee). |
| Does it work on a real annual prepaid? | The **unit test** works (`delta=$1,100` vs another row `$13,200`). Same-account “GL $13,200 vs source $1,100” would **not** fire (`1,100×12=$13,200` is compared to *other* rows, and the `$13,200` row is skipped because it is the same account). |
| Does it fire on Sentinel today? | **Hint yes; class steal only after later PRs.** Service Revenue Δ$285 → `$285×12=$3,420` matches **Payroll Taxes $3,675** (7.5%) and **Rent $3,200** (6.4%). Counted in the class-6 refresh table. On `main`, cutoff still outranks it (`Last Billed` → `timing_cutoff`). After **PR #11** (roster dates ignored) **and** **PR #9** (fallback reads this hint), Python can stamp **`accrual_mismatch`** on a cancelled-contract `stale_reference`. |

So: the Kova 1 “mikro-fix” is not “add delta×12 from scratch.” It is **replace the formula**, **stop scanning the whole P&L**, **emit the monthly number in pandas**, and **keep one existing class**.

---

## Scope lock

- Six classes only. `accrual_mismatch` stays the label.
- Pandas computes every ratio and the implied monthly / annual figures. Claude does **not** divide by 12 (golden rule). Those figures must appear on the item / `numbers_used`.
- No waterfall, no SSP, no new `SourceFileType`, no `0010` migration.
- Do not treat GL-only coverage (e.g. Sentinel Software Subscriptions $615) as an annual prepaid.

---

## 1. What exists today

```python
# hint_computer.py::_delta_matches_known_vendor
annual_equivalent = abs(item.delta) * 12
# skip item.account, then:
# |other_account.amount - annual_equivalent| / annual_equivalent <= 0.10
```

Tolerance: `_ANNUAL_MATCH_TOLERANCE = 0.10`.

Docstring example is **internally wrong**: “GL $13,200, delta vs expected $12,100, ×12 ≈ $13,200.” `$12,100×12=$145,200`. The **test** is the real spec: delta `$1,100` × 12 = `$13,200` on a **different** account named “HubSpot Annual Invoice.”

`comparison.py` historical averages are a different agent. Not an input to this hint.

On this branch, `_classify_from_hints` never reads the bool. The prompt still describes the prepaid-asset story, so Claude *can* emit `accrual_mismatch` without Python forcing it.

---

## 2. When it fires, which class, does it work? (concrete)

**Happy path (synthetic, already in `test_delta_matches_known_vendor_annual_pattern`).**

- Item: SaaS Subscriptions, `delta=$1,100`
- Consolidated: HubSpot Annual Invoice `$13,200`
- Hint **true**. On this branch, fallback **ignores** the hint → `stale_reference` unless `is_round_fraction`. After PR #9: fallback `accrual_mismatch`.
- Prompt template: lump-sum, prepaid **asset**, amortize — vendor-expense story

**Same-account annual vs monthly (the assignment).**

- GL Software `$13,200`, source monthly `$1,100`, same account
- `delta = 1,100 − 13,200 = −12,100`
- `abs(delta)×12 = $145,200` ≠ `$13,200`
- Other P&L lines almost never equal `$145,200`
- **Hint false.** The intended SMB miss is undetectable.

**Sentinel Service Revenue (false positive, counted).**

- Two-sided: GL `$3,540` vs contracts `$3,825`, Δ `$285` (cancelled still billed)
- `$285×12=$3,420` vs Payroll Taxes `$3,675` and Rent `$3,200` — both inside 10%
- Designed class: `stale_reference`
- **Today (`main`):** hint true, but fallback is `timing_cutoff` because `Last Billed` is in April. Claude can still pick prepaid from the prompt.
- **After PR #11 + PR #9:** `crosses_period_boundary` false → fallback reads this hint → **`accrual_mismatch`** (“create a prepaid asset”) — nonsense for cancelled monitoring

**Vandelay Software Subscriptions.**

- GL `$2,300` vs Amazon Helium10 line `$1,800` (labeled annual in a description column)
- Ratio `2,300/1,800≈1.28`, not 12. `abs(delta)×12=$6,000` may still match some other OPEX line (e.g. Warehouse Rent `$6,500` is 8.3%). False-positive risk, not a true 12× prepaid.

**Conclusion.** Wired to the right **class**, wrong **signal**. Unsafe on live Sentinel.

---

## 3. How the hint should be built

Compare the **two sides of this recon item**, not a hunt across accounts.

Let `G = |gl_amount|`, `S = |non_gl_total|`. Two-sided only (`not is_gl_only`, `not is_source_only`).

**Fire when one side is ~12× the other ±10%** (same tolerance constant, or tighten to 5% if tests stay green):

- `G / S ∈ [12×0.9, 12×1.1]` or `S / G` in that band (whichever side is the lump)
- Absolute floors: both sides ≥ `$100`, `|delta|` already material from consolidator (`$500` hard or `$100`+pct)
- Skip if `is_customer_deposit` or `is_processor_fee_gap` (50% and 3–8% bands do not overlap 12×)

Implied monthly = `max(G,S) / 12` — **pandas**, stored on the item (e.g. `implied_monthly` in JSONB hints or a recon field). Prompt may only repeat that number.

Optional extra (not required for v1): description/header token `annual` / `12-month` on the involved file, same closed-list style as deposit columns. Do not log values.

Do **not** keep “delta × 12 ≈ random other account.” That is the false-positive engine. The HubSpot unit test must be rewritten to same-account `$13,200` vs `$1,100`.

Quarterly (`×4`): out of this slice unless a fixture exists. One band, one story.

---

## 4. Same model as deposit / fee? **Yes.**

| | Deposit / fee (PR #9) | This slice |
|--|----------------------|------------|
| New class? | No | No — `accrual_mismatch` already exists |
| Discriminator | JSONB bools | Keep/repurpose `delta_matches_known_vendor` **or** rename to `looks_like_annual_prepayment` (optional; rename is clearer, default `False` still JSONB) |
| Pandas | ratio / fee band | 12× same-item ratio + implied monthly |
| Fallback | force class | **Force** `accrual_mismatch` when the hint is on (today Claude can ignore it) |
| Prompt | two templates | Two templates **under the same class**: expense lump → prepaid asset; revenue lump → unearned / defer. Do not use the deposit 50% template. Do not use class 6. |

**Why not a new bool plus keeping the old formula?** The old formula should die. One hint, one definition.

**Why not `is_customer_deposit`?** That is 50% job peşinat / `timing_cutoff`. Annual monitoring cash in revenue is a **12× lump**, different speech act, different class.

---

## 5. Boundary vs Bucket 2 rollforward — do not overbuild

| This slice (Kova 1) | Not this slice (Kova 2) |
|---------------------|-------------------------|
| One period, two file totals, ratio ~12 | Opening + billings − recognized = close |
| “This month’s GL looks like a full year of the source run-rate” | ASC 606 / SSP / membership double-count at row grain |
| One implied monthly number from pandas | Waterfall schedule ingest |
| Catch **absence** of amortization | Assume the dealer keeps a rollforward |

**Scope-creep risk.** If implementation starts allocating remaining 11 months, posting a JE, or reading a deferred-revenue schedule, stop. Success is: the card says prepaid/unearned and shows pandas’ monthly figure. The books are not rewritten.

Triage already forbade ServiceTitan double-recognition here (row identity is gone after groupby). Still forbidden.

---

## 6. Demo data vs isolated fixture

**Isolated fixture.** Same reason as deposit/fee: Sentinel/Vandelay/DRONE do not contain a clean same-account 12× pair.

| Dataset | Annual prepaid 12×? |
|---------|---------------------|
| Sentinel five-file | **No.** Software $615 is GL-only coverage. Service Revenue Δ$285 is roster, and is a **false positive** on the current formula. |
| Vandelay | Helium10 “annual” **description** vs GL `$2,300` / source `$1,800` — not 12×. |
| DRONE | Single-file P&L historically; not this recon. |

Fixture (hand-crafted `ReconciliationItem`, no xlsx):

- GL Software Subscriptions `$13,200`, vendor file `$1,100`, same account → hint true, class `accrual_mismatch`, implied monthly `$1,100`
- Negative: Service Revenue Δ`$285` vs a P&L that includes Rent `$3,200` → hint **false**
- Negative: 50% deposit `$4,000/$8,000` → still deposit, not annual
- Negative: fee band 5.74% → still fee, not annual

---

## 7. Files / schema

| File | Change? |
|------|---------|
| `backend/tools/hint_computer.py` `_delta_matches_known_vendor` | **Yes.** Same-item 12×; stop other-account scan. Optionally rename. Emit implied monthly (field on hints or item). |
| `backend/domain/contracts.py` | **Maybe.** Rename or add `implied_monthly: float \| None`. No change to `ReconciliationClassification`. |
| `backend/agents/interpreter.py` | **Yes.** Force class when hint is on (coverage/deposit style). Keep below fee/deposit/cutoff in the order. |
| `backend/prompts/narrative_prompt.txt` | **Yes.** Use pandas implied monthly only. Revenue vs expense wording. Never ask Claude to divide. |
| `tests/tools/test_hint_computer.py` | **Yes.** Rewrite HubSpot as same-account 12×; add Sentinel $285 negative. |
| `tests/agents/test_interpreter_classify.py` | **Yes.** Force over Claude `stale_reference`. |
| Isolated fixture module | **Yes.** Like `deposit_vs_fee_fixture.py`. |
| `consolidator.py` | **No.** |
| Frontend | **No** required. |
| SQL migration | **No.** JSONB. Highest file stays `0009`. |

---

## 8. False positives — how to bound them

The current “any other account ≈ 12× delta” rule **will** label real one-off spend as annual prepaid whenever some unrelated line is ~12× the gap (Sentinel $285 is the proof).

Limits for the new rule:

1. **Same item only** — no P&L-wide search.
2. **Two-sided** — GL-only $13,200 with no invoice is coverage, not prepaid.
3. **Ratio band around 12**, not around 2–3 (that is a big invoice, not a year).
4. **Do not fire** if deposit or fee hints are on.
5. **Optional name/token** (`annual`, `12 mo`, `subscription`) if QA still sees FPs — closed list, no value logging.
6. **Do not use** `comparison.py` history in v1 (mixes flux with recon).

Residual risk: a true one-off that is coincidentally 12× the other source’s total on the **same** account (rare). Accept; prompt says “appears to be” and asks the user to prepaid/defer, not auto-post.

---

## 9. Risk and rollback

| Risk | Why | Mitigation |
|------|-----|------------|
| Sentinel Service Revenue → prepaid asset | Old formula × Rent / Payroll Taxes | Delete other-account scan; regression test Δ$285 |
| Claude invents `$1,100` | Template “expected monthly” | Pandas `implied_monthly` in recon payload + `numbers_used` |
| Claude arithmetic | Prompt “÷12” | Forbidden. Number is precomputed. |
| Customer annual cash vs vendor expense | One class, two balance-sheet sides | Two prompt templates; still `accrual_mismatch` |
| Scope creep into waterfall | “Remaining 11 months” | Explicit non-goal |
| Rename breaks old JSONB | `delta_matches_known_vendor` in stored reports | Keep old field as alias **or** accept default `False` on old rows |

**Rollback:** revert hint formula + force-merge + prompt. No `DOWN` migration.

---

## Before / after (if later approved — do not apply now)

**HubSpot-shaped same account (new fixture):**

| | Today | After (if approved) |
|--|-------|-------|
| Hint | False (same-account skip) | True |
| Fallback class | `stale_reference` on `main`; `accrual_mismatch` after PR #9 only if some *other* line matches | `accrual_mismatch` (forced) |
| Number in prose | Invented or missing | pandas `$1,100` |

**Sentinel Service Revenue Δ$285:**

| | `main` | After #9+#11, old formula | After this slice |
|--|-------|---------------------------|------------------|
| Hint | **True** (vs Rent / Payroll Taxes) | **True** | **False** |
| Fallback class | `timing_cutoff` (`Last Billed`) | `accrual_mismatch` | `stale_reference` |

---

## Approval checkpoint

Approve or amend before any implementation prompt:

1. Replace other-account `delta×12` with **same-item 12×** (GL vs source). Kill the P&L hunt.
2. Same JSONB + existing `accrual_mismatch` model as deposit/fee. Force class when hint is on. Pandas emits implied monthly. No 7th class, no migration, no rollforward.
3. Isolated fixture; Sentinel $285 is a **negative** test, not a demo of success.
4. Optional rename `looks_like_annual_prepayment`; optional `annual` token. Quarterly ×4 out of slice.

No implementation until this checkpoint is explicit.
