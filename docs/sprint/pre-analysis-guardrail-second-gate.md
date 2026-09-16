# Pre-analysis — Guardrail second gate (two debts, one family)

Status: analysis only. No code in this change.
Date: 2026-09-16.
Parent: `docs/sprint/guardrail-fix-pre-analysis.md` open questions 2–3;
`docs/06-reports/pending-decisions-audit.md` §1.3–1.4;
`docs/sprint/test-plan-full-product.md` E2.
Checkout: `main`.

Process: (1) this pre-analysis → approval, (2) implementation as **two
slices**, (3) verification vs this file. Do not start coding until §10 is
locked.

---

## One-sentence diagnosis

The monthly close already checks Claude’s `numbers_used` against pandas with
cent precision. Two holes remain in the same family: (A) a number written in
the prose but omitted from `numbers_used` still saves, because
`ENFORCE_NARRATIVE_CONSISTENCY` is `False`; (B) quarterly and Opus still use
the old ±$1,000 mixed-unit pool, so invented dollars often pass. Flipping the
flag does not close B. Passing `strict=True` on quarterly/Opus without fixing
their prompts does not safely close A-for-them either.

---

## Scope lock

| In this family | Out |
|---|---|
| Flip or keep `ENFORCE_NARRATIVE_CONSISTENCY` as an explicit product call | Changing money/percent *tolerances* (`$0.01`, `0.05pp`) |
| Move quarterly + Opus onto `strict=True` **after** pandas owns every number those prompts currently ask Claude to derive | Weakening monthly `strict=True` to match quarterly |
| Prompt edits so Claude copies, never subtracts / `year-1` / “if derivable” | Close-flow, mapping memory, a 7th class |
| Tests: intentional mismatch still fails; the `$999,999` empty-`numbers_used` bypass fails once A is on | Live Anthropic; `supabase db push`; Cloudflare |

Two slices. Not one PR that “just turns the remaining flags on.”

---

## 1. What the guardrail actually is today

`verify_guardrail` has two modes and a named Stage 1 switch.

```
                    numbers_used  vs  pandas refs
monthly interpreter ──────────────► strict=True
                                    money pool at $0.01
                                    percent pool at 0.05pp
                                    then Stage 1: prose vs numbers_used
                                    (logged; blocked only if flag True)

quarterly / Opus ─────────────────► strict=False (default)
                                    one flat pool
                                    max(1% of ref, $1,000)
                                    zeros excluded
                                    Stage 1 never runs
```

Evidence in code:

- Flag: `backend/tools/guardrail.py` `ENFORCE_NARRATIVE_CONSISTENCY = False`.
- Stage 1 (`check_narrative_consistency`) is called **only** on the
  `strict=True` branch. The legacy branch returns before it.
- Monthly: `interpreter.py` passes `strict=True`.
- Quarterly: `quarterly.py` calls `verify_guardrail(...)` with no `strict`.
- Opus: `opus_upgrade.py` same — no `strict`.

So “the second gate is still off” is true, and it is **two gates**, not one
switch that all three callers share.

---

## 2. Debt A — `ENFORCE_NARRATIVE_CONSISTENCY` is still False

### What this gate is

Stage 1 asks: every dollar/`%` token **written in the narrative** must also
sit in `numbers_used`. That array is what Stage 2 (pandas) checks. If Claude
writes `$999,999` in prose and leaves `numbers_used` empty, Stage 2 has
nothing to reject.

The original bypass, still true on `strict=True` while the flag is False:

```
verify_guardrail(
    {"numbers_used": [], "narrative": "We found $999,999 missing."},
    {"revenue": 1_000_000.0},
    strict=True,
)  ->  (True, "Success")   # violation is only logged
```

Pinned by `test_narrative_violation_is_warn_only_by_default`.
`test_narrative_violation_fails_when_enforcement_is_enabled` already proves
the flip works.

### Why it was left off

`guardrail-fix-pre-analysis.md` open question 3: measure live violation rate
for one release, then decide. That was not forgotten; it was a product call
nobody made.

### Measurement that exists

Test-plan E2 on live Redhawk run `cc19d60d`:
`guardrail_narrative_unlisted_number` logged **0 times**. Every narrated
dollar was in `numbers_used`. No percentages in that prose.

One measured close is not a fleet, but it is the measurement window the flag
was waiting on. Audit §1.3 says the same: one tour passed, flag still off,
no owner.

### What flipping does *not* do

- Does **not** tighten money tolerance (already cent-level on monthly).
- Does **not** put quarterly or Opus on Stage 1, because they never enter
  the `strict=True` branch.
- Does **not** catch bare integers (`85` accounts, year `2026`). The parser
  deliberately skips those so dates and counts are not treated as money.
  Redhawk E1 listed counts `85, 82, 3, 16, 1` and date `2026`; Stage 1 would
  still ignore them. That is existing design, not a hole this slice opens.

### Risk if we flip

False rejects: Claude writes `$2,400.00` and forgets to list `2400.0` in
`numbers_used`. Monthly already retries once with the reinforced prompt.
Second miss → `guardrail_failed`, file stays, Retry Analysis works. That is
the correct fail-closed for a verified report.

False accepts that remain: spelled-out numbers, bare integer dollars against
the prompt’s formatting rule. Stage 1 never claimed to be a proof.

---

## 3. Debt B — quarterly and Opus still on the decorative pool

This is the hole the 2026 guardrail fix **explicitly parked**.
`guardrail-fix-pre-analysis.md` §F: exclude `quarterly.py` from the first
strict change. Recommendation was never “leave them forever.”

### Why the old pool is decorative

Legacy `flatten_summary` dumps every numeric leaf — dollars **and**
`variance_pct` — into one list. Each small percentage whitelists ±$1,000 of
arbitrary dollars. Measured in that pre-analysis: **~41% of invented dollar
amounts in $1–$20,000 pass**. `test_legacy_path_still_accepts_dollar_floor_drift`
still pins `500` accepted against pandas `487`.

Quarterly and Opus are on that path today.

### Why you cannot just pass `strict=True`

The prompts still ask Claude to **derive**. Golden rule: pandas computes,
Claude copies.

**Quarterly** (`quarterly_report_prompt.txt`):

| Prompt asks | Who should compute it | Today |
|---|---|---|
| `{N} of {M} months` | Python from `len(runs_data)` / 3 | `months_available` is persisted later; **not** in `aggregated_summary` for the guardrail. Claude subtracts. |
| `{year-1}` in “Q1 2026 vs Q1 2025” | Python `year - 1` | Prompt tells Claude to do it. |
| “Revenue increased 12% from January to February” | Python `q_mom_revenue_growth` | List **is** computed, but `flatten_summary` / `flatten_summary_by_unit` **do not walk lists**. Those MoM percents never enter the reference pool. |
| Example board figures `$12.9M` … in the prompt | Must not be copied | Example block can leak into `numbers_used`. |
| Recurring “3/3 months — Jan +12%” | Count is pandas; the `+12%` must be a provided monthly variance, not Claude’s | Prompt models a derived pattern. |

Quarterly already computes totals, margins, YoY percents, prior-year
revenue/margin/OpEx in Python and puts most of them on
`aggregated_summary`. The leftovers above are why strict would fail closed
on a previously “working” path — `quarterly.py` **raises `GuardrailError`**
on mismatch. That is a hard fail, not a soft `opus_status=failed`.

**Opus** (`opus_narrative_prompt.txt`):

| Prompt asks | Problem |
|---|---|
| “net position **if derivable**” | Tells Claude to invent net income / net margin from revenue − expense. |
| Prose class labels in the section-3 bullets | Token list is now pinned; unknown tokens still fail the Literal on `main` (the drop-unknown fix is on the other branch). |
| Recon money | `opus_upgrade.py` only adds `delta` / `gl_amount` / `non_gl_total`. Nested match `gross`/`fee`/`net`, roster counts, `implied_monthly` are **not** in its pool. Strict monthly already includes those. |

Opus fail-closed is milder: `opus_status=failed`, the Haiku/base narrative
stays. Quality loss, not a stranded run. Still a hole: a “deep dive” that
passes legacy ±$1,000 can overwrite a strict-verified monthly report.

### Same family, different blast radius

| | Debt A (flag) | Debt B (strict on Q/Opus) |
|---|---|---|
| Callers | Monthly interpreter only | `quarterly.py`, `opus_upgrade.py` |
| Failure mode | `guardrail_failed` on the monthly run | Quarterly: `GuardrailError`. Opus: `opus_status=failed` |
| Prompt work | None required for the flip | **Required first** |
| Pandas work | None | N, M, prior_year, MoM list flattening, net if we want Opus to say it |
| Touches `guardrail.py` tolerances | No — flag only | No — `strict=True` already exists |

---

## 4. What is *not* the problem

- Monthly Stage 2 is not the old ±$1,000 pool. Interpreter already uses
  `strict=True`.
- The six-class taxonomy is unrelated.
- `guardrail.py` money/percent constants are not “still wrong.” They are
  the corrected values. Do not reopen §A of the 2026 fix.
- Email, close-flow, mapping, Item 2/3/6 are out.

---

## 5. Recommended slices (after approval)

### Slice A — enforce Stage 1 on monthly

1. Set `ENFORCE_NARRATIVE_CONSISTENCY = True`.
2. Rewrite `test_narrative_violation_is_warn_only_by_default` so the
   `$999,999` / empty `numbers_used` case **fails** under `strict=True`.
   Keep an explicit test that the named flag is True, not a hidden
   conditional.
3. Do not change `money_tolerance` / `pct_tolerance`.
4. Do not pass `strict=True` to quarterly or Opus in this slice.

Exit: monthly cannot save a report whose prose contains a `$` or `%` figure
absent from `numbers_used`. Quarterly and Opus behave exactly as today.

### Slice B — make quarterly and Opus copy-only, then `strict=True`

Do **not** start B by flipping `strict`. Order:

1. **Pandas first.** Add to `aggregated_summary` (and therefore the
   guardrail pool): `months_present`, `months_in_quarter`, `prior_year`.
   Flatten `q_mom_revenue_growth` into named scalars or a dict so unit-aware
   flatten sees them as percents (`mom_revenue_growth_pct` keys, not a
   bare list).
2. **Prompts second.** Quarterly: copy those fields; delete `{N} of {M}`
   as arithmetic; delete `year-1`; delete the fake `$12.9M` example or
   replace it with placeholders that are clearly not numbers to copy.
   Opus: delete “net position if derivable.” If net is needed, pandas must
   supply `net_income` on the summary. Never ask Claude to subtract.
3. **Opus reference pool** aligned with the monthly interpreter (match
   money, roster counts, `implied_monthly`) so a correct rewrite does not
   fail strict for missing refs.
4. **Then** `verify_guardrail(..., strict=True)` on both callers.
   If Slice A has already flipped the flag, Stage 1 applies here too —
   that is correct, not a surprise.
5. Tests: intentional invented `$999` fails on both callers; a verbatim
   copy of `q_total_revenue` / `q_avg_gross_margin` still passes; a test
   that would have passed only via the $1,000 floor now fails.

Exit: no remaining `verify_guardrail` call site uses the legacy pool.
`_tolerance_for` can stay in the module for one release so a revert is a
caller change, not a deletion; deleting it is optional cleanup, not the
slice.

### Sequencing

A then B. A is a one-flag product call with the measurement already in
hand. B is prompt + pandas. Combining them hides a quarterly outage inside
a “we turned the second gate on” commit.

B without A is possible but leaves the `$999,999` empty-array bypass on
monthly, which is the more user-visible report.

---

## 6. Options considered and rejected

| Option | Why not |
|---|---|
| One PR: flag True + `strict=True` on all callers | Quarterly hard-fails on `{N} of {M}` / `year-1` / unlistened MoM percents. Original 2026 recommendation forbade this. |
| Flip the flag only, call the family done | Opus can still overwrite a strict monthly report with a ±$1,000-passing deep dive. |
| Put quarterly/Opus on strict with no prompt work | Fixes the pool, breaks the writers. Golden rule says fix pandas/prompt, not loosen the pool. |
| Widen monthly tolerance so quarterly can join without prompt work | Re-opens the decorative guardrail on the product path. |
| Delete `_tolerance_for` in Slice A | Unused only after B. Deleting it in A is drive-by. |

---

## 7. Tests each slice must add

### Slice A

1. Default `ENFORCE_NARRATIVE_CONSISTENCY is True`.
2. `numbers_used=[]` + `"We found $999,999 missing."` + `strict=True` →
   `passed is False`.
3. Same numbers listed in `numbers_used` and present in pandas → pass.
4. Existing unit-aware mismatch tests still fail closed.

### Slice B

1. Quarterly `verify_guardrail(..., strict=True)` in the agent.
2. Invented `999.0` against a ~$300k quarterly aggregate → fail (today the
   $1,000 floor can hide this depending on nearby percents).
3. `q_mom_revenue_growth` values are reachable as percent refs (not dropped
   as a list).
4. Prompt files contain `months_present` / `prior_year` (or the names we
   lock) and do **not** contain “if derivable” or “year-1” as an instruction
   to calculate.
5. Opus `strict=True`; “net position if derivable” gone.

No live LLM.

---

## 8. Files (implementation, not now)

### Slice A

| File | Change |
|---|---|
| `backend/tools/guardrail.py` | Flag `True`. Comment: measured (E2 0 violations), now enforcing. |
| `tests/tools/test_guardrail.py` | Default fail on the bypass; flag assertion. |
| `docs/sprint/test-plan-full-product.md` E2 note | Warn-only → enforcing. |
| `CLAUDE.md` | One line: Stage 1 enforced on monthly. |

### Slice B

| File | Change |
|---|---|
| `backend/agents/quarterly.py` | Extra pandas fields; flatten MoM; `strict=True` |
| `backend/prompts/quarterly_report_prompt.txt` | Copy-only |
| `backend/agents/opus_upgrade.py` | Richer recon pool; `strict=True` |
| `backend/prompts/opus_narrative_prompt.txt` | No derived net |
| `tests/agents/test_quarterly.py` | Strict mismatch |
| Opus tests (new or existing upgrade tests) | Strict mismatch |

`backend/tools/guardrail.py` tolerances — **do not change** in either slice.

---

## 9. Infra

No migration. No `supabase db push`. No Cloudflare. This family is
Python + prompts + tests only.

---

## 10. Approval checklist

Reply with yes/no per row. Implementation of a slice starts only when that
slice is locked.

- [ ] This is **two slices**, not one job.
- [ ] Slice A: flip `ENFORCE_NARRATIVE_CONSISTENCY` to True (monthly only).
- [ ] Slice B: pandas + prompts first, then `strict=True` on quarterly and Opus.
- [ ] Do A before B.
- [ ] Do not change money/percent tolerances.
- [ ] Do not ask Claude to calculate `{N} of {M}`, `year-1`, MoM %, or net.
- [ ] No live SQL / deploy in these slices.

If A is “no,” say whether we keep measuring or wait for more live E2 counts.
If B is “no,” say whether quarterly/Opus stay on legacy until a later close
slice.
