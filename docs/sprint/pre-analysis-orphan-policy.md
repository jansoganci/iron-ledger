# Pre-analysis — Orphan policy (GL-only / source-only)

*Planning only. No implementation until this document is approved.*  
*Date: 24 August 2026. Revised same day: visibility addendum — do not silently drop GL-only cards.*  
*Parent: [field-service-close-triage.md](field-service-close-triage.md).*  
*Independent of Slice 1 code. Do not land in the same PR as the `_is_material` AND-gate.*

Question: when a GL account has no matching subledger file (GL-only), or a subledger line has no GL counterpart (source-only), today’s pipeline labels it `missing_je`. Is that correct, or should it be another of the six classes — or not a reconciliation card at all?

---

## Scope lock

- Six classifications only. No seventh.
- No new `SourceFileType`. No bank matcher.
- PAYROLL substring helper and `structural_explained` fee-hint are **not** this slice.
- AND-gate (`_is_material`) is a **different** PR. This analysis assumes that gate: GL-only still has `delta_pct ≈ ±100%` and still **passes** materiality if `|delta| >= $100`.

---

## 1. How orphans become `missing_je` today (after the AND-gate)

Consolidator **still does not classify.** GÖREV 1 only changed *which* items exist, not the label path.

Runtime:

1. `consolidator.py::_detect_deltas` — if a `(canonical, category)` group has a single `source_file` and the run has ≥2 files, it builds an item with `hints.is_gl_only` or `hints.is_source_only`. `_build_item` applies `_is_material(delta, delta_pct)`.
2. `orchestrator.py` overwrites hints via `hint_computer.compute_hints` (recomputes `is_gl_only` / `is_source_only` from `item.sources`).
3. `interpreter.py` — Claude’s `reconciliation_classifications[account]` wins if present; else `_classify_from_hints`.
4. Prompt (`narrative_prompt.txt`): `missing_je` when `is_source_only` or `is_gl_only`. Also “if unsure, default to missing_je.”
5. Fallback: `is_gl_only or is_source_only` → `missing_je` (first branch). Last resort `stale_reference` is **unreachable** for orphans.

So both writers **agree** on `missing_je` for any orphan that survives materiality. GÖREV 1 effect: source-only items under `$500` with `delta_pct is None` no longer exist. GL-only items with `|amount| >= $100` still exist (pct ≈ 100%). Classification chain for remaining orphans is unchanged.

---

## 2. Sentinel count — from git history files, not a guess

Current `main` / this workspace tree has only:

- `docs/demo_data/sentinel/sentinel_gl_mar_2026.xlsx`
- `docs/demo_data/sentinel/february/sentinel_gl_feb_2026.xlsx`

The April 2026 smoke set (payroll, supplier, contracts, installation) was added in `595e0fd` and **deleted** in `c0e059e`. Those four files were restored to `/tmp` for this analysis (`git show 595e0fd:docs/demo_data/sentinel/…`). They were **not** committed back. This is consolidator-only (account / category / amount). Not a full parser → Haiku → interpreter replay, so it is **not** a claim that the 2026-04-24 run was exactly these integers.

### What the xlsx actually contain

GL sheet (header row 4): 21 P&L accounts after dropping Total\* / Gross Profit / Net Income; **Bank Charges $95**. Department files all already use GL account names: `Salaries & Wages`, `Equipment COGS`, `Service Revenue`, `Installation Revenue`.

### Reconstruction A — skip subtotals, dept category aligned to GL (post-mapper analog)

Ran `consolidate()` from the AND-gate implementation (same rule this policy would sit on top of):

| Shape | Count | Accounts |
|-------|-------|----------|
| GL-only | **16** | Bad Debt $177, Contractors $700, Depreciation $620, Employee Benefits $1,240, Equipment Rental $390, Insurance $1,150, Licenses & Permits $250, Marketing $2,400, Office Supplies $215, Payroll Taxes $3,675, Professional Fees $875, Rent $3,200, Software Subscriptions $615, Telephone $320, Utilities $480, Vehicle Expense $2,100 |
| Source-only | **0** | — |
| Two-sided | **4** | Equipment COGS Δ$1,700; Installation Revenue Δ$1,500; Salaries & Wages Δ$700; Service Revenue Δ$285 |
| Not an item | **1** | Bank Charges $95 (`< $100`) |

16 + 0 = **16 orphans**. All 16 are GL-only: a P&L line with **no uploaded subledger that speaks that account**. None of them is “invoice in the department file, missing from GL.”

The 4 two-sided rows are the real tie-outs (payroll register vs wages, suppliers vs COGS, contracts vs service revenue, install payments vs install revenue). Those are **not** the orphan policy.

### Reconstruction B — if Total / Gross Profit / Net Income leak into `account`

Same files, named rows kept (29 accounts): **24 GL-only + 0 source-only + 4 two-sided = 28 items**. That 24 includes `Total Revenue`, `Total COGS`, `Gross Profit`, `Net Income`, etc. Those are parser-drop candidates, not close exceptions.

### Vs archived smoke (32 recon = 28 `missing_je` + 4 `categorical`)

Cannot replay classifications: no stored Claude JSON. Directionally: 4 two-sided ≈ the 4 `categorical_misclassification`; the `missing_je` mass matches **GL-only P&L lines** (16 if subtotals are dropped, more if they leak or if `(canonical, category)` splits double-count — Reconstruction C below).

### Reconstruction C — dept `category` left raw (payroll OPEX vs GL PAYROLL; supplier “Equipment” vs COGS)

22 items: **18 GL-only + 2 source-only + 2 two-sided**. The extra four are **the same two accounts split** (Salaries & Wages, Equipment COGS) into a GL-only plus a source-only because `_detect_deltas` groups by `(canonical, category)`. That is the grouping bug, not a true missing JE. Out of this policy’s *recommendation*, but it inflates `missing_je` if mapper and GL disagree on category.

**Answer to “how many of the 28 are orphans?”** On the historical five-file set, after skipping subtotals and aligning category: **16 of 20 recon items are orphans, and all 16 are GL-only. 0 source-only.** The archived 28 cannot be reproduced as a precise subset without the original parse; the **pattern** is GL-only, not source-only.

---

## 3. Is `missing_je` the right class? (six-class, no seventh)

Taxonomy: `missing_je` = appears in one source only, **or** delta equals a single invoice. Template: “amount in [source] with no matching entry in the GL. A journal entry may be missing.”

| Shape | Fits `missing_je`? | Better treatment inside the six |
|-------|--------------------|----------------------------------|
| **Source-only** (subledger has a line, GL does not) | **Yes.** This is the JE-missing case (CableMax-style). Keep `missing_je`. | Optional: if `crosses_period_boundary`, `timing_cutoff` can outrank in the fallback **after** one-sided is no longer an automatic first branch — only when the date hint is on that file. Do not do that in the same slice as “drop GL-only.” |
| **GL-only** (P&L line, no file uploaded for that account) | **No.** Rent $3,200 in GL with no rent subledger is not a missing journal entry. The books already have the entry. Nothing is absent from the GL. The prompt template (“in [source] with no matching entry in the GL”) is **backwards** for `is_gl_only`. | Not `stale_reference` / `timing_cutoff` / `accrual_mismatch` / `categorical_misclassification`. **Not** `structural_explained` either (that class is fees/netting). Visibility without a seventh class: [addendum](#addendum--keep-gl-only-visible-without-a-7th-class). |
| **GL-only that is really a split** (same name, different category) | Looks one-sided only because of grouping | Separate slice: group deltas by `canonical` only. Then it becomes two-sided → existing `similar_amount_in_other_account` / `categorical_misclassification`. Not a new class. |

**Recommendation (v1, superseded).** Silent skip of GL-only cards. Rejected: “no card” and “checked clean” look the same; the product promise is to say why files don’t agree, including “we could not compare.”

**Recommendation (v2).** Keep emitting GL-only **cards**. Do **not** add a seventh taxonomy class. Do **not** park them under `structural_explained`. Treat coverage as a **presentation + prompt** problem keyed off the existing pandas hint `is_gl_only`. Full argument: [addendum](#addendum--keep-gl-only-visible-without-a-7th-class).

Do **not** add `uncovered_account` to `ReconciliationClassification`.

---

## Addendum — keep GL-only visible, without a 7th class

Product objection to v1 is accepted: dropping the 16 cards makes a forgotten subledger indistinguishable from a clean tie-out.

### 1. Sub-tag under `structural_explained` vs using class 6 as-is vs a third path

**Using `structural_explained` as-is (no extra field).** Least code. Fallback/prompt: `is_gl_only` → class 6. Frontend already greys it: CheckCircle, label “Explained”, copy “Expected — no action needed”, card `opacity-70`, **hides `suggested_action`**. Guardrail unchanged.

Product cost: Rent $3,200 becomes “no action needed.” Forgetting the rent/payroll file looks like a successful close. Class 6’s real job (processor fees / netting — still a dead class, still the field-service flagship) is spent on coverage. Later, a true fee gap and “no file uploaded” share one badge. **Not clean.**

**Sub-tag under `structural_explained`** (`classification = structural_explained` plus e.g. `hints.coverage_gap` or `subtype: uncovered | fee_netting`). Six-class Literal stays. JSONB can hold the subtype. UI can grey “No supporting file” vs green “Explained.”

Product cost: two meanings in one enum. `ReconciliationCard` today keys **only** on `classification === "structural_explained"` (`isExplained`). Without a frontend fork, coverage cards still hide the upload action and say “no action needed.” Prompt templates collide: class 6 text is “platform fees… No action required.” Claude already defaults unsure → `missing_je`; asking it to pick class 6 for both fees and uncovered accounts will mix them. When class-6 fee-hint work lands, you need the subtype anyway — so the subtype is the real discriminator, and hanging it off the fee class is the wrong parent.

**Third path (recommended).** Keep the six classes for **exceptions only**. Coverage is not a discrepancy class. Discriminator already exists: `hints.is_gl_only`. Add an optional JSONB field on the item for UI/counts, e.g. `card_kind: "coverage" | "exception"` (default `"exception"`). Pandas sets `card_kind="coverage"` when it emits a GL-only item (a fact about files present, not Claude arithmetic). Interpreter: if `is_gl_only` / `card_kind=coverage`, do **not** map to `missing_je` or `structural_explained`; write a coverage sentence; leave `classification` **null** (or omit from `reconciliation_classifications`). Fallback: `is_gl_only` must stop returning `missing_je` (today it does, first branch). Frontend: badge/section from `card_kind` or `hints.is_gl_only`, not from class 6. Stats strip must stop dumping Rent $3,200 into “Medium.”

Why this is less friction than a class-6 subtype: you do not teach Claude a second meaning for class 6; you do not wait to fork `isExplained`; fee-netting work stays unblocked; the six-class lock stays literal.

Disagreeing with the user’s lean: **visibility — yes. Parenting coverage under `structural_explained` — no.** Class 6 already means “delta explained, no action.” Coverage means “we did not compare; consider uploading a file.” Those are opposite speech acts. A grey badge cannot fix a taxonomy that says both are “Explained.”

### 2. Concrete file list (third path)

Pandas / items (keep producing cards — consolidator already does):

| File | Change |
|------|--------|
| `backend/domain/contracts.py` | `ReconciliationItem.card_kind: Literal["exception", "coverage"] = "exception"`. Optional. No change to `ReconciliationClassification`. `is_gl_only` already on `ReconciliationHints`. |
| `backend/agents/consolidator.py` `_detect_deltas` / `_build_item` | **Do not skip GL-only.** Set `card_kind="coverage"` on GL-only items. Source-only stays `"exception"`. |
| `backend/tools/hint_computer.py` | No new hint required if `is_gl_only` remains true (orchestrator already recomputes it). |

Classification / prose:

| File | Change |
|------|--------|
| `backend/prompts/narrative_prompt.txt` | `missing_je` **only** for `is_source_only` (and invoice-sized two-sided gaps). Remove `is_gl_only` from that bullet. Add a **coverage** template, not as taxonomy #7: “GL shows [amount] for [account]. None of the uploaded files include this account, so it was not compared. This is not a missing journal entry.” Soft action: upload a supporting file or confirm there isn’t one. Do **not** use the class 6 fee template. Do not put coverage accounts in `reconciliation_classifications` (or map them to null). |
| `backend/agents/interpreter.py` `_classify_from_hints` | Split today’s first branch: `is_source_only` → `missing_je`; `is_gl_only` → **do not classify** (leave null) / do not return `structural_explained`. |
| `backend/agents/interpreter.py` merge loop | If `card_kind=="coverage"` or `hints.is_gl_only`, do not let Claude overwrite into `missing_je` / class 6 without a coverage check. |
| `backend/tools/guardrail.py` | **No change.** Still `numbers_used` only. Coverage amounts already in recon values. |

Frontend (this is where “info vs needs review” actually happens):

| File | Change |
|------|--------|
| `frontend/src/components/ClassificationBadge.tsx` | Do **not** add a 7th `Classification` union member. For coverage, either skip this badge or add a **separate** `CoverageBadge` (grey, not CheckCircle). Putting coverage into `CONFIG.structural_explained` reuses “Explained.” |
| `frontend/src/components/ReconciliationCard.tsx` | `isExplained` must **not** treat coverage as class 6. New copy e.g. “No supporting file uploaded.” Keep a visible, non-error action (“Upload a file for this account, or confirm none exists”). Do not use `opacity-70` + hide action. |
| `frontend/src/components/ReconciliationPanel.tsx` | Split groups: exception cards by severity; coverage in a third block “Not compared.” Header count: “4 to review · 16 not compared” not “20 items” as if they were the same. Empty state “No discrepancies” must **not** fire when only coverage cards exist? If coverage exists, show that block, not “all clean.” |
| `frontend/src/components/ReportSummary.tsx` `StatsStrip` | Today High/Medium/Low are **dollar buckets on every recon item**. Rent $3,200 is Medium. Exclude `card_kind=coverage` from High/Medium/Low; optional fourth stat “Not compared.” `anomaly_count` is flux, already separate — no change. |
| `backend/tools/excel_export.py` | Classification column: blank or “Not compared” for coverage. Do not paint Total Operating Expenses-level dollars as HIGH severity red if we ever leak subtotals. |

Tests: `tests/agents/test_consolidator.py` (GL-only still an item, `card_kind=coverage`); interpreter fallback tests if present; a frontend test only if the repo has component tests (today: none required).

**Not in this slice:** `comparison.py`, AccountMapper, PAYROLL helper, fee-band class-6 hint, grouping-by-canonical, `0010` migration.

**If you insist on the class-6 subtype anyway**, add the same frontend forks **plus** prompt subtype rules **plus** `isExplained = classification === "structural_explained" && subtype !== "uncovered"`. More files, same UI work, worse taxonomy. Not fewer.

### 3. The 16 GL-only — before / after (third path)

Today (AND-gate on, current prompt/fallback): each of the 16 is a recon item, `is_gl_only`, classified `missing_je`, high/orange “Missing JE” badge, `ReconciliationPanel` severity from `|delta|` (Rent $3,200 = Medium, Payroll Taxes $3,675 = Medium, Bad Debt $177 = Low). `StatsStrip` “Findings” includes all 16. Narrative: “journal entry may be missing” (wrong — the JE is in the GL).

After (third path): same 16 items still in `reports.reconciliations` JSON. `card_kind=coverage`, `classification=null`. Grey info row/section “Not compared — no supporting file.” Not in High/Medium exception counts. Narrative: could not compare; not a missing JE. Two-sided four unchanged. Source-only (none on this demo) still `missing_je`.

`structural_explained` as-is: same 16 items, badge “Explained”, copy “no action needed”, muted card, **no** upload action. Visible, but lies.

Class-6 + subtype: same 16 items, custom grey if UI forks; if UI does not fork, identical to as-is.

Silent skip (v1): 16 gone; Findings look like only the 4 two-sided; user cannot see they never uploaded rent/insurance/etc.

### 4. Migration / schema

**No migration.** `reports.reconciliations` is JSONB. `card_kind` is a Pydantic field with default `"exception"`; old rows without it stay exceptions. Hints already persist on the item. Highest SQL file remains `0009`. Do not add `0010` for a coverage enum column.

`ReconciliationClassification` Literal stays six values. `NarrativeJSON.reconciliation_classifications` stays `dict[str, ReconciliationClassification]`; coverage accounts are omitted from that dict (null classification).

### 5. Risk / rollback

| Risk | Why | Mitigation |
|------|-----|------------|
| Claude still stamps `missing_je` on GL-only | Prompt still lists `is_gl_only` under class 3; merge prefers Claude | Prompt edit + interpreter ignore Claude class when `card_kind=coverage` |
| Class 6 used “for convenience” | Frontend greys it for free | Do not. Breaks fee work and hides the upload action |
| StatsStrip still Medium-counts Rent | Dollar grouping ignores kind | Must change `ReportSummary.tsx` in the same slice or the info badge is theatre |
| Category-split pair | GL-only half becomes coverage, source-only half `missing_je` for one real account | Grouping slice later; call out in QA |
| Empty state | 0 exceptions + 16 coverage must not say “No discrepancies detected” | Panel empty-check uses exception subset only, still renders coverage |
| Guardrail | Unrelated | No change |

**Rollback:** revert the item `card_kind` + prompt + fallback + frontend count/badge commit(s). JSONB old reports without `card_kind` still render as today. No `DOWN` migration.

---

## 4. Files / functions / schema (v1 skip-card — discarded)

Kept only as history. Do not implement skip-GL-only. The live list is in the addendum §2.

**Schema / migration:** none (same as addendum). Highest migration remains `0009`.

**Do not touch:** comparison.py, AccountMapper, PAYROLL helper, fee-band class-6 engine.

---

## 5. Before / after examples

See addendum §3. v1 “no item” column is **not** the plan anymore.

| Input | Today | After v2 (coverage card) |
|-------|--------|--------------------------|
| GL Rent $3,200, no rent file | `missing_je`, Medium | Coverage card, not compared, not Medium-exception |
| GL Rent $200, same | `missing_je`, Low | Coverage card |
| Dept Bonus $600, no GL | `missing_je` | Unchanged `missing_je` |
| Equipment COGS two-sided Δ$1,700 | exception | Unchanged |

**Sentinel direction:** item **count stays in the same ballpark** (16 coverage + 4 exceptions if Reconstruction A). What changes is **mix and chrome**, not disappearance. `missing_je` should fall by about those 16. Do not promise a total of 4.

---

## 6. Risk / rollback

See addendum §5. v1 “hide and log” rollback is obsolete.

---

## IMPLEMENTATION

Blocked. Approve v2 (coverage cards, not class 6, not a 7th class) before any prompt.

One PR when approved: `card_kind` + prompt + fallback split + badge/panel/stats. Do not mix with AND-gate, PAYROLL, or fee-hint class 6.

---

## VERIFICATION (after code, not now)

| Check | Prediction | Actual | Match? |
|-------|------------|--------|--------|
| GL-only Rent still an item | yes, `card_kind=coverage` | | |
| That item’s classification | not `missing_je`, not `structural_explained` | | |
| Source-only $600 | still `missing_je` | | |
| Two-sided $700 payroll | still exception | | |
| StatsStrip Medium | does not include Rent $3,200 | | |
| Class 6 union | still six strings | | |
| Sentinel `missing_je` | down by ~the GL-only set; cards still visible | | |

---

## Approval checkpoint

1. **Reject v1** silent skip. Visibility required.
2. **Reject** `structural_explained` as-is for GL-only (false “no action”).
3. **Prefer third path** (`card_kind=coverage` + `is_gl_only`, classification null, grey info section) over a class-6 subtype. If you still want the subtype, say so explicitly — it is more UI work for a worse parent class.
4. Source-only stays `missing_je`. No seventh `ReconciliationClassification`. No SQL migration.
5. Frontend counts must change in the same slice or the badge is cosmetic.
6. Do not mix with AND-gate / PAYROLL / fee-hint PRs.

