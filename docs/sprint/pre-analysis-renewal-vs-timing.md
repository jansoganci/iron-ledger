# Pre-analysis — Renewal / roster dates vs `crosses_period_boundary`

*Planning only. No implementation until this document is approved.*  
*Date: 25 August 2026.*  
*Parent: [field-service-close-triage.md](field-service-close-triage.md) Bucket 1 item 4.*  
*Process: (1) this pre-analysis → approval, (2) implementation as one piece, (3) verification vs this file.*

This is **one piece**. Not PAYROLL. Not deposit vs fee. Not coverage. Not deferred-revenue **rollforward ingest** (Bucket 2). Not a seventh classification.

---

## Direct answer

**The claim is true, with one correction to the example dates.**

`crosses_period_boundary` does **not** look at “the transaction date.” It scans **every object/datetime column** in **every involved source file**. It does **not** use `SourceFileType`. A contracts roster `Last Billed` / renewal / next-bill date after month-end sets the hint to true, and the fallback then stamps **`timing_cutoff`**, which **outranks** `stale_reference`.

The user’s “renews 28 February, period boundary 1 March” example **does not fire** in today’s code: `period_end` is the **last day of the period month** (`2026-03-31` for `period=2026-03-01`), and 28 Feb is not after 31 Mar. The live miss is the **next** cycle date: Sentinel `Last Billed = 2026-04-01` **does** fire.

Correct behaviour: **drop roster/renewal columns from this hint** (and/or skip date-scan on contracts files). Do **not** add `is_contract_renewal` as a coverage-style card. A future renewal date is not a recon finding. The dollar gap on the RMR tie-out, if material, stays **`stale_reference`**.

---

## Scope lock

- Six classes only.
- Pandas-only date logic in `hint_computer.py`.
- No new `SourceFileType`. No bank matcher. No waterfall ingest.
- Do not turn “this roster has an April next-bill date” into a card.

---

## 1. What does the hint actually look at?

### Code (today)

`backend/tools/hint_computer.py::_crosses_period_boundary`:

- Input: `involved_files` (filenames on the item’s `sources`), `source_raw_dfs`, `period_end`.
- `period_end = last calendar day of `period`’s month` (`_period_end`). For March close that is **31 March**, not 1 March.
- Predicate: **any** parsed date in **any** scanned column **>** `period_end`.
- Columns scanned: `df.select_dtypes(include=["object", "datetime64[ns]", "datetime64[ns, UTC]"])`. Not a named `date` field. Integers/floats (typical `amount`) are skipped; object columns that happen to parse as dates are **not**.
- File grain: the **whole file**, not rows for this account. One future cell in the contracts workbook flags Service Revenue.
- Docstring says “transaction date.” The loop does not implement that.

### `SourceFileType`

`backend/domain/contracts.py::SourceFileType` is `general_ledger | payroll | supplier_invoices | contracts`.

`hint_computer.py` **never imports it**. Orchestrator infers type from filename (`_FILE_TYPE_PATTERNS`, including `contract` / `subscription` / `roster`) for AccountMapper only. The cutoff hint cannot treat a contracts file differently from an invoice file.

### What that means in English

| Column shape | Treated as cutoff signal today? |
|--------------|----------------------------------|
| Invoice Date, Payout Date, Settlement Date, Deposit Date | Yes (often correct) |
| Balance Due Date, Due Date | Yes (sometimes correct: cash/invoice due next month) |
| Last Billed, Start Date, renewal, next bill, contract end | Yes if they parse as dates after month-end (**wrong**) |
| Numeric amounts stored as object | `to_datetime` may yield 1970-01-01; not `> period_end`, so usually silent |
| Free text like Harvest `Payout Period` = `"Mar 1-14"` | Can coerce to a **future** datetime (observed **2031-03-01**) and fire — extra footgun of “any object column” |

---

## 2. Concrete fire / no-fire examples

All vs `period_end = 2026-03-31`. Function: `d > period_end`.

| Scenario | Date | Fires? |
|----------|------|--------|
| Claim as written: renewal **28 Feb**, “boundary 1 Mar” | 2026-02-28 | **No** (`False` vs 1 Mar **and** vs 31 Mar) |
| Renewal / last billed **1 Apr** (next cycle) | 2026-04-01 | **Yes** |
| Install **Balance Due Date** 5 Apr / 18 Apr | 2026-04-05, 2026-04-18 | **Yes** (designed cutoff / remaining cash) |
| CableMax **Invoice Date** 3 Apr | 2026-04-03 | **Yes** (real next-period invoice) |
| Vandelay Shopify **Payout Date** 2 Apr | 2026-04-02 | **Yes** (real late payout) |
| Sentinel **Start Date** (2022–2025) | max 2025-12-20 | **No** |

**Sentinel contracts (historical five-file set, `595e0fd`):** columns are `Start Date`, `Last Billed` — **no** `renewal_date` header. `Last Billed` max is **2026-04-01** (five rows share that day). That is enough. This is the roster/next-bill miss, even without a column named renewal.

**Unit test already encodes the wide scan:** `test_crosses_period_boundary_true_when_future_date_present` uses **Balance Due Date** in April, not a txn `date` in April.

---

## 3. If it fires, which class? Mix-up with `stale_reference`?

Fallback today (`interpreter.py::_classify_from_hints`, including deposit/fee order from PR #9):

1. GL-only → coverage (`None`)
2. source-only → `missing_je`
3. `is_processor_fee_gap` → `structural_explained`
4. `is_customer_deposit` / `is_round_fraction` → `timing_cutoff`
5. **`crosses_period_boundary` → `timing_cutoff`**
6. similar amount → `categorical_misclassification`
7. `delta_matches_known_vendor` → `accrual_mismatch`
8. else → **`stale_reference`**

So a two-sided **contracts vs Service Revenue** delta that should be “roster out of date” (`stale_reference`) becomes **`timing_cutoff`** as soon as any Last Billed / next-bill is in April. The date hint **steals** the RMR class. Claude can still pick `stale_reference` if the merge does not force cutoff (unlike deposit/fee, `crosses_period_boundary` is **not** forced over Claude) — but if Claude is unsure, or omitted, Python writes cutoff.

PR #6 Sentinel recount: Service Revenue Δ$285 was designed `stale_reference` (cancelled contracts) and fallback said **`timing_cutoff`** because `Last Billed` hit April. Same bug.

**Bucket 2 deferred-revenue rollforward:** related only as “RMR / prepaid monitoring is not a cutoff.” Do **not** build a waterfall in this slice. Annual cash booked 100% to revenue remains Bucket 1 item 5 (`delta_matches_known_vendor` / `accrual_mismatch`). This slice is **which dates feed the cutoff hint**.

---

## 4. Correct behaviour

**Exclude roster cycle dates from `crosses_period_boundary`. Do not invent a new hint or a coverage card.**

| Option | Verdict |
|--------|---------|
| A. Column allowlist (txn-like names only) | **Do this.** e.g. `date`, `txn_date`, `invoice_date`, `payment_date`, `payout_date`, `settlement_date`, `deposit_date`. |
| B. Column blocklist (`renewal`, `last billed`, `start date`, `end_date`, `next_bill`, `contract_end`) | **Do this too** as belt-and-suspenders; allowlist alone still lets a weird header through if it parses. |
| C. Skip date-scan when filename looks like `contracts` / roster (`_FILE_TYPE_PATTERNS`) | **Optional extra**, still no `SourceFileType` schema change. Stops Last Billed even if someone names it `date`. |
| D. New hint `is_contract_renewal` | **No.** Nothing to classify. Not coverage (coverage = GL line with no supporting file). A future renewal is not “we did not compare.” |
| E. Map renewal → `stale_reference` | **No extra hint needed.** If the cutoff hint stops firing, the existing last-resort / roster template already covers the dollar gap. |
| F. Triage’s blanket “exclude **due**” | **Too blunt.** Sentinel install **Balance Due Date** and Corebuilt **Due Date** are invoice/job due dates — legitimate cutoff. Exclude **Last Billed** / renewal / start / end / next bill, **keep** invoice due / balance due / payout / invoice date. |

Not a seventh class. Not `card_kind=coverage`.

Prompt: one line that cutoff means **transaction or payout dated after close**, not “this customer’s next bill is April.” Optional. Hints stay pandas.

---

## 5. Demo data — is a new company fixture required?

**No new demo company.** The miss is already in Sentinel contracts + the existing unit test. Implementation tests can be a tiny DataFrame (same pattern as deposit/fee: isolated, no Haiku).

| Dataset | Roster/renewal misfire? | Legitimate cutoff still present? |
|---------|-------------------------|----------------------------------|
| **Sentinel contracts** (git `595e0fd`; not all four dept xlsx on every branch) | **Yes:** `Last Billed` 1 Apr. No `renewal_date` column. | Start Date does not fire. |
| **Sentinel install payments** | N/A (due date, not renewal) | **Yes:** Balance Due Date Apr 5/18. Keep. |
| **Sentinel suppliers** | No | **Yes:** Invoice Date 3 Apr (CableMax). Keep. |
| **Vandelay Shopify** | No | **Yes:** Payout Date 2 Apr. Keep. |
| **Harvest settlements** (in-tree) | `Payout Period` text coerced to 2031 | **Also** Deposit Date 2–3 Apr (real). Allowlist would drop the 2031 garbage. |
| **DRONE** | Not used here | Out. |
| **Corebuilt subs** | Due Date into April/May | Invoice Date 3 Apr is real; Due Date is invoice due — keep if we keep “due” for AP. |

Isolated pytest fixture is enough: (1) contracts-shaped `Last Billed=2026-04-01` → hint **false** after the fix; (2) invoice `Invoice Date=2026-04-03` → hint **true**; (3) Feb 28 renewal → still **false**.

---

## 6. Files / schema

| File | Change? |
|------|---------|
| `backend/tools/hint_computer.py` `_crosses_period_boundary` | **Yes.** Allowlist + blocklist on **header names**. Optionally skip files whose stem matches contracts/roster patterns. Do not log cell values. |
| `tests/tools/test_hint_computer.py` | **Yes.** Last Billed April → false; Invoice Date / Payout Date April → true; Balance Due Date decision per §4 (recommend **still true**). Feb 28 → false. |
| `backend/agents/interpreter.py` | **No** order change required if the hint stops lying. Cutoff still outranks stale_reference **when the hint is a real txn date**. |
| `backend/prompts/narrative_prompt.txt` | **Optional** one sentence: cutoff ≠ next bill on a roster. |
| `backend/domain/contracts.py` | **No.** Do not add `is_contract_renewal`. Do not extend `SourceFileType`. |
| `backend/agents/consolidator.py` | **No.** |
| Frontend | **No.** |

**Migration:** none. Hint is already JSONB on the item. Highest SQL file stays `0009`.

---

## 7. Risk and rollback

| Risk | Why | Mitigation |
|------|-----|------------|
| Install demo loses cutoff | Blanket exclude of `due` | Keep Balance Due Date / invoice due; only drop roster names. |
| Contracts file uses a column literally named `date` for next bill | Allowlist would still fire | Optional filename skip for `contract` / `roster` / `subscription`. |
| Claude still writes cutoff | Prompt + dates in the payload | After pandas hint is false, fallback is `stale_reference` unless another hint wins. Do not need to force-clear Claude unless QA shows it; not this slice’s coverage-style override unless we see it in tests. |
| Harvest 2031 | `format="mixed"` on text periods | Allowlist drops `Payout Period`. Do not parse every object column. |
| False negative: real April invoice | Too-tight allowlist | Include invoice / payout / settlement / payment / deposit / txn `date`. |

**Rollback:** revert the allowlist/blocklist in `_crosses_period_boundary`. No migration. Old reports keep whatever hint was stored in JSONB.

---

## Before / after (if later approved — do not apply now)

**Sentinel Service Revenue** (GL $3,540 vs contracts $3,825, Δ$285, `Last Billed` 1 Apr on cancelled rows):

| | Today | After |
|--|-------|-------|
| `crosses_period_boundary` | **True** (Last Billed) | **False** |
| Fallback | `timing_cutoff` | `stale_reference` (no other hint) |
| Narrative | “Will clear next month” (wrong) | Roster out of date / cancelled still billed |

**Sentinel Installation Revenue** (Balance Due Date in April):

| | Today | After |
|--|-------|-------|
| Hint | True | **True** if Balance Due Date stays allowed |
| Class | `timing_cutoff` | `timing_cutoff` (unchanged on purpose) |

**Feb 28 renewal:**

| | Today | After |
|--|-------|-------|
| Hint | False already | False |

---

## Approval checkpoint

Approve or amend before any implementation prompt:

1. Allowlist txn-like headers + blocklist roster/renewal/`Last Billed`/`Start Date`. **Keep** invoice/payout/deposit/**balance due**. Do **not** blanket-drop every `due`.
2. No `is_contract_renewal` hint. No coverage card. No `SourceFileType` change. No migration.
3. Optional contracts-filename skip. Optional prompt sentence. Interpreter order unchanged.
4. Tests: isolated DataFrames; Sentinel Last Billed is the regression; Feb 28 stays false.

No implementation until this checkpoint is explicit.
