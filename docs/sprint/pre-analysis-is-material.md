# Pre-analysis — Slice 1: consolidator `_is_material` AND-gate

*Planning only. No implementation until this document is approved.*  
*Date: 24 August 2026.*  
*Parent: [field-service-close-triage.md](field-service-close-triage.md) Bucket 1 item 1.*  
*Process: (1) this pre-analysis → approval, (2) implementation as one piece, (3) verification vs this file.*

This is **one piece**. Not PAYROLL (`account_tags.py`). Not `structural_explained`. Not grouping-by-canonical. Not flux / onboarding / `0010`.

---

## Scope lock

Implement the **already-written** consolidator docstring, in pandas only:

> Flag if `|delta| >= $100 AND |delta_pct| > 5%`, OR `|delta| >= $500`.

(`_DELTA_DOLLAR_MIN = 100`, `_DELTA_PCT_MIN = 0.05`, `_DELTA_DOLLAR_HARD = 500`. Dollar gates inclusive to match today’s constant names and tests; percent gate is a strict `>` on the 5% constant.)

**Correction to the triage.** The unused percent gate is a real bug. It is **not** the main reason Sentinel emitted 32 recon cards. Most of those cards are **GL-only orphans**: a 41-line P&L vs a handful of department files. For a GL-only item, `delta_pct = delta / gl_amount = ±100%`, which already clears 5%. The AND-gate **keeps** those. Do not approve this slice expecting 32 → a small number. That drop needs a **different** slice (orphan policy: do not treat “this GL line has no uploaded subledger” as `missing_je`). That policy is **out of this piece**. If the goal of the next code drop is “believable card count,” reject this slice and commission a pre-analysis for orphan policy instead.

---

## 1. Affected files / functions (complete, from the repo)

Call graph today: `orchestrator.py` (`run_multi_file_parser_until_preview` and `apply_mapping_and_consolidate`) → `consolidate()` → `_detect_deltas` → `_build_item` / `_is_material`. Downstream only **reads** the list length.

| File | Symbol | Change? |
|------|--------|---------|
| `backend/agents/consolidator.py` | module docstring lines 16–17 | No (already states the AND-gate) |
| `backend/agents/consolidator.py` | `_DELTA_DOLLAR_MIN`, `_DELTA_PCT_MIN`, `_DELTA_DOLLAR_HARD` | No (values stay) |
| `backend/agents/consolidator.py` | `_is_material` | **Yes.** Signature must take `delta_pct: float \| None`. Body: hard `$500` OR (`$100` AND pct present AND `> 5%`). `delta_pct is None` → only the hard gate. |
| `backend/agents/consolidator.py` | `_build_item` (~L315) | **Yes.** Pass computed `delta_pct` into `_is_material`. |
| `backend/agents/consolidator.py` | `_detect_deltas` two-sided path (~L277–278) | **Yes.** `if _is_material(item.delta)` is redundant today and **wrong** after the signature change (would pass `delta_pct=None` and drop every two-sided item under `$500`). Delete this second check; `_build_item` already returns `None`. |
| `backend/agents/consolidator.py` | `_detect_deltas` orphan skip (~L262–270) | **Yes.** Reuse `_is_material(delta, delta_pct)` instead of a bare `< $100` continue, so orphans and two-sided share one gate. |
| `tests/agents/test_consolidator.py` | `test_is_material` | **Yes.** Today parametrizes `(delta,) → bool` and expects `$100` True with no pct. Must become `(delta, delta_pct) → bool` with the cases in §2. |
| `tests/agents/test_consolidator.py` | `test_consolidate_payroll_delta_flagged` | No expected failure. `$700` vs GL `$44,900` is `1.56%` but `$700 >= $500` (hard). |
| `tests/agents/test_consolidator.py` | `test_consolidate_supplier_delta_flagged` | No expected failure. `$1,700` vs GL `$36,100` is `4.71%` but hard gate. |
| `tests/agents/test_consolidator.py` | `test_consolidate_single_source_no_reconciliations` | No. |
| `tests/agents/test_consolidator.py` | new cases | **Yes.** Two-sided `$400` / `2%` must not flag; two-sided `$400` / `20%` must; source-only `$200` (`pct is None`) must not; GL-only `$200` (`pct = 100%`) still must; `$500` / `0.1%` must. |

**Read-only, do not touch**

| File | Why listed |
|------|------------|
| `backend/agents/orchestrator.py` | Calls `consolidate()`; consumes `recon_items`. No materiality math. |
| `backend/tools/hint_computer.py` | Runs **after** items exist. Fewer items → fewer hint calls. Do not change hints. |
| `backend/agents/interpreter.py` | Classifies whatever list it receives. |
| `backend/prompts/narrative_prompt.txt` | Untouched. |
| `backend/tools/guardrail.py` | Untouched. Fewer recon numbers is still valid. |
| `backend/agents/comparison.py` | Different thresholds (`_TIER1_*` / `_TIER2_*`). Out of scope. |
| `backend/domain/contracts.py` | `ReconciliationItem.delta` / `delta_pct` already exist. No schema change. |
| `frontend/src/components/ReconciliationPanel.tsx` | Renders the list. Card count falls automatically. |
| `tests/tools/test_hint_computer.py` | Builds items by hand; does not call `_is_material`. |
| `tests/agents/test_orchestrator_mapping.py` | Mapping, not materiality. |
| `video/src/Composition.tsx` | Hardcoded demo copy (“31 reconciliations”). Not runtime. Out of scope. |

No other production references to `_is_material` or the three `_DELTA_*` constants exist.

---

## 2. Behavior — BEFORE / AFTER

Rule in code today:

```python
return abs_delta >= 500 or abs_delta >= 100   # i.e. abs_delta >= 100; pct unused
```

Rule after (single function, both call sites):

```
if abs(delta) >= 500: flag
elif abs(delta) < 100: do not flag
elif delta_pct is None: do not flag
else: flag iff abs(delta_pct) > 0.05
```

`delta_pct` is `delta / gl_amount` when `gl_amount` is non-zero, else `None` (already how `_build_item` computes it).

| # | Input | BEFORE item? | AFTER item? |
|---|--------|--------------|-------------|
| A | Two-sided. GL `$10,000`, source `$10,050`. `delta=$50`, `pct=0.5%` | No (`< $100`) | No |
| B | Two-sided. GL `$10,000`, source `$10,100`. `delta=$100`, `pct=1%` | **Yes** | **No** (dollar ok, pct not) |
| C | Two-sided. GL `$1,000`, source `$1,100`. `delta=$100`, `pct=10%` | Yes | Yes (both gates) |
| D | Two-sided. GL `$20,000`, source `$20,400`. `delta=$400`, `pct=2%` | **Yes** | **No** |
| E | Two-sided. GL `$50,000`, source `$50,500`. `delta=$500`, `pct=1%` | Yes | Yes (hard gate; pct ignored) |
| F | GL-only. GL Rent `$200`, no dept file. `delta=-$200`, `pct=-100%` | Yes | **Yes** (pct always ~100%) |
| G | Source-only. Dept `$200`, no GL line. `gl_amount=None`, `pct=None` | **Yes** | **No** (no pct, under hard) |
| H | Source-only. Dept `$600`, no GL line. `pct=None` | Yes | Yes (hard gate) |
| I | Unit fixture payroll. GL `$44,900` vs dept `$44,200`. `delta=$700`, `pct=1.56%` | Yes | Yes (hard `$500`) |
| J | Unit fixture supplier. GL `$36,100` vs `$37,800`. `delta=$1,700`, `pct=4.71%` | Yes | Yes (hard) |

Worked example for B (the actual bug this slice fixes):

```
# BEFORE
abs(100) >= 100 → ReconciliationItem(account=..., delta=100.0, delta_pct=0.01)

# AFTER
abs(100) >= 500? no
abs(100) >= 100 and 0.01 > 0.05? no
→ no item
```

---

## 3. Schema / migration

None. No new table, column, or JSONB key. `reports.reconciliations` stays the same shape, possibly shorter array. Highest migration on disk remains `0009_add_report_type_and_quarterly.sql`. Do not write `0010`.

---

## 4. Expected Sentinel smoke (honest bound, not a fake integer)

**BEFORE (archived, 24 Apr 2026, `docs/archive/three_sector_demo_plan.md`):** 41 GL rows → 32 recon = 28 `missing_je` + 4 `categorical_misclassification`. Zero `structural_explained` / `stale_reference` / `timing_cutoff`. Guardrail green.

**This environment:** `docs/demo_data/sentinel/` is **not in the workspace**. Exact AFTER counts cannot be computed here. Do not invent them.

**Predicted direction if those same files are re-run after this slice only:**

- Item count: `<= 32`. A large drop is **not** predicted.
- The 4 `categorical_misclassification` (large dollar gaps, including the ~`$700` payroll pattern) stay, via the hard gate, even when pct `< 5%`.
- Most of the 28 `missing_je` are GL-only lines with `|pct| ≈ 100%` → **still items**, still `missing_je` (prompt and fallback agree on one-sided).
- Drops, if any: two-sided `|delta| ∈ [$100, $500)` with `|pct| ≤ 5%`, and source-only lines in that dollar band. Likely a handful, not 28.
- Class-6 still does not fire (not this slice).
- Flux / `comparison.py` anomalies unchanged.

**Pass criteria for later verification (section 3):** AFTER total `<=` BEFORE total; the 4 categorical still present if those dollar gaps are still `>= $500`; GL-only accounts `>= $100` still present; no `structural_explained` newly appearing; guardrail still green. If AFTER total falls by more than ~10 items, the implementation probably changed orphan policy or grouping — that is **scope creep**, not success.

---

## 5. Risk / rollback

| Risk | Why | Mitigation |
|------|-----|------------|
| Second `_is_material(item.delta)` left in place | After adding `delta_pct`, default `None` would hide all two-sided items under `$500`, including fixtures I and J | Delete that call in the same patch; tests I/J fail if it is left |
| Expecting Sentinel 32 → “clean” | AND-gate does not suppress GL-only | This document; do not “fix” orphans in the same PR |
| Percent on GL-only is 100% | Looks like the AND-gate “does nothing” on the demo | Expected; verify with cases F vs G in unit tests, not with a card-count hope |
| `>` vs `>=` on `$100` / 5% | Docstring says `>`; tests used `>= $100` | Lock the rule in §Scope; unit-parametrize exact `$100` / `5%` / `$500` |
| Claude narrative mentions a dropped `$100` line | Interpreter only sees remaining items | No prompt change |
| Guardrail | Unrelated | No change |

**Rollback:** revert the single consolidator commit (and its test commit). No migration to undo. No stored recon rows to backfill; next run rebuilds `reports.reconciliations`.

---

## 2. IMPLEMENTATION

Blocked. Do not start until this pre-analysis is explicitly approved. One PR, one concern: `_is_material` + `_detect_deltas` call sites + `test_consolidator.py`. No drive-by grouping, hint, prompt, or payroll work.

---

## 3. VERIFICATION (after code, not now)

Fill this in on the implementation turn. Do not pre-fill fake smoke numbers.

| Check | Pre-analysis prediction | Actual | Match? |
|-------|-------------------------|--------|--------|
| Unit: cases A–J | as §2 | | |
| `test_consolidate_payroll_delta_flagged` | still flags `$700` | | |
| `test_consolidate_supplier_delta_flagged` | still flags `$1,700` | | |
| Sentinel item count | `<= 32`, not a collapse | | |
| Sentinel classes | 4 categorical remain; most `missing_je` remain; class 6 still 0 | | |
| Other classes newly appearing / disappearing | none expected | | |
| If mismatch: plan wrong vs implementation drifted? | | | |

If Sentinel files are still absent, record “files missing — unit cases A–J only” rather than guessing.

---

## Approval checkpoint

Approve or amend:

1. This slice is docstring AND-gate only. Card-count collapse is **not** a success metric.
2. If you instead want Sentinel 32 → a small list, **do not implement this**. Ask for a separate pre-analysis: “do not emit `is_gl_only` merely because no subledger file covers that GL line.”
3. PAYROLL helper and `structural_explained` stay later, each with their own pre-analysis.
