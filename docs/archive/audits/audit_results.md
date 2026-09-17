# IronLedger — Audit Status

> **This file has two parts.** The section immediately below is the **current,
> post-merge status**, re-verified against `main` at the HEAD named in it.
> Everything after it — Tours 1, 2 and 3 — is the **historical audit record**
> as written against the pre-merge snapshot `31492f9`. The historical sections
> are deliberately **not** edited. Where they are now stale, the
> "Stale in the historical record" table below says so explicitly.

## Current Status (post-merge)

**Verified against:** `main` @ `3534236` (`documents committed`), in sync with
`origin/main`. Every row below was re-checked by reading current code, tests,
migrations and prompts — not carried over from the earlier audit text.

**Test suite on this HEAD: `262 passed, 5 skipped, 0 failed, 0 errors`.**

Note this supersedes the historical `237 passed, 5 skipped`. The count rose
because the guardrail fix added 25 tests and the stack landed the rest; the
`test_parser_end_to_end.py` failure and four errors that the Tour 1 audit
treated as pre-existing are **gone** — PR #1 carried commit `90173b4`, which
fixed them.

### a. What is actually live on `main` right now

The entire Kova 1 stack, Item 5, and the guardrail fix are all merged. Item 1
remains spec-only, exactly as designed.

| Area | State |
|---|---|
| **Guardrail** | Corrected version live. Unit-aware tolerances, narrative parser, `strict=True` on the Interpreter path. |
| **Kova 1 (six items)** | All live: materiality AND-gate, coverage/`card_kind`, deposit-vs-fee hints, cutoff allowlist, annual prepayment, PAYROLL tagging. |
| **Item 5** | Live: `_gates_from_band`, `_BAND_R`, migration `0010`, `PATCH /companies/me`, `RevenueBandField.tsx`. |
| **Item 1** | **Spec only — no code.** Re-confirmed absent: no `batch_matcher.py`, no `BatchMatch` symbol, `SourceFileType` still exactly four literals, no `kova_cash_*` fixtures. |
| **Item 4, parked 2/3/6** | Not started. `roster_counts.py` absent; zero `RMR`/`roster_count` references in `backend/`. |
| **Migrations** | `0001`–`0010`: 10 files, 10 unique prefixes, no gaps, no duplicates. |
| **Classifications** | Exactly **six**. No seventh value appeared through any merge. |

### Stale in the historical record (Tours 1–3 below)

These statements were true when written and are **false now**. They are left
in place unedited; this table is the correction.

| Historical claim | Location | Now |
|---|---|---|
| "They have not landed on `main`." | Tour 1, Executive conclusion | **False.** The full chain `#1 → #2 → #4 → #9 → #11 → #13 → #14 → #15 → #16 → #17` is merged. |
| "PRs #2, #4, #5, #9, #11, #13, #16, #17 are all open; most are drafts." | Tour 1, Delivery-state caveat | **False.** All merged except **#5**, closed unmerged as superseded by #16. |
| "the numeric guardrail does not currently enforce the stated golden rule" | Tour 1, Executive conclusion / §B.1–B.4 | **Fixed** for the Interpreter path. §B.5 (quarterly / opus prompts) is still open — see table (c). |
| "Verified on stack; not landed" (PAYROLL, `card_kind`, migration `0010`) | Tour 2, §A rows 3, 4, 8 | **Now landed.** |
| "`237 passed, 5 skipped`" | Tour 1 §A / §D | Superseded: **262 passed, 5 skipped**. |
| "`guardrail.py:21` cites `docs/sprint/guardrail-fix-pre-analysis.md`, which is not in the repo" | Post-Tour-3 note | **Resolved.** That doc is committed in `3534236`. |
| "the working tree is also dirty and contains only a partial mixture of coverage/UI edits" | Tour 1, Delivery-state caveat | **Resolved.** Reconciled: two unique items kept, the rest discarded as superseded by #4. |

### b. COMPLETE — verified merged and working as claimed

| Item | Verified on `main` |
|---|---|
| **Guardrail — tolerance split** | `flatten_summary_by_unit` present; money `max($0.01, 1e-6×ref)`, percent `0.05pp`. Invented-value acceptance measured at **0.015%**, down from 40.9%. |
| **Guardrail — narrative parser** | `parse_narrative_numbers` present; ignores dates, ordinals, counts, GL codes. |
| **Guardrail — `implied_monthly`** | Now **genuinely live**, not inert: `#13` added the hint, and a `1,000.00` implied-monthly value was confirmed to pass the guardrail end-to-end. |
| **Guardrail — reinforced prompt** | `narrative_prompt_reinforced.txt` carries PART 2, the six-class taxonomy, and the full JSON shape. A retry can no longer silently drop reconciliation findings. |
| **Kova 1 #2 — materiality AND-gate** | `_is_material(delta, delta_pct=None)` present in `consolidator.py`. |
| **Kova 1 #4 — coverage / `card_kind`** | `card_kind` on `ReconciliationItem`; coverage is a card kind, not a seventh class. |
| **Kova 1 #9 — deposit vs processor fee** | `is_customer_deposit` and `is_processor_fee_gap` both present as separate hints. |
| **Kova 1 #11 — cutoff allowlist** | `_crosses_period_boundary` with roster/renewal exclusions present. |
| **Kova 1 #13 — annual prepayment** | `implied_monthly` on `ReconciliationHints`; same-item 12× ratio. |
| **PAYROLL tagging** | `account_tags.py` present with the **newer** `str \| None` signature from #16 — confirming #5 was correctly closed as superseded. |
| **Item 5 — revenue-scaled materiality** | `_gates_from_band`, `_BAND_R`, `0010`, `PATCH /companies/me`, `RevenueBandField.tsx` all live. |
| **Item 1 — spec freeze** | `docs/sprint/kova2-implementation-plan.md` on `main`; **no** implementation leaked. |
| **Cherry-picked items** | `CLAUDE.md` OWASP/Security line and `tests/tools/test_excel_export.py` both committed and tracked in `3534236`; the export test passes now that #4's changes are in. |

### c. COMPLETE WITH OPEN NOTES — shipped, with a known loose end

Every row was re-verified as **still open** on this HEAD. Nothing here is
resolved by this document.

| # | Item | Open note (verified still open) | Source |
|---|---|---|---|
| 1 | Guardrail Stage 1 | `ENFORCE_NARRATIVE_CONSISTENCY = False` — narrative/`numbers_used` mismatches are **logged, not blocking**. Deliberate: one release of measurement before enforcing. | Fix decision 3 |
| 2 | `quarterly.py` | Still calls `verify_guardrail` **without** `strict=True` → legacy `max(1%, $1,000)`. Its prompt still asks Claude to derive `{N} of {M}` / `year-1` (2 matches), so it cannot be migrated until that prompt is fixed. | Tour 1 §B.5 |
| 3 | `opus_upgrade.py` | Also still legacy (no `strict=True`); `opus_narrative_prompt.txt` still says "net position if derivable". Drifts from the Interpreter's standard. | Tour 1 §B.5 |
| 4 | `delta_pct` | Deliberately **excluded** from the guardrail reference pool — adding it would widen the accepted set. Recorded so it is not re-proposed as an oversight. | Fix decision 1 |
| 5 | Migration `0010` | `ADD COLUMN` is guarded by `IF NOT EXISTS`; `ADD CONSTRAINT` is **not** (Postgres has no such form). Re-running `0010` errors. | Tour 2 E.1 |
| 6 | Item 5 tests | `test_icp_100k_250k_salaries_flags` and `test_payroll_name_uses_tier2_of_band` **still do not discriminate** Tier 1 from Tier 2 — re-confirmed by probe: both paths flag, so they'd pass even if `is_payroll_account` were deleted. Routing itself is proven by `test_tier2_payroll_fires_at_lower_gates`. | Tour 2 E.2 |
| 7 | `seed.sql` | Does not set `monthly_revenue_band` (0 matches) → demo company runs on the NULL fail-safe `$50k/$10k` and never exercises Item 5. | Tour 2 E.3 |
| 8 | `500k_plus` band | Unbounded above; a `$500k/mo` and a `$5M/mo` company get identical gates. | Tour 2 E.4 |
| 9 | Percentage gates | `_TIER1_PCT`/`_TIER2_PCT` are fixed across bands — only the dollar gates scale. | Tour 2 E.5 |
| 10 | Hint leakage | `_crosses_period_boundary` still scans the whole involved file rather than rows belonging to the reconciliation account. | Tour 1 E.2 |
| 11 | Processor-fee signal | `_is_processor_fee_gap` still has **no** file/account-identity or direction check — any two-sided 3–8% gap is forced to `structural_explained`. | Tour 1 E.3 |
| 12 | `compute_hints` fallback | Still catches every exception and returns an empty hint object; a hint-engine defect degrades classification silently. | Tour 1 E.4 |
| 13 | Repo formatting | `black --check backend tests` → **7 files would be reformatted**; `flake8` → **535 violations** (systemic: no flake8 config, so the 79-char default fights black's 88). | Tour 1 §D |
| 14 | Demo data | `docs/demo_data/` holds six named company folders; the `drone_*.xlsx` files referenced in `CLAUDE.md` **do not exist** (0 found). | Tour 2 E.3 |

### d. NOT STARTED — priority ordered

Ordering logic is stated per row on three axes: **ICP value**, **architectural
risk if built carelessly**, and **dependency on anything not yet built**.
Remediation of the table (c) loose ends is tracked there, not repeated here.

| Rank | Item | ICP value | Architectural risk | Dependency | Why this rank |
|---|---|---|---|---|---|
| **1** | **Item 1 — bank/processor three-way (PR-A/B/C)** | **Highest.** Cash reconciliation is the core field-service close pain; the spec targets exactly the ICP (one processor, one UF account, one bank, one period). | **Moderate but contained.** Spec is frozen, scope-locked, and emits only existing classes. Risk is in the four unresolved spec gaps below, not the design. | **None unbuilt.** Item 5 has shipped, which was its stated roadmap pre-condition. | Highest value, no blocking dependency, and the spec is already frozen — the only work left is closing four gaps and building it. |
| | ↳ **Prerequisite gaps (Tour 3 E.1–E.4), all re-verified still open** | | | | **E.1** `_classify` reads `m.fee_pct`, which the frozen `BatchMatch` does not declare (confirmed: 1 usage, 0 declarations). **E.2** the fee formula's `else` branch reads `bank.amount`, undefined for a two-way FSM+GL match. **E.3** `settlement_date` precedence unstated — PZ-200's whole classification depends on it. **E.4** `match_id` is required but its construction is unspecified. E.1 and E.4 block **PR-A** specifically, since PR-A ships the model. |
| **2** | **Item 4 — RMR account-count vs GL** | Medium-high. Recurring-revenue roster vs GL is a real alarm/HVAC close step. | Moderate. Spec says class stays `stale_reference`; the risk is re-widening the #11 cutoff allowlist, which the spec explicitly forbids. | **Blocked on Item 1.** The spec's own pre-condition is "Item 1 shipped (roadmap)". | Real value, but gated behind rank 1 by an explicit roadmap dependency. Nothing exists yet — zero `RMR`/`roster_count` references in `backend/`. |
| **3** | **Item 3 — central-station wholesale accrual** | Low-medium. Alarm-only; HVAC in the same wave doesn't have this vendor. | Moderate. The honest story is `active_count × rate`; a "if COGS is big, accrue" hint would invent wholesale. | **Blocked on Item 4** — it needs Item 4's counts — and therefore transitively on Item 1. | Deepest dependency chain of the parked set, and narrowest audience. Today's supplier-vs-GL path already covers it when the invoice lands. |
| **4** | **Item 2 — truck stock / van inventory** | Low for the ICP. 5–40 person shops typically expense van parts on purchase. | **High.** A true cycle-count is a balance-sheet rollforward that `monthly_entries`' unique `(company_id, account_id, period)` cannot hold; JSONB hints can't represent a quantity rollforward. Building it would commit the product to an inventory engine. | None technical — blocked on **evidence**. | Parked on architectural risk, not sequence. **Revisit when** a dealer supplies a real count-vs-GL workbook (SKU, qty, location, opening), not a purchases register. |
| **5** | **Item 6 — WIP / professional services** | **Not the ICP at all** — documented second vertical. | High. Needs job grain (`job_id`, contract value, cost-to-date, billed-to-date, `% complete`) that Discovery drops and `groupby("account")` destroys. Unbilled vs write-off is human collectability. | Blocked on a **product decision**, plus Items 1 and 5 existing. | Lowest: wrong vertical, highest data-model mismatch, and needs an explicit decision to sell professional services before any spec work. |

---

# IronLedger Development Audit

Audit target: cumulative PR-stack snapshot `31492f9`, compared with `main` at
`a876a73`.

## Executive conclusion

Most implementation claims are technically present and their tests pass on the
stacked feature branches. They have not landed on `main`.

More importantly, the numeric guardrail does not currently enforce the stated
golden rule: it trusts `numbers_used` without checking the narrative text and
accepts deviations of up to $1,000 for small values. The stack should not be
treated as production-ready until that is corrected.

## A. Verification table

| Claim | Status | Evidence and finding |
|---|---|---|
| Three-bucket triage methodology | **Partially verified** | The document defines Bucket 1/2/3 as described in [`docs/sprint/field-service-close-triage.md:12-20`](https://github.com/jansoganci/iron-ledger/blob/31492f9/docs/sprint/field-service-close-triage.md#L12-L20), and the research mapping is internally consistent at [lines 403-412](https://github.com/jansoganci/iron-ledger/blob/31492f9/docs/sprint/field-service-close-triage.md#L403-L412). It is not a current status document: it says “planning only” and “no implementation” at [lines 3-8](https://github.com/jansoganci/iron-ledger/blob/31492f9/docs/sprint/field-service-close-triage.md#L3-L8), still says `0010` does not exist at line 22, and contains nine Bucket 1 headings, not six, at [lines 220-327](https://github.com/jansoganci/iron-ledger/blob/31492f9/docs/sprint/field-service-close-triage.md#L220-L327). |
| `_is_material` dollar AND percent | **Partially verified** | The ordinary gate is `$100 AND >5%`, but a separate `$500` hard-dollar OR remains: [`backend/agents/consolidator.py:328-341`](https://github.com/jansoganci/iron-ledger/blob/31492f9/backend/agents/consolidator.py#L328-L341). PR #2 accurately states the full formula. Negative cases cover `$100/1%`, `$400/2%`, missing percentages, and the `$500` override in [`tests/agents/test_consolidator.py:191-211`](https://github.com/jansoganci/iron-ledger/blob/31492f9/tests/agents/test_consolidator.py#L191-L211) and [lines 214-307](https://github.com/jansoganci/iron-ledger/blob/31492f9/tests/agents/test_consolidator.py#L214-L307). Thus “no OR” is literally false; “fixed to the documented combined rule” is true. |
| Deterministic PAYROLL detection | **Verified on stack; not landed** | `is_payroll_account` is a case-insensitive substring helper with the five claimed needles and no LLM/I/O: [`backend/tools/account_tags.py:1-27`](https://github.com/jansoganci/iron-ledger/blob/31492f9/backend/tools/account_tags.py#L1-L27). `calculate_variance` consumes the canonical account name at [`backend/agents/comparison.py:73-79`](https://github.com/jansoganci/iron-ledger/blob/31492f9/backend/agents/comparison.py#L73-L79). Positive and negative tests are at [`tests/tools/test_account_tags.py:10-47`](https://github.com/jansoganci/iron-ledger/blob/31492f9/tests/tools/test_account_tags.py#L10-L47). PR #5 is still open; PR #16 copied the helper into its stack. |
| Coverage/exception split via `card_kind` | **Verified on stack; not landed** | The domain field remains separate from the six-class enum: [`backend/domain/contracts.py:186-200`](https://github.com/jansoganci/iron-ledger/blob/31492f9/backend/domain/contracts.py#L186-L200). Consolidator assigns coverage only to GL-only items at [`backend/agents/consolidator.py:299-315`](https://github.com/jansoganci/iron-ledger/blob/31492f9/backend/agents/consolidator.py#L299-L315); interpreter prevents Claude from reclassifying them at [`backend/agents/interpreter.py:108-145`](https://github.com/jansoganci/iron-ledger/blob/31492f9/backend/agents/interpreter.py#L108-L145). The claimed UI component genuinely exists and separates coverage at [`frontend/src/components/ReconciliationPanel.tsx:32-105`](https://github.com/jansoganci/iron-ledger/blob/31492f9/frontend/src/components/ReconciliationPanel.tsx#L32-L105). Tests include malicious/incorrect Claude classification at [`tests/agents/test_interpreter_classify.py:28-48`](https://github.com/jansoganci/iron-ledger/blob/31492f9/tests/agents/test_interpreter_classify.py#L28-L48). |
| Customer deposit vs processor fee hints | **Partially verified** | Both fields exist and are deterministically computed before interpreter enforcement: [`backend/domain/contracts.py:180-183`](https://github.com/jansoganci/iron-ledger/blob/31492f9/backend/domain/contracts.py#L180-L183), [`backend/tools/hint_computer.py:123-157`](https://github.com/jansoganci/iron-ledger/blob/31492f9/backend/tools/hint_computer.py#L123-L157), and [`backend/agents/interpreter.py:126-145`](https://github.com/jansoganci/iron-ledger/blob/31492f9/backend/agents/interpreter.py#L126-L145). The tests prove separate hints and forced classes at [`tests/tools/test_deposit_vs_fee.py:50-147`](https://github.com/jansoganci/iron-ledger/blob/31492f9/tests/tools/test_deposit_vs_fee.py#L50-L147). However, `_is_processor_fee_gap` treats any two-sided 3–8% difference as processor netting, without checking file/account identity or direction: [`backend/tools/hint_computer.py:284-296`](https://github.com/jansoganci/iron-ledger/blob/31492f9/backend/tools/hint_computer.py#L284-L296). No ordinary two-sided 5% non-processor negative test exists. |
| Restricted `crosses_period_boundary` | **Verified, with residual risk** | The allowlist/blocklist and contracts-roster exclusion are implemented at [`backend/tools/hint_computer.py:79-103`](https://github.com/jansoganci/iron-ledger/blob/31492f9/backend/tools/hint_computer.py#L79-L103) and [lines 175-223](https://github.com/jansoganci/iron-ledger/blob/31492f9/backend/tools/hint_computer.py#L175-L223). Negative tests cover Last Billed, renewal, payout-period text, and a contracts file with a generic `date` column at [`tests/tools/test_hint_computer.py:137-212`](https://github.com/jansoganci/iron-ledger/blob/31492f9/tests/tools/test_hint_computer.py#L137-L212). It still scans every row in each involved file rather than rows belonging to the reconciliation account. |
| Same-item annual prepayment approximately 12× | **Partially verified** | Same-item absolute GL/source ratio, ±10%, side floor, deposit/fee exclusion, and pandas-derived `implied_monthly` are implemented at [`backend/tools/hint_computer.py:346-376`](https://github.com/jansoganci/iron-ledger/blob/31492f9/backend/tools/hint_computer.py#L346-L376). Negative tests retire the old cross-account `delta × 12` false positive and exclude coverage/deposit/fee at [`tests/tools/test_annual_prepayment.py:68-119`](https://github.com/jansoganci/iron-ledger/blob/31492f9/tests/tools/test_annual_prepayment.py#L68-L119). It is not fully guardrail-wired; see section B. |
| Migration `0010_add_company_monthly_scale.sql` | **Verified on stack; unverified as applied** | The nullable column and four-value CHECK exist at [`supabase/migrations/0010_add_company_monthly_scale.sql:1-19`](https://github.com/jansoganci/iron-ledger/blob/31492f9/supabase/migrations/0010_add_company_monthly_scale.sql#L1-L19). Existing company RLS covers the added column through the owner policy at [`supabase/migrations/0001_initial_schema.sql:138-151`](https://github.com/jansoganci/iron-ledger/blob/31492f9/supabase/migrations/0001_initial_schema.sql#L138-L151). Whether it has been applied to a live Supabase project is unverified. |
| `_gates_from_band` output for all bands | **Verified** | Formula and representative revenue values are at [`backend/agents/comparison.py:23-46`](https://github.com/jansoganci/iron-ledger/blob/31492f9/backend/agents/comparison.py#L23-L46). Outputs are: `under_100k=(1250,250)`, `100k_250k=(4375,875)`, `250k_500k=(9375,1875)`, and `500k_plus=(50000,10000)`. Exact assertions are at [`tests/agents/test_comparison.py:173-195`](https://github.com/jansoganci/iron-ledger/blob/31492f9/tests/agents/test_comparison.py#L173-L195). |
| NULL/unknown fail-safe | **Verified** | `None`, empty, and unknown bands return legacy `$50k/$10k` at [`backend/agents/comparison.py:38-46`](https://github.com/jansoganci/iron-ledger/blob/31492f9/backend/agents/comparison.py#L38-L46); tests explicitly reject zero floors at [`tests/agents/test_comparison.py:193-201`](https://github.com/jansoganci/iron-ledger/blob/31492f9/tests/agents/test_comparison.py#L193-L201). |
| POST remains idempotent; PATCH is existing-row update path | **Verified** | The existing-company branch returns without update/create at [`backend/api/routes.py:1277-1290`](https://github.com/jansoganci/iron-ledger/blob/31492f9/backend/api/routes.py#L1277-L1290). `PATCH /companies/me` is the existing-row writer at [lines 1316-1342](https://github.com/jansoganci/iron-ledger/blob/31492f9/backend/api/routes.py#L1316-L1342). The idempotency test asserts neither `update` nor `create` is called at [`tests/api/test_companies_band.py:66-83`](https://github.com/jansoganci/iron-ledger/blob/31492f9/tests/api/test_companies_band.py#L66-L83). Creation naturally writes the initial band; therefore “only band-update path” is accurate for existing rows, not initial inserts. |
| `237 passed, 5 skipped` | **Verified** | Reproduced on `31492f9`: exactly `237 passed, 5 skipped`. The five skips are four missing DRONE binary-fixture tests and one documented NetSuite XML edge case in `tests/integration/test_parser_end_to_end.py`; none concerns the audited feature paths. |
| Kova 1 reconciliation tests unaffected by Item 5 | **Verified** | The cross-cutting matrix states no `calculate_variance` dependency at [`docs/sprint/kova2-implementation-plan.md:1384-1398`](https://github.com/jansoganci/iron-ledger/blob/31492f9/docs/sprint/kova2-implementation-plan.md#L1384-L1398). Source inspection found no such calls in the five claimed files. The exact PR #16 subset result was reproduced: `99 passed`. The Item 5 commit changed none of those files. |
| Item 1 locked design | **Verified** | The single-processor/single-UF/single-bank/single-period boundary, ID-first match, exact-cent/same-day fallback, pandas-only math, and five states are explicit at [`docs/sprint/kova2-implementation-plan.md:575-590`](https://github.com/jansoganci/iron-ledger/blob/31492f9/docs/sprint/kova2-implementation-plan.md#L575-L590). |
| Item 1 remains unimplemented | **Verified** | No `batch_matcher.py`, `BatchMatch`, bank/processor source literals, or matcher tests exist. `SourceFileType` remains four literals at [`backend/domain/contracts.py:18-23`](https://github.com/jansoganci/iron-ledger/blob/31492f9/backend/domain/contracts.py#L18-L23), and unknown filenames still fall back to `supplier_invoices` at [`backend/agents/orchestrator.py:513-534`](https://github.com/jansoganci/iron-ledger/blob/31492f9/backend/agents/orchestrator.py#L513-L534). PR #17 changes only the planning document. |
| Isolated three-file fixture exists | **Contradicted if interpreted as checked-in files** | The fixture is specified for a later PR at [`docs/sprint/kova2-implementation-plan.md:1114-1127`](https://github.com/jansoganci/iron-ledger/blob/31492f9/docs/sprint/kova2-implementation-plan.md#L1114-L1127), but none of the three `kova_cash_*.csv` files exists. PR #17’s changed-file list contains only `docs/sprint/kova2-implementation-plan.md`. |

### Delivery-state caveat

PRs #2, #4, #5, #9, #11, #13, #16, and #17 are all open; most are drafts.
None of their feature commits is an ancestor of `main`. The current local
working tree is also dirty and contains only a partial mixture of coverage/UI
edits, not the complete stack.

## B. Golden-rule compliance

The named calculations themselves comply:

- Consolidator deltas and materiality are Python at
  [`backend/agents/consolidator.py:280-341`](https://github.com/jansoganci/iron-ledger/blob/31492f9/backend/agents/consolidator.py#L280-L341).
- Annual ratios are Python at
  [`backend/tools/hint_computer.py:346-376`](https://github.com/jansoganci/iron-ledger/blob/31492f9/backend/tools/hint_computer.py#L346-L376).
- Scaled flux arithmetic is Python at
  [`backend/agents/comparison.py:38-82`](https://github.com/jansoganci/iron-ledger/blob/31492f9/backend/agents/comparison.py#L38-L82).
- The monthly prompt explicitly forbids arithmetic at
  [`backend/prompts/narrative_prompt.txt:60-73`](https://github.com/jansoganci/iron-ledger/blob/31492f9/backend/prompts/narrative_prompt.txt#L60-L73).

The guardrail, however, does not enforce the golden rule:

1. It iterates only `claude_json["numbers_used"]`; it never parses numeric
   tokens from `narrative`:
   [`backend/tools/guardrail.py:42-53`](https://github.com/jansoganci/iron-ledger/blob/31492f9/backend/tools/guardrail.py#L42-L53).
   A narrative containing `$999,999` with `numbers_used=[]` passes. This was
   reproduced directly.

2. Its tolerance is `max(1% of reference, $1,000)` at
   [`backend/tools/guardrail.py:15-24`](https://github.com/jansoganci/iron-ledger/blob/31492f9/backend/tools/guardrail.py#L15-L24).
   A claimed value of `999` passed against a pandas reference of `1`. For an
   SMB-focused product, this is not meaningful numeric verification.

3. `implied_monthly` is supplied to Claude and requested in the narrative at
   [`backend/prompts/narrative_prompt.txt:51-54`](https://github.com/jansoganci/iron-ledger/blob/31492f9/backend/prompts/narrative_prompt.txt#L51-L54),
   but interpreter guardrail references include only `gl_amount`,
   `non_gl_total`, `delta`, and source amounts:
   [`backend/agents/interpreter.py:334-347`](https://github.com/jansoganci/iron-ledger/blob/31492f9/backend/agents/interpreter.py#L334-L347).
   A valid large-value annual case can therefore fail. A valid `100,000`
   implied monthly amount was reproduced as rejected when the two sides were
   `1,200,000` and `110,000`.

4. The reinforced retry prompt contains no reconciliation context or
   instructions at
   [`backend/prompts/narrative_prompt_reinforced.txt:7-29`](https://github.com/jansoganci/iron-ledger/blob/31492f9/backend/prompts/narrative_prompt_reinforced.txt#L7-L29),
   even though interpreter switches to it after a failed first attempt at
   [`backend/agents/interpreter.py:349-371`](https://github.com/jansoganci/iron-ledger/blob/31492f9/backend/agents/interpreter.py#L349-L371).
   A retry may silently omit the reconciliation narrative and still persist.

5. Existing non-Kova prompts also violate the strict rule.
   `opus_narrative_prompt.txt` asks Claude for “net position if derivable” at
   [`backend/prompts/opus_narrative_prompt.txt:13-17`](https://github.com/jansoganci/iron-ledger/blob/31492f9/backend/prompts/opus_narrative_prompt.txt#L13-L17).
   The quarterly prompt asks Claude to produce `{N} of {M}` and `year-1` at
   [`backend/prompts/quarterly_report_prompt.txt:17-36`](https://github.com/jansoganci/iron-ledger/blob/31492f9/backend/prompts/quarterly_report_prompt.txt#L17-L36),
   rather than receiving those deterministic values.

Conclusion: “Claude never computes” is verified for the new feature algorithms,
but contradicted as a system-wide enforcement claim.

## C. Scope discipline

- Six classes remain fixed at
  [`backend/domain/contracts.py:9-16`](https://github.com/jansoganci/iron-ledger/blob/31492f9/backend/domain/contracts.py#L9-L16).
  `coverage` is correctly a separate `card_kind`, not a seventh class.
- Migration filenames are contiguous `0001` through `0010`, all using four
  digits and snake case. No gap, reuse, or unexpected `0011` exists.
- `0010` is the only schema addition in the stack and was explicitly planned.
  Item 1 introduced no SQL, source type, matcher, or fixture files.
- PR #16 includes PAYROLL tagging although PR #5 was separate, but this was
  explicit—not quiet scope expansion—at
  [`docs/sprint/kova2-implementation-plan.md:46-47`](https://github.com/jansoganci/iron-ledger/blob/31492f9/docs/sprint/kova2-implementation-plan.md#L46-L47).

No seventh class or unplanned migration was found. Live migration application
and live RLS behavior are unverified because no remote database was touched.

## D. Test integrity

Reproduced results:

- Full cumulative stack: `237 passed, 5 skipped`.
- Exact PR #16 “Kova 1 unchanged” subset: `99 passed`.
- Expanded audited-feature subset: `156 passed`.
- Frontend typecheck: passed.
- Frontend production build: passed, with only Vite’s existing large-chunk
  warning.

The negative tests are real and passing, particularly:

- AND-gate false positives:
  [`tests/agents/test_consolidator.py:214-279`](https://github.com/jansoganci/iron-ledger/blob/31492f9/tests/agents/test_consolidator.py#L214-L279).
- Non-payroll names and absent values:
  [`tests/tools/test_account_tags.py:30-47`](https://github.com/jansoganci/iron-ledger/blob/31492f9/tests/tools/test_account_tags.py#L30-L47).
- Coverage resisting Claude’s `missing_je`:
  [`tests/agents/test_interpreter_classify.py:28-48`](https://github.com/jansoganci/iron-ledger/blob/31492f9/tests/agents/test_interpreter_classify.py#L28-L48).
- Renewal/roster cutoff false positives:
  [`tests/tools/test_hint_computer.py:137-212`](https://github.com/jansoganci/iron-ledger/blob/31492f9/tests/tools/test_hint_computer.py#L137-L212).
- Retired annual cross-account false positive:
  [`tests/tools/test_annual_prepayment.py:68-92`](https://github.com/jansoganci/iron-ledger/blob/31492f9/tests/tools/test_annual_prepayment.py#L68-L92).
- Invalid/unknown revenue bands and idempotent POST:
  [`tests/agents/test_comparison.py:173-201`](https://github.com/jansoganci/iron-ledger/blob/31492f9/tests/agents/test_comparison.py#L173-L201),
  [`tests/api/test_companies_band.py:49-83`](https://github.com/jansoganci/iron-ledger/blob/31492f9/tests/api/test_companies_band.py#L49-L83).

Missing tests:

- No narrative-token-versus-`numbers_used` consistency test.
- No annual `implied_monthly` guardrail integration test.
- No ordinary two-sided 3–8% non-processor negative case.
- No unrelated-account future date/deposit row leakage test.
- No browser/component behavior tests for coverage; only typecheck/build and
  backend unit tests.

Repository-required formatting checks do not pass:

- `black --check backend tests` reports seven files requiring formatting,
  including `interpreter.py`, `hint_computer.py`, and feature tests.
- `flake8 backend tests` fails broadly, including unused imports in
  `consolidator.py`, `interpreter.py`, and `test_deposit_vs_fee.py`.

Many flake8 failures predate this stack, so attributing all of them to these PRs
would be unverified.

## E. Additional concerns

### 1. Critical: guardrail false assurance

The `$1,000` floor and unparsed narrative mean a report can be marked verified
while containing an omitted or materially wrong SMB-scale number. This is the
highest-risk finding.

### 2. High: hint leakage across accounts

`_crosses_period_boundary` scans the whole involved file, and
`_deposit_column_signal` scans all rows in it at
[`backend/tools/hint_computer.py:175-207`](https://github.com/jansoganci/iron-ledger/blob/31492f9/backend/tools/hint_computer.py#L175-L207)
and [lines 252-281](https://github.com/jansoganci/iron-ledger/blob/31492f9/backend/tools/hint_computer.py#L252-L281).
One future invoice or deposit row can influence every reconciliation item tied
to that file.

### 3. High: processor-fee signal is weaker than its name

A generic two-sided 5% discrepancy is deterministically forced to
`structural_explained`, including overriding Claude, even without
processor/payout evidence. That can convert a real exception into “no action
required.”

### 4. Medium: broad hint-computation fallback

`compute_hints` catches every exception and returns an empty hint object at
[`backend/tools/hint_computer.py:158-167`](https://github.com/jansoganci/iron-ledger/blob/31492f9/backend/tools/hint_computer.py#L158-L167).
A hint-engine defect silently degrades classification rather than failing the
run or exposing an auditable error.

### 5. Medium: stacked delivery is fragile

PR #16 targets PR #15 rather than `main`, PR #17 targets PR #16, and PAYROLL
was independently implemented in PR #5 and copied into PR #16. Tests prove the
cumulative snapshot works; they do not make any of it shipped. Until the stack
is rebased or merged coherently, “complete” should mean “implemented on an open
branch,” not “available in IronLedger.”

## Verification commands run

```text
pytest -q
237 passed, 5 skipped

pytest -q \
  tests/tools/test_deposit_vs_fee.py \
  tests/tools/test_annual_prepayment.py \
  tests/tools/test_hint_computer.py \
  tests/agents/test_consolidator.py \
  tests/agents/test_interpreter_classify.py
99 passed

Expanded audited-feature subset
156 passed

npm run typecheck
passed

npm run build
passed

black --check backend tests
failed: 7 files would be reformatted

flake8 backend tests
failed: broad existing style and unused-import violations
```

---

# Tour 2 — Item 5 (Revenue-Scaled Materiality)

Audit target: `c63d13a` ("feat: scale flux gates from company monthly revenue
band"), evaluated within the cumulative stack snapshot `31492f9`, compared with
`main` at `a876a73`.

**File-path note:** the task specified `docs/sprint/audit_results.md`. No such
file exists; `docs/sprint/` contains only `pre-analysis-coverage-ui.md`. Tour 1
lives at `docs/audit_results.md`, so this section is appended there. Tour 1
content is unmodified above.

## Executive conclusion

Item 5 holds up. All seven claims are verified against the code; the band→gate
arithmetic was recomputed independently rather than trusted, and every named
test exists with real assertions. Scope discipline is clean: exactly one
migration, consolidator materiality untouched, six classes unchanged.

Two caveats, neither fatal. Two of the named tests do not actually discriminate
Tier 1 from Tier 2 — they pass either way, so they do not prove what their names
claim (the routing *is* proven, by a different test). And migration `0010` is
not re-runnable: the column add is guarded, the CHECK constraint is not.

## A. Verification table

| Claim | Status | File:line citation | Test citation | Notes |
|---|---|---|---|---|
| **1. Migration `0010`** — nullable TEXT column, four-value CHECK, no backfill, no new table, RLS unchanged, highest-numbered, no `0011` | **Verified** (on stack; unverified as applied to a live DB) | `supabase/migrations/0010_add_company_monthly_scale.sql:6-19` | n/a (schema) | Confirmed by reading the file: `ADD COLUMN IF NOT EXISTS monthly_revenue_band TEXT`, CHECK allows `NULL` OR exactly the four values. `git ls-tree 31492f9 supabase/migrations/` shows `0001`–`0010`, contiguous, no `0011`. `git diff a876a73 31492f9 -- supabase/` returns a single `A` line for `0010`. No backfill statement, no `CREATE TABLE`, no `POLICY`/`GRANT` — RLS inherited from the existing owner policy at `0001_initial_schema.sql:138-151`. **Not idempotent** — see E.1. Live application unverified (no remote DB touched). |
| **2. `_gates_from_band` exact pairs** | **Verified** — math recomputed independently | `backend/agents/comparison.py:30-46` | `tests/agents/test_comparison.py:173-201` | Formula read as `max(500.0, 0.025*r), max(250.0, 0.005*r)` over `_BAND_R = {under_100k: 50_000, 100k_250k: 175_000, 250k_500k: 375_000, 500k_plus: 2_000_000}`. I computed each pair rather than trusting the claim: `under_100k` → `max(500,1250)/max(250,250)` = **1250/250**; `100k_250k` → `max(500,4375)/max(250,875)` = **4375/875**; `250k_500k` → `max(500,9375)/max(250,1875)` = **9375/1875**; `500k_plus` → `max(500,50000)/max(250,10000)` = **50000/10000**. All match. NULL/unknown returns `_TIER1_DOLLAR, _TIER2_DOLLAR` (line 43-44) — the legacy constants *by identity*, not by recomputation, which is the stronger guarantee. Note `under_100k`'s t2 is the `$250` floor and the formula coinciding exactly. |
| **3. Tier 2 eligibility; dead categories removed** | **Verified** | `backend/agents/comparison.py:75`; `backend/tools/account_tags.py:17-27`; `supabase/migrations/0001_initial_schema.sql:36-44` | `tests/agents/test_comparison.py:81-90`, `:93-101` | `is_tier2 = category == "REVENUE" or is_payroll_account(account_name)` — read at line 75. `git grep _TIER2_CATEGORIES 31492f9` returns **zero code hits**: removed, not supplemented. The only surviving `PAYROLL`/`DEFERRED_REVENUE` strings in `backend/` are a docstring at `comparison.py:63`. Seeded categories confirmed as exactly `REVENUE, COGS, OPEX, G&A, R&D, OTHER_INCOME, OTHER` — **no PAYROLL, no DEFERRED_REVENUE**, so the old gate provably never fired. `test_deferred_revenue_category_is_not_tier2` locks this in. |
| **4. API: idempotent POST / PATCH-only update / required band** | **Verified** — all three sub-claims independently | `backend/api/routes.py:1279-1290` (POST early-return), `:1316-1342` (PATCH), `:119` + `:123` (`Literal` band, no default) | `tests/api/test_companies_band.py:49,54,67,87,103,123,132` | (a) POST: existing-company branch returns `JSONResponse(200, _company_public(existing))` and returns *before* any `create`/`update` call; test at `:67-83` asserts `repo.update.assert_not_called()` **and** `repo.create.assert_not_called()`. (b) PATCH `/companies/me` is the sole existing-row writer (docstring says so, and it is the only route calling `companies_repo.update`); test `:87-99` asserts `update.assert_called_once_with(COMPANY_ID, monthly_revenue_band="100k_250k")`; cache invalidation covered at `:103-115`. (c) `monthly_revenue_band: Literal[...]` with no default → required → 422; tests at `:49` (omitted) and `:54` (invalid value). **seed.sql is unaffected**: `supabase/seed.sql:7` inserts DRONE via raw `INSERT INTO companies (owner_id, name, currency)`, bypassing the endpoint; it does not set the band (grep confirms absent) → stays NULL → fail-safe gates. See E.3. |
| **5. Test results `237 passed, 5 skipped` + seven named tests** | **Verified** — reproduced | `tests/agents/test_comparison.py:173,177,193,212,225,238,251` | all seven located by `git grep "def <name>"` | Reproduced exactly on `31492f9` in a clean detached worktree: **`237 passed, 5 skipped`**. All seven named tests exist with real assertions, not stubs — bodies read at `:173-274`. Two of them are non-discriminating; see E.2. |
| **6. Kova 1 isolation (99 tests unchanged)** | **Verified** | n/a | `tests/tools/test_deposit_vs_fee.py`, `test_annual_prepayment.py`, `test_hint_computer.py`, `tests/agents/test_consolidator.py`, `test_interpreter_classify.py` | Grepped all five files at `31492f9` for `calculate_variance`, `ComparisonAgent`, and `comparison`: **zero hits in all five**. The isolation claim is true, not merely asserted. Corroborated structurally in section D — the dependency is absent in both directions, so no expected-value change was possible. |
| **7. UI shows labels only; browser verification absent** | **Verified** (both halves — including that the gap is still open) | `frontend/src/components/RevenueBandField.tsx:2-5` | `tests/api/test_companies_band.py` (backend only) | `git grep` for `4375\|1250\|9375\|50000\|dollar_t1\|dollar_t2` across `frontend/src/` returns **nothing** — no raw floor reaches the UI. `RevenueBandField.tsx:2-5` defines exactly four options with plain-English labels ("Under $100k / month", "$100k–$250k / month", "$250k–$500k / month", "$500k+ / month"); `ProfilePage.tsx:139` renders via `bandLabel()`. The band values shown are *user-facing revenue ranges*, not computed materiality floors — the claim is honored. **The no-browser-verification caveat still stands:** `git ls-tree -r 31492f9` matched no Playwright, Cypress, `e2e`, `.spec.`, screenshot, or `.png` artifact anywhere. Frontend evidence remains typecheck + build only. No later confidence in any PR description changes this. |

## B. Golden-rule compliance check

**Compliant. Claude never sees a scaled gate, and never computes one.**

Traced the full path:

- The gates are computed in pandas-land and consumed in pandas-land:
  `_gates_from_band` (`backend/agents/comparison.py:38-46`) → `calculate_variance(..., dollar_t1=, dollar_t2=)` (`:167-175`) → `flag` (`:79`). All arithmetic is Python.
- **The band never enters `PandasSummary`.** The returned object is built at
  `backend/agents/comparison.py:253-257` with exactly `accounts`, `period`,
  `company_id`. No band, no `dollar_t1`/`dollar_t2`, no `R`.
- The band's only other appearance in the agent is a **log field** at
  `comparison.py:248` (`logger.info("comparison complete", extra={...})`) — a
  log, not a model input, and it logs the band string only, no cell values.
- `git grep -i "monthly_revenue_band\|revenue_band" 31492f9 -- backend/prompts/`
  → **no prompt references the band.** Grepping `narrative_prompt.txt` for
  `band|gate|threshold|materiality|4375|1250|50000` → **no matches.**
- Claude therefore receives only already-flagged `AccountSummary` rows
  (`account, category, current, historical_avg, variance_pct, severity`), every
  field pandas-computed at `:178-189`.

Item 5 introduces **no** new number for Claude to narrate, so it adds no new
guardrail surface. Note this is a statement about Item 5 only — it does not
soften Tour 1 section B, where the guardrail's `$1,000` floor and unparsed
narrative remain the highest-risk open finding.

## C. Scope discipline check

All three checks pass.

- **Exactly one new migration.** `git diff --name-status a876a73 31492f9 -- supabase/`
  returns a single line: `A supabase/migrations/0010_add_company_monthly_scale.sql`.
  No `0011`, no modification to any existing migration, no change to `seed.sql`.
- **Recon thresholds untouched.** `git show --name-only c63d13a` does **not**
  list `backend/agents/consolidator.py`. `_is_material` at
  `backend/agents/consolidator.py:328-341` still reads `$500` hard-dollar OR
  (`$100` AND >5%) — identical to what Tour 1 audited. The `$100`/`$500`
  constants were not touched by Item 5. (The commit message's "Recon
  `_is_material` unchanged" is accurate.)
- **Six classes unchanged.** `ReconciliationClassification` at
  `backend/domain/contracts.py:9-16` remains exactly `timing_cutoff`,
  `categorical_misclassification`, `missing_je`, `stale_reference`,
  `accrual_mismatch`, `structural_explained`. `contracts.py` is not in
  `c63d13a`'s changed-file list at all. No seventh class.

Item 5's full footprint is 17 files (`git show --name-status c63d13a`): 3 new
backend/frontend source files, 1 migration, 3 test files, and 10 modifications
— all within the band feature's blast radius. Nothing incidental.

## D. Cross-tour interaction check

**Architecturally independent, verified in both directions — not merely claimed.**

- **Kova 1 → comparison:** grepped `backend/agents/consolidator.py`,
  `backend/tools/hint_computer.py`, and `backend/agents/interpreter.py` for
  `calculate_variance`, `_gates_from_band`, `ComparisonAgent`,
  `monthly_revenue_band`, `dollar_t1`, `dollar_t2`, and
  `from backend.agents.comparison` → **zero hits in all three files.**
- **comparison → Kova 1:** grepped `backend/agents/comparison.py` for
  `ReconciliationClassification`, `card_kind`, `consolidat` → **zero hits.**

The two layers operate on different inputs and produce different outputs:
`calculate_variance` consumes `monthly_entries` history and writes `anomalies`
(flux); the consolidator/hint/interpreter path consumes multi-source
reconciliation items and writes `card_kind` + one of six classes. There is no
shared threshold, no shared constant, and no call edge.

**Answering the specific question:** a band change alters `dollar_t1`/`dollar_t2`,
which alters only the `flag` boolean at `comparison.py:79`. That boolean feeds
`Anomaly` construction (`:192`). It is never read by `_is_material`, by
`compute_hints`, or by the interpreter's classification enforcement. So a
"bigger flux flag" **cannot** reclassify a coverage card or a deposit/fee card
— confirmed structurally, not by assertion. Tour 1's 99-test result standing
unchanged is a consequence of this, not a coincidence.

## E. Anything concerning that wasn't explicitly claimed

Scoped to Item 5's footprint only. Item 1 and parked items 2/3/6 excluded.

### E.1 — Medium: migration `0010` is not re-runnable

`ADD COLUMN IF NOT EXISTS` (line 7) is guarded; `ADD CONSTRAINT` (line 10) is
not. PostgreSQL has no `ADD CONSTRAINT IF NOT EXISTS`, so a second application
of `0010` fails with a duplicate-object error on
`companies_monthly_revenue_band_chk` — after the column add silently no-ops.
The file's own header comment implies safe re-application, and `seed.sql:5`
advertises "safe to re-run" as a repo norm. This is the only `ADD CONSTRAINT`
in the entire migration set (`git grep "ADD CONSTRAINT" 31492f9 -- supabase/migrations/`),
so there is no established guard pattern to have copied. Low blast radius —
`supabase db push` tracks applied migrations — but it will bite anyone
re-running by hand or rebuilding a local DB from a partial state.

### E.2 — Medium: two named tests do not discriminate Tier 1 from Tier 2

`test_icp_100k_250k_salaries_flags` (`:212`) and
`test_payroll_name_uses_tier2_of_band` (`:251`) both assert `flag is True` for
`43_500` vs `38_000` — delta `$5,500`, `14.47%`. I re-ran each case with the
payroll name stripped (forcing the Tier 1 path) and compared:

```
test_icp_100k_250k_salaries_flags     band=100k_250k t1=4375 t2=875
  with payroll name (Tier2)=True | without (Tier1)=True | DISCRIMINATES=False
test_payroll_name_uses_tier2_of_band  band=under_100k t1=1250 t2=250
  with payroll name (Tier2)=True | without (Tier1)=True | DISCRIMINATES=False
```

Both cases clear the Tier 1 gate on their own (`5500 > 4375` and `14.47 > 10`;
`5500 > 1250` and `14.47 > 10`). The tests would still pass if
`is_payroll_account` were deleted from line 75. `test_payroll_name_uses_tier2_of_band`
in particular does not test what its name asserts.

This is a test-quality gap, **not** a code defect — the routing genuinely works
and *is* proven by `test_tier2_payroll_fires_at_lower_gates` (`:81-90`), which
I confirmed does discriminate:

```
test_tier2_payroll_fires_at_lower_gates  band=None t1=50000 t2=10000
  with payroll name (Tier2)=True | without (Tier1)=False | DISCRIMINATES=True
```

Fix is cheap: pick a delta between the band's `t2` and `t1` (e.g. `$1,000` on a
`100k_250k` base, or a sub-10% percentage) so only the Tier 2 path can flag.

### E.3 — Low: seeded demo company gets fail-safe gates, not ICP gates

`supabase/seed.sql:7` inserts DRONE Inc. with `(owner_id, name, currency)` only.
`monthly_revenue_band` is never set, so the demo company runs on the NULL
fail-safe `$50,000 / $10,000` — the exact gates Item 5 exists to replace for
SMB-scale customers. This is correct-by-design behavior (the fail-safe working
as intended) and is *not* a regression, since those were the hardcoded gates
before Item 5. But the seeded demo therefore never exercises the feature. If
any demo narrative is meant to show scaled materiality, it will not. Whether
this changes which demo accounts flag is **unverified** — the `docs/demo_data/`
paths referenced in `CLAUDE.md` (`drone_feb_2026.xlsx`, `drone_mar_2026.xlsx`)
no longer exist; that directory now holds six named company folders instead.
One line in `seed.sql` would close it.

### E.4 — Low: `500k_plus` is unbounded above and under-scaled at the top

`_BAND_R["500k_plus"] = 2_000_000` is reverse-engineered so the formula
reproduces the legacy `$50k/$10k` exactly (`comparison.py:23-25` says as much).
That is a deliberate, well-documented continuity choice. The consequence is
that a `$500k/month` company and a `$5M/month` company receive identical gates,
and for the latter the gates are ~10× too tight. Out of scope for the stated
ICP (5–40 employees, field service), so this is a note rather than a defect —
but the top band is the one place where "revenue-scaled" stops scaling.

### E.5 — Low: percentage gates are not band-scaled

`_TIER1_PCT = 10.0` and `_TIER2_PCT = 3.0` (`comparison.py:26,28`) stay fixed
across all bands; only the dollar gates move. The `AND` of both means the
percentage gate becomes the binding constraint for small companies — e.g. an
`under_100k` company needs a `>10%` swing on a non-payroll account no matter how
small the dollar floor drops. This is consistent with how the feature was
specified and is arguably correct (it suppresses small-dollar noise), but it is
worth stating explicitly: the claim "revenue-scaled materiality" scales one of
the two gates, not both.

### E.6 — Informational: `PATCH /companies/me` rate limit

`@limiter.limit("5/hour")` (`routes.py:1317`) matches POST's limit. Since PATCH
is the only correction path for a mis-selected band, a user who fat-fingers
onboarding gets five corrections per hour. Not a defect; flagging because the
limit was inherited from a create-shaped endpoint rather than chosen for an
update-shaped one.

## Verification commands run (Tour 2)

```text
git ls-tree --name-only 31492f9 supabase/migrations/
  0001..0010, contiguous, no 0011

git diff --name-status a876a73 31492f9 -- supabase/
  A  supabase/migrations/0010_add_company_monthly_scale.sql   (only line)

git show --name-status c63d13a
  17 files; consolidator.py and contracts.py absent

git grep -n "_TIER2_CATEGORIES" 31492f9 -- backend/ tests/
  no code hits (docstring mention only)

git grep -n "monthly_revenue_band" 31492f9 -- backend/prompts/
  no matches

git grep -n "4375\|1250\|9375\|50000\|dollar_t1\|dollar_t2" 31492f9 -- frontend/src/
  no matches

git ls-tree -r --name-only 31492f9 | grep -iE "playwright|e2e|cypress|\.spec\.|screenshot|\.png"
  no matches

pytest -q            (clean detached worktree at 31492f9)
  237 passed, 5 skipped

_gates_from_band recomputed by hand for all five inputs — all five match
Tier1/Tier2 discrimination probe re-run for three payroll tests — 2 of 3 non-discriminating
```

---

# Tour 3 — Item 1 (Bank/Processor Three-Way, Spec-Only)

Audit target: the Item 1 section of
`docs/sprint/kova2-implementation-plan.md` at `31492f9` (spec lines 575–1149),
plus absence-of-code checks against both `31492f9` and the working tree.

**File-path note:** as in Tour 2, the task named `docs/sprint/audit_results.md`;
that file does not exist. Tours 1 and 2 live in `docs/audit_results.md`, so
Tour 3 is appended here. Prior content is unmodified.

**Evidence basis for this tour.** Unlike Tours 1 and 2, almost nothing here is
traceable to running code, because almost no code is supposed to exist. Every
row below is explicitly marked **[spec]** (the document says X) or **[traced]**
(I ran a command against the repo and confirmed X). The absence checks in claim
1, and the spec's own citations into existing code, are the only **[traced]**
items.

## Executive conclusion

**No code leaked. The spec is unusually disciplined and is close to
build-ready.** The scope lock is real, the assumption admissions are written
down rather than glossed, the classification priority is enumerated as
executable pseudocode, and the fixture pins an expected class per row including
a true negative. The spec's own line citations into existing code are accurate
— I spot-checked eleven and all resolved.

Four concrete gaps would stop me writing PR-A code from this document alone,
the sharpest being that `_classify` reads `m.fee_pct`, a field the frozen
`BatchMatch` model does not have. All four are small and fixable in the
document; none is an architectural problem.

One wording defect worth correcting: the claim "the fallback never compares FSM
gross to bank net" is not what the pseudocode does. The outcome is still safe,
but for a different reason than the spec gives.

## A. Verification table

| Claim | Status | Citation | Notes |
|---|---|---|---|
| **1. No premature code leak** | **Verified** **[traced]** | confirmed absent (see below) | Four independent checks, all against both `31492f9` and the working tree. (a) **No matcher module:** `backend/tools/` contains exactly `__init__, excel_export, file_reader, guardrail, hint_computer, normalizer, pii_sanitizer, validator` — no `batch_matcher.py`; `git ls-tree -r 31492f9 \| grep -i match` returns nothing. (b) **`SourceFileType` unchanged:** `backend/domain/contracts.py:18-23` reads exactly `general_ledger, payroll, supplier_invoices, contracts` — byte-identical in both trees, no `bank_statement`, no `processor_settlement`. (c) **No migration beyond `0010`:** `31492f9` holds `0001`–`0010`, working tree `0001`–`0009`; no `0011`. (d) **No `BatchMatch`/`batch_matcher`/`processor_settlement` symbol anywhere.** The single grep hit for `bank_statement` is `tests/agents/test_consolidator.py:83` — `("bank_statement.csv", False)`, a **negative** assertion in the pre-existing `_is_gl_label` test proving a bank file is *not* treated as GL. That predates Item 1 and is the opposite of a leak. The `kova_cash_*.csv` fixtures are also absent, consistent with Tour 1's finding. **No scope violation.** |
| **2. Matching algorithm consistency** | **Partially verified** **[spec]** | spec C.5.1 (join hierarchy, assumptions table, fee block, `_classify`, `match` pseudocode) | **The assumptions admission is fully present and is the strongest part of the document** — a dedicated table headed *"Assumptions (not in the research docs — do not present as derived)"* pins date window `0 days`, dollar tolerance `$0.00` after `round(...,2)`, and records that "±1 business day" was **withdrawn** with the reason ("was a leftover sentence… no research number backs it") and a re-entry condition ("a new go-ahead, not a silent widen"). It also explicitly refuses to import the Amazon 14-day settlement figure from `close-process-by-sector.md` as a different vertical. This is not glossed over. **ID-first join is consistent**: `norm(id) := None if null/blank else str(id).strip().casefold()`, three-way match requires all three equal and non-`None`, and the "one side has an id, another does not" case is handled explicitly (do not invent an id; may meet in fallback only if both still unmatched). **The gross-vs-net claim does not hold as worded** — see E.5. **The fee formula is undefined for one reachable case** — see E.2. |
| **3. Ambiguous match handling** | **Verified**, with one precedence caveat **[spec]** | spec C.5.1 rule (c) and `_classify`; PZ-300 at C.5.2 State 3 | The never-pick rule is stated unambiguously, not implied — rule (c): *"`ambiguous=True`, `candidate_count=max(nf, ng, nb)`, `unmatched=True`, class `stale_reference`. **Never silently pick** the first / largest / closest row. A wrong silent pick would label a real miss as a fee."* Reinforced in Pass 2 (`# (c) do NOT pick first / largest / closest`) and in section E (*"Claude never sees a candidate list and is never asked to pick"*). One card, not several: Pass 2 groups by `(round(net,2), calendar_date)` with an inline comment explaining that per-row looping *"would split two $100 blanks into one stale_reference plus a leftover missing_je — the fixture requires ONE card."* `candidate_count = max(nf,ng,nb)` = 2 for the fixture blanks, and the spec pre-empts the off-by-error (*"fixture blanks: 2, not 4"*). **Priority order is written down as executable pseudocode**, and PZ-300 does demonstrate exactly the claimed point: `fee_pct = 0.04` sits inside the 3–8% band yet resolves to `missing_je`, because `not has_gl` is tested first — with the rationale stated in the prose above the block (*"Do not apply the 3–8% fee band unless a GL row is in the match — otherwise PZ-300… would be labelled `structural_explained` and the state table would be a lie"*). **Caveat:** the claimed order (cutoff → missing GL → wrong UF → fee → `$0` drop → stale) omits that **`ambiguous` is tested first, above cutoff**. The code is right; the summary of it is incomplete. See E.7. |
| **4. Five-state completeness, six classes only** | **Verified** **[spec]** + **[traced]** for enum validity | spec Item 1 state table (line 584–590 region), C.5.2, section E table; `backend/domain/contracts.py:9-16` | Mapping as written: gross/net fee gap → `structural_explained`; payout after `period_end` → `timing_cutoff`; processor batch not in GL → `missing_je`; bank deposit not in GL/UF → `missing_je`; wrong clearing account → `categorical_misclassification`. The ambiguous case adds `stale_reference`. **[traced]** All six named values exist in the live `ReconciliationClassification` Literal at `contracts.py:9-16` (`timing_cutoff, categorical_misclassification, missing_je, stale_reference, accrual_mismatch, structural_explained`) — every class the spec uses is an existing value, and `accrual_mismatch` simply goes unused (it is Kova 1's annual-prepayment class). No seventh class is requested; the document says so four separate times, including *"Do not invent a seventh enum"* (C.1) and *"No 7th class. No `unmatched_cash`"* (section E). The three-way table is stated identically in three places (Item 1 header, C.5.3 expected output, section E) and I checked them against each other — they agree on all seven rows. |
| **5. Fixture design completeness** | **Verified** **[spec]** | spec C.5.3 (three file tables + expected-output table) | Self-containment is explicit: *"No Sentinel files, no Vandelay Shopify/Amazon payouts, no DRONE P&L."* All three files are given as full literal tables, not prose. **Per-row expected classification is pinned, not exemplified** — the "Expected matcher output (PR-B acceptance — pin these)" table gives `match_kind`, pandas `fee`, `settlement_date`, `gl_account`, class, **and a card?/no-card column** for all seven outcomes. Coverage: one row per each of the five states (PZ-100, PZ-200, PZ-300, DEP-99, PZ-500) **plus** the true negative PZ-900 (`fee = 0.00`, `gl_amount == net`, UF account → `_classify` rule 4 returns `None`, *"Acceptance: zero cards for PZ-900"*) **plus** two ambiguous blank-ref rows. Unmatched counters are pinned too (`unmatched_processor_count = 0`, `unmatched_bank_count = 1`). The fixture also carries deliberate distractors — Rent and Service Revenue GL rows with no ref and non-UF accounts, which the sidecar rule excludes (*"Do not sidecar Rent"*) — and omits a `fee` column on purpose so `fee` must come from `gross - net`. |
| **6. MVP boundary discipline** | **Verified** **[spec]** | spec Item 1 "MVP boundary (locked)"; A. Pre-conditions; B; D; G | The lock sentence names all four axes explicitly: *"one processor, one Undeposited Funds (or merchant clearing) GL account, one bank, one period"*, and closes with an explicit exclusion list: *"No A2X, no auto-JE, no multi-currency, no many-to-many splits, no connectors."* I searched the Item 1 section for the creep vocabulary and found no sentence that would require multi-currency, multi-bank, recurring/automated reconciliation, or a connector — including inside the "future"/"optional" hedges. The two forward-looking mentions are both properly fenced: bank attestation is deferred to a hypothetical `0011` and marked *"Not this item"*, and the ±1-day window is marked out-of-v1 with a re-entry gate. Section D enforces the singleton rule at ingest (*"one `processor_settlement` and one `bank_statement` per `(company_id, period)`"*). Two soft notes rather than creep: E.6 (the rejection message implies an unlisted `messages.py` string) and E.4 in the *readiness* sense. |

## B. Golden-rule compliance check (spec-level)

**Compliant, and specified more tightly than any prior item.** This is a
spec-level finding — no narrative path exists to trace **[spec]**.

- **Every numeric example is declared pandas-derived.** C.5.2 opens: *"All
  dollars below are fixture literals; `fee` and `fee_pct` are pandas."* The fee
  block in C.5.1 is literal Python (`fee = round(gross - net, 2)`), preceded by
  the heading **"Pandas fee (always, never Claude)"**.
- **Claude is given copy-only verbs throughout.** The MVP boundary sentence:
  *"Pandas computes gross, fee, net, unmatched counts. Claude copies; never
  subtracts."* C.1 repeats it under `BatchMatch`. Each of the six worked
  examples ships a "Guardrail-safe sentence" containing only literals that
  appear on the match object.
- **An explicit forbidden list exists** (C.5.3): *"Forbidden in the prompt:
  'subtract,' '4.5%,' 'about 2,' any Jobber/Stripe rate."* The "about 2" entry
  is notable — it forbids Claude from *rounding a count* it was told to copy.
- **`fee_pct` is deliberately withheld from the model.** Stated twice: *"`fee_pct`
  is an internal pandas gate only — **not** a prompt placeholder (no '4.5%' in
  the sentence)"* (C.1) and *"do not serialize it onto the item that Claude
  sees"* (C.5.3). No division reaches the narrative path.
- **A disagreeing vendor `fee` column is refused as a second source of truth:**
  *"If the settlement file also has a `fee` column, ignore it for the match
  decision. Guardrail-safe number is pandas `gross - net`."*
- **The guardrail is actually wired, not assumed.** C.8 instructs
  `_run_with_guardrail` to append pandas `gross`, `fee`, `net` and unmatched
  counts to the reference values *"(and `abs` of each, same pattern as
  `delta`)"*. **[traced]** That pattern exists today at
  `backend/agents/interpreter.py:334-347`, which appends
  `gl_amount`/`non_gl_total`/`delta` plus `abs` of each — so the instruction
  matches a real, existing code shape rather than an imagined one. Section F
  pins the corresponding test (`1000.00`/`955.00`/`45.00` pass; an invented
  `45` fails; `4.5` must never appear in `numbers_used`).

No part of the spec asks Claude to compute gross, fee, net, a percentage, or a
class.

## C. Scope discipline check

All three checks pass.

- **Zero code, zero migration, zero new literal.** Re-stated from row 1, all
  **[traced]**: no `batch_matcher.py` or any matcher module; `SourceFileType`
  byte-identical to its four-literal form at `contracts.py:18-23`; highest
  migration is `0010` at `31492f9` and `0009` in the working tree; no
  `BatchMatch` symbol; no `kova_cash_*.csv`. The spec enforces this on itself
  in five places, including a hard stop in its own header (*"Do not write
  matcher code, do not add `SourceFileType` values, do not open an item-1 PR
  from this document"*) and section D (*"Do not add `SourceFileType` literals…
  in a docs-only PR"*).
- **Six-classification constraint holds across all five states.** Verified in
  row 4 against the live enum. Every class the spec emits is an existing value.
- **No contradiction with Item 5's `0010`.** The spec defends the boundary
  twice, unprompted: A. Pre-conditions — *"Do not steal `0010` (that is item 5).
  Attestation, if ever persisted, is `0011`."* — and B's migration table —
  *"If persisted later: `0011_add_bank_attestation.sql`. **Not this item. Not
  `0010`.**"* Item 1 requires no migration at all (*"**No SQL in v1**"*), and
  its stated pre-condition on Item 5 is a **roadmap** ordering, explicitly *"Not
  a Python import of `_gates_from_band`"* — so there is no code coupling to the
  Item 5 surface Tour 2 audited.

Additionally, the spec's PR split is designed around exactly the failure mode
this audit round exists to catch: PR-A ships inert types and the fixture with
`_detect_file_type` **unwired**, because *"If PR-A is merged alone with patterns
live, Vandelay… would stop being `supplier_invoices` and consolidator would tell
a fee story without a matcher."* Section G marks PR-A "Safe. Inert types." and
PR-B "Behaviour change."

## D. Readiness-for-implementation assessment

**Close, but not yet. I would not write PR-A from this document alone without
four clarifications** — three of which are one-line fixes.

PR-A's payload is small (inert `SourceFileType` literals, sidecar type names,
the three fixture CSVs, optionally an empty `batch_matcher.py`), and the fixture
tables in C.5.3 are complete enough to type in verbatim. The blockers below bite
PR-A only through the frozen `BatchMatch` shape, which C.1 itself flags as
*"Exact shape to freeze at build time"* — an acknowledged open item, not an
oversight. They bite PR-B hard.

**Must resolve before PR-A:**

1. **`BatchMatch` is missing `fee_pct`** (E.1). `_classify` reads `m.fee_pct`;
   the frozen model has no such field. PR-A ships this model, so the shape must
   be settled first — as an excluded/private field, or by changing `_classify`
   to take `fee_pct` as a parameter.
2. **`match_id` generation is unspecified** (E.4). It is a required `str` on a
   model PR-A ships, and the ambiguous group has no natural id.

**Must resolve before PR-B:**

3. **`net` is undefined for a two-way FSM+GL match** (E.2). The fee formula's
   `else` branch reads `bank.amount` when no bank row exists. The spec's own
   walk-through assumes `fee = 0` there ("dropped as $0 if booked to UF") but
   never says `net := gross` when the bank side is absent.
4. **`settlement_date` precedence is unspecified** (E.3). PZ-200's entire
   classification depends on preferring the bank's `2026-04-02` over the FSM's
   `2026-03-31`, and that rule is never written.

**Should resolve before PR-B, lower risk:**

5. **The per-batch speech contract is left as a fork** (E.6):
   `NarrativeJSON.reconciliation_classifications` is `dict[account → class]`,
   which C.1 correctly calls *"insufficient"*, then offers two options joined by
   "or" without choosing. An implementer must pick, and the two choices produce
   different JSON contracts for the frontend.
6. **The duplicate-file rejection needs a `messages.py` string** (E.7), which
   section C does not list among the files to touch.

Everything else I would consider decided: join keys, normalisation, the
tolerance locks and their admissions, pass ordering, ambiguity handling,
per-row expected output, the guardrail reference wiring, the PR split, and
rollback. That is a substantially higher bar than the earlier PR summary this
audit round was created to catch, which claimed a frontend component existed
when it did not — the Item 1 document makes the opposite error impossible for
itself by repeatedly asserting its own non-existence.

## E. Anything concerning that wasn't explicitly claimed

Spec-internal logic only. No Kova 1 or Item 5 findings re-opened; the deferred
transaction-level schema debate is not touched.

### E.1 — High: `_classify` reads a field the frozen `BatchMatch` does not have

`_classify` gates the fee band on `m.fee_pct` (C.5.1). The `BatchMatch` model in
C.1 declares `match_id, processor_ref, bank_ref, gl_ref, gl_account, gl_amount,
gross, fee, net, settlement_date, match_kind, ambiguous, candidate_count,
unmatched, classification` — **no `fee_pct`**. The document also states twice
that `fee_pct` must *not* be serialized onto the item Claude sees, so simply
adding it as a plain field would contradict B's golden-rule protection.

This is the one gap an implementer hits in the first hour. Resolution is easy —
compute `fee_pct` inside `_classify` from `fee`/`gross`, pass it as an argument,
or declare it `PrivateAttr`/`exclude=True` — but the document freezes a model
shape that its own algorithm cannot execute against.

### E.2 — High: the fee formula has no defined value when the bank side is absent

```
else:
    gross = round(float(fsm.gross), 2)      # FSM collection
    net   = round(float(bank.amount), 2)    # bank deposit
```

A Pass-2 FSM↔GL match with `nb = 0` is explicitly reachable — the spec
constructs one in its own gross-vs-net discussion (*"fsm↔gl unique on `1000.00`
(dropped as `$0` if booked to UF)"*) and Pass 2's comment confirms no-bank pairs
live in the same groups (`nb=0`). In that case `bank.amount` does not exist, so
`net`, and therefore `fee`, are undefined.

The "dropped as $0" aside implies the intended behaviour is `net := gross` →
`fee = 0` → `_classify` rule 4 drops the card. That is almost certainly right,
but it is inferred from a parenthetical, not stated. An implementer who instead
returns `None` for `net` gets a `TypeError` in rule 4's
`round(m.net, 2)`; one who returns `0.0` gets `fee = gross`, a spurious
100%-fee card. Three plausible readings, three different outcomes.

### E.3 — Medium: `settlement_date` population precedence is never stated

`_classify`'s cutoff rule — the highest-priority non-ambiguous rule — tests
`m.settlement_date > period_end`. For PZ-200 the FSM row is dated `2026-03-31`
(in period), the GL row `2026-03-31` (in period), and only the bank row is
`2026-04-02`. `timing_cutoff` therefore requires `BatchMatch.settlement_date` to
be sourced from the **bank/settlement** row specifically, never from
`collected_date` or `gl_date`. The C.5.3 expected-output table shows the right
values, but no rule anywhere says how the field is populated when the three
sides disagree — which is precisely the situation the state exists to detect.

Related and also unstated: for a match with no bank row, `settlement_date` is
presumably `None`, and the cutoff rule is guarded by `is not None`, so such a
match can never be `timing_cutoff` no matter how late its FSM date. Probably
intended (the payout is what straddles, not the collection), but worth one
sentence.

### E.4 — Medium: `match_id` is required but its construction is unspecified

`BatchMatch.match_id: str` is non-optional. For ID matches the natural value is
the normalised id; for `match_kind="amount_date"` and for the ambiguous blank-ref
group there is no id at all — that group's defining property is that both rows
have blank refs. Since C.8 proposes the interpreter may *"classify by match id"*,
this identifier is load-bearing for per-batch speech, not just a debug label.
Needs a stated construction rule (e.g. normalised id, else a deterministic
`f"{amt}_{date}_{seq}"`).

### E.5 — Medium: the "never gross-to-net" guarantee is real but the stated reason is wrong

The spec asserts: *"Pass 2 compares **net to net** (`round(..., 2)`), never FSM
`gross` to bank `net`."* Its own pseudocode says otherwise:

```
# NET never GROSS: fsm.net if present else fsm.gross; gl.amount;
#                  bank.net if present else bank.amount.
```

C.5.1's frame table marks FSM `net` as *optional* and `gross` as *required*, and
the C.5.3 fixture FSM file has **no `net` column at all** — so in the canonical
case every FSM row contributes its **gross** to a grouping key shared with bank
**net** values. Gross and net are compared.

The safety property nonetheless holds, because grouping requires **exact**
equality after `round(...,2)`: a gross and a net can only land in the same group
when `fee == 0`, which is a legitimate match, not a disguised fee. The spec's
own worked case confirms it (`1000.00` FSM vs `955.00` bank never group).

So the conclusion is sound and the `$0.00` tolerance lock is what earns it —
but the document explains the guarantee with a claim its pseudocode contradicts.
Anyone later asked to "relax the tolerance slightly" would read the prose,
believe gross and net are never compared, and silently reintroduce false fee
matches. The tolerance lock and this guarantee are the same lock; the spec
presents them as two.

### E.6 — Medium: the per-batch speech contract is a fork, not a decision

C.1 correctly identifies that `NarrativeJSON.reconciliation_classifications`
(`dict[account → class]`) cannot express per-batch classes, then leaves the fix
open: *"Future interpreter must classify by match id **or** nest class on each
match and keep the account-level class as the primary residue."* Both are
defensible; they are not equivalent. Nesting changes the JSONB payload the
frontend reads and the guardrail walks; keying by match id requires match ids to
be stable and unique (see E.4). For a document whose stated purpose is *"the
freeze so a later build has zero open product questions"*, this is the one
genuinely open product question left in it.

### E.7 — Low: the ambiguous rule sits above cutoff, and the prose summary omits it

`_classify` tests `m.ambiguous` **first**, before the cutoff rule. The
consequence: an ambiguous group whose rows settled after `period_end` is
`stale_reference`, not `timing_cutoff`. That is defensible — you cannot assert a
cut-off date for a batch you refused to identify — but the priority is stated
only as pseudocode ordering, never in prose, and every prose summary of the
order in and around this document begins at "cutoff". Worth one explicit line so
a later reader does not "restore" cutoff to the top.

### E.8 — Low: `_is_material` interaction with matcher cards is asserted, not specified

Section E states *"`is_material` still applies (Kova 1 AND-gate unchanged)"*.
It is not stated **what value** is fed to it for a matcher card. PZ-300's `delta`
could reasonably be `500.00` (the unmatched gross) or `20.00` (the fee); DEP-99
could be `750.00` or `0.00`. Under Kova 1's gate — `$500` hard-dollar OR (`$100`
AND >5%) — the two readings differ for real fixture rows: a `$20` fee with no
percentage context would not clear the gate, while `$500` would. The expected-
output table says all six exception rows produce cards, which only holds under
the larger-value reading. One sentence naming the field would close it.

### E.9 — Informational: the fixture's ambiguous rows are not in the three-way tables

The two blank-ref `$100` rows exist in File 1 and File 3 and in the expected-
output table, but the C.5.2 walk-through introduces them under *"Ambiguous
fallback (not a sixth class — extra fixture rows)"* rather than as a numbered
state, and section E's frontend table lists them last without a state name.
Presentation only — the behaviour is pinned in all three places and they agree
— but a reader skimming the five-state table will not see that a seventh
outcome is expected from the fixture.

## Verification commands run (Tour 3)

```text
ls backend/tools/                                    # no batch_matcher.py
git ls-tree -r --name-only 31492f9 | grep -i match   # no matcher module
git show 31492f9:backend/domain/contracts.py         # SourceFileType = 4 literals
sed -n '16,26p' backend/domain/contracts.py          # working tree identical
git ls-tree --name-only 31492f9 supabase/migrations/ # 0001..0010, no 0011
ls supabase/migrations/                              # working tree 0001..0009

git grep -n "bank_statement\|processor_settlement\|BatchMatch\|batch_matcher" \
    31492f9 -- backend/ frontend/ tests/ supabase/
  1 hit: tests/agents/test_consolidator.py:83 ("bank_statement.csv", False)
         — pre-existing negative assertion in _is_gl_label, not a leak

git ls-tree -r --name-only 31492f9 | grep -i kova_cash    # absent

Spec citation spot-checks (11, all resolved):
  _FILE_TYPE_PATTERNS ~511-523      -> orchestrator.py:513          OK
  _detect_file_type   ~526-532      -> orchestrator.py:528-531      OK
  SourceFileType      ~18-23        -> contracts.py:18-23           OK
  apply_plan drop     ~108-134      -> normalizer.py:108-134        OK
  _apply_reconciliation_classifications ~115 -> interpreter.py:115  OK
  _classify_from_hints ~71          -> interpreter.py:68            OK (~3)
  structural_explained guard ~140-141 -> interpreter.py:140-141     OK
  _run_with_guardrail recon_values ~340-347 -> interpreter.py:334-347 OK
  consolidator row_count ~275       -> consolidator.py:275          OK
  MappingReview payroll  ~232       -> MappingReview.tsx:233        OK
  excel_export row_count ~231,~287  -> excel_export.py:231,287      OK
  _FEE_BAND_MIN/_MAX = 3%-8%        -> hint_computer.py:67-68       OK
```

---

## Audit round closed

Tours 1–3 cover Kova 1's six items, Kova 2 Item 5, and the Item 1 spec freeze —
everything built or specified on the `31492f9` stack as of this round. **This is
not a standing audit of the project.** Item 1's actual implementation (PR-A/B/C),
Item 4, and parked items 2/3/6 if revisited each need their own audit when they
land.

The highest-priority open finding across all three tours remains Tour 1 §E.1 —
the guardrail's unparsed narrative and `$1,000` tolerance floor — which is on
`main` today and is unaffected by anything audited in Tours 2 and 3.

---

## Follow-up backlog — guardrail fix (PR #18)

Opened by PR #18 (`fix/guardrail-unit-aware-tolerance`), which migrated the
Interpreter to the corrected unit-aware guardrail. Deliberate omissions, each
needing its own change:

- **`backend/agents/opus_upgrade.py` will drift from the Interpreter's guardrail
  path until separately migrated.** It calls `verify_guardrail` at line 115
  without `strict=True`, so it keeps the legacy `max(1% of ref, $1,000)`
  single-pool tolerance — the behaviour measured at a 40.9% invented-value
  acceptance rate on SMB-scale data — while `interpreter.py` now runs at 0.015%.
  Out of scope for PR #18 by decision; not a regression (it is unchanged from
  `main`), but the two narrative paths no longer verify to the same standard.
- **`backend/agents/quarterly.py`** stays on legacy for the same reason, plus a
  prerequisite: its prompt asks Claude to derive `{N} of {M}` and `year-1`
  values (Tour 1 §B.5), so it must be brought into golden-rule compliance
  before it can be migrated.
- **`ReconciliationItem.delta_pct`** is deliberately NOT added to the guardrail
  reference pool — adding it would widen the accepted value set. Decided
  against; recorded here so it is not re-proposed as an oversight.
- **`ENFORCE_NARRATIVE_CONSISTENCY`** in `backend/tools/guardrail.py` is `False`
  for one release to measure the real violation rate. Flip only on an explicit
  decision.
