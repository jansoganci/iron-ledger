# Pre-analysis — Orphan policy (GL-only / source-only)

*Planning only. No implementation until this document is approved.*  
*Date: 24 August 2026.*  
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
| **GL-only** (P&L line, no file uploaded for that account) | **No.** Rent $3,200 in GL with no rent subledger is not a missing journal entry. The books already have the entry. Nothing is absent from the GL. The prompt template (“in [source] with no matching entry in the GL”) is **backwards** for `is_gl_only`. | **Do not emit a recon item.** Coverage, not an exception: “17 GL lines had no supporting file.” Not `stale_reference` (that is roster vs revenue). Not `timing_cutoff` (no date). Not `structural_explained` (not fees). Not `accrual_mismatch`. Not `categorical_misclassification` (no counterpart amount). |
| **GL-only that is really a split** (same name, different category) | Looks one-sided only because of grouping | Separate slice: group deltas by `canonical` only. Then it becomes two-sided → existing `similar_amount_in_other_account` / `categorical_misclassification`. Not a new class. |

**Recommendation (this slice):** stop creating reconciliation items for `is_gl_only`. Keep creating them for `is_source_only` (still `missing_je`) and for two-sided material deltas (six-class as today). Optional UI copy: “No supporting file for N GL accounts” from pandas counts — not a classification.

Do **not** add a seventh class named `uncovered_account`. That is a coverage metric, not a discrepancy.

---

## 4. Files / functions / schema

If later approved (not this turn):

| File | Change |
|------|--------|
| `backend/agents/consolidator.py` `_detect_deltas` | When `len(grp) < 2` and the only source is GL → `continue` (no item). When the only source is non-GL → keep current `_build_item` + materiality. |
| `tests/agents/test_consolidator.py` | GL-only Rent $200 must **stop** flagging if this policy lands (opposite of Slice 1’s AND-gate test). Source-only `$600` still flags. |
| `backend/tools/hint_computer.py` | No change required if GL-only items are not created. `_is_gl_only` remains for safety. |
| `backend/agents/interpreter.py` / `narrative_prompt.txt` | Optional later: stop listing `is_gl_only` under `missing_je` so a leaked item cannot be mis-templated. Not required if consolidator never emits them. |
| `frontend/.../ReconciliationPanel.tsx` | No code if we simply emit fewer items. Optional coverage line is a later UI slice. |

**Schema / migration:** none. Hints already on the item JSON. Highest migration remains `0009`. Do not write `0010` for this.

**Do not touch:** comparison.py, guardrail, AccountMapper, PAYROLL helper, fee-band / class 6.

---

## 5. Before / after examples (policy, not AND-gate)

AND-gate already landed separately. These examples are **orphan policy on top**.

| Input | Today (post-AND-gate) | After this policy |
|-------|----------------------|-------------------|
| GL Rent $200, payroll file covers only Payroll | Recon item, `is_gl_only` → `missing_je` | **No item** |
| GL Rent $3,200, same | Item, `missing_je` | **No item** |
| Dept Bonus $200, no GL line | No item (AND-gate, pct None, `< $500`) | Still no item |
| Dept Bonus $600, no GL line | Item, `is_source_only` → `missing_je` | **Unchanged** — still `missing_je` |
| GL Equipment COGS $36,100 vs supplier $37,800 (same category) | Two-sided item Δ$1,700 | Unchanged (not an orphan) |
| Same accounts, **different** category | Two one-sided items, both `missing_je` | Still wrong until grouping slice; this policy would drop the GL-only half and keep the source-only half — **call out as a sequencing risk** |

**Sentinel effect (direction only, no fake total):** GL-only cards should **disappear**. Two-sided tie-outs (payroll, COGS, contracts, installs) should **remain**. `missing_je` should fall by about the number of uncovered P&L lines (order of the sixteen named above if subtotals stay dropped). Do not promise “total becomes 4” — parser category splits and Total\* leakage move the integer. Source-only stays rare on this demo because department files already use GL names.

If a future smoke still shows ~28 `missing_je`, either subtotals leaked, categories split, or this policy was not applied — stop and compare to Reconstruction A.

---

## 6. Risk / rollback

| Risk | Why | Mitigation |
|------|-----|------------|
| Hide a true “GL extra” that the controller wanted to investigate | Some GL-only *are* errors (duplicate account, leftover) | Coverage count in pandas/logs (`gl_only_skipped=N`) so ops can see they were omitted, not classified |
| Sequencing with category-split | Dropping GL-only while keeping source-only on a split pair leaves one `missing_je` for an account that actually exists on both sides | Grouping-by-canonical first **or** accept a leftover source-only until that slice |
| Slice 1 test `test_and_gate_gl_only_rent_200_still_flagged` | Will fail if this policy lands | Invert that test in the same PR as the policy; do not silently break Slice 1 |
| Prompt still says `is_gl_only` → missing_je | Harmless if no such items | Optional prompt cleanup later |
| Expecting class-6 / fee stories to appear | Unrelated; two-sided install/contracts stay whatever class Claude picks | Keep class-6 on its own pre-analysis |

**Rollback:** revert the consolidator orphan-branch commit. No migration. Next run rebuilds `reports.reconciliations`.

---

## 2. IMPLEMENTATION

Blocked. Do not start until this pre-analysis is explicitly approved. One PR, one concern: skip GL-only item creation in `_detect_deltas`. No class-6, no PAYROLL, no grouping rewrite unless you explicitly expand scope (not recommended in the same PR because of the split-pair sequencing risk).

---

## 3. VERIFICATION (after code, not now)

| Check | Prediction | Actual | Match? |
|-------|------------|--------|--------|
| Unit: GL-only Rent $200 | no item | | |
| Unit: source-only $600 | still `is_source_only` item | | |
| Unit: two-sided $700 payroll | still an item | | |
| Sentinel GL-only named P&L lines | gone from recon list | | |
| Sentinel two-sided four | still present (if category aligned) | | |
| New seventh class | none | | |
| If `missing_je` barely moves | plan wrong (still grouping/subtotals) vs implementation missed the skip | | |

---

## Approval checkpoint

1. GL-only = **no recon card** (coverage, not `missing_je`).
2. Source-only = keep `missing_je`.
3. No seventh class. No migration.
4. Implement grouping-by-canonical as a **later** slice if split pairs still matter.
5. Do not mix this PR with AND-gate, PAYROLL, or class-6.
