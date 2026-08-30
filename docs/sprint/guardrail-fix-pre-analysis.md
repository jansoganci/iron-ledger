# Guardrail Fix — Pre-Analysis

**Status: design only. No code written. Awaiting explicit go-ahead.**

Target: `backend/tools/guardrail.py` (CRITICAL per `CLAUDE.md`), plus the
reference-building code in `backend/agents/interpreter.py` and the prompt files.

Source findings: `docs/audit_results.md` Tour 1 §B and §E.1.

## Where this document lives, and why

Written to `docs/sprint/guardrail-fix-pre-analysis.md` rather than appended to
`docs/audit_results.md`.

Two reasons. The audit file is a closed record — it ends with an explicit "Audit
round closed" marker, and it documents *what is true of a snapshot*; amending it
with forward-looking design would blur an evidence document into a planning
document. And the repo already has this convention: `docs/sprint/` holds
`pre-analysis-coverage-ui.md`, and the git history shows `docs: pre-analysis for
consolidator materiality AND-gate` (`16c7028`) and `docs: pre-analysis for
GL-only vs source-only orphan policy` (`46e2024`). This is the established home
for a design pass that precedes a build.

## Scope note — which tree this targets

`backend/tools/guardrail.py` is **byte-identical on `main` (`a876a73`) and on the
stack (`31492f9`)** — `git diff` between them on that path is empty. The
guardrail fix is therefore directly targetable at `main` and does not need the
Kova 1/Item 5 stack to land first.

**One exception, and it matters for §C:** `implied_monthly` **does not exist on
`main`.** It arrived with `aa9004d` (annual prepayment) and lives only on the
stack. Verified: `grep -rn "implied_monthly" backend/ tests/` returns nothing in
the working tree, and 14 hits at `31492f9`. So the fix splits into two
independently shippable parts:

| Part | Targets | Depends on the stack? |
|---|---|---|
| §A tolerance, §B narrative parsing, §D reinforced prompt | `main` | No |
| §C `implied_monthly` reference | the stack (or `main` after the stack lands) | **Yes** |

Shipping §C against `main` today would add a reference field for a hint that no
code produces — harmless but dead. Recommend §A/§B/§D first on `main`, §C with
or after the annual-prepayment merge.

---

## The problem is worse than the audit stated

The audit reported that "a claimed value of `999` passed against a pandas
reference of `1`." That is true, but it understates the mechanism, because it
reads as an edge case. It is not an edge case — it is the normal operating state.

`flatten_summary` walks `pandas_summary` and returns **every numeric leaf in one
flat list, with no unit information.** `AccountSummary` (`contracts.py:48-54`)
carries `current`, `historical_avg`, **and `variance_pct`**. So every account
contributes a *percentage* — typically a single- or double-digit number — into
the same pool as dollar amounts. With a `$1,000` floor, each of those
percentages whitelists a **±$1,000 band of arbitrary dollar values**.

Measured against a realistic SMB field-service month (7 accounts, Item 5's
`100k_250k` ICP band):

```
reference values (21):
 [-2.2, 2.7, 6.67, 7.95, 14.47, 50.0, 61.07, 88.0, 95.0, 890.0, 910.0,
  1490.0, 2400.0, 3000.0, 3200.0, 10000.0, 15000.0, 38000.0, 43500.0,
  148000.0, 152000.0]

9 of those are percentages/small values (<100), each whitelisting ±$1,000.

Invented dollar values in $1–$20,000 that PASS the guardrail today:
  8,172 / 20,000 = 40.9%
```

**Four out of every ten invented dollar amounts pass verification.** Individually
confirmed: an invented `999.00`, `1,500.00`, `2,000.00`, `750.00`, `61.00` and
`45.00` all pass against that summary.

And the narrative bypass reproduces exactly as the audit described:

```
verify_guardrail({"numbers_used": [], "narrative": "We found $999,999 missing."},
                 summary)   ->  (True, 'Success')
```

The guardrail is not weak at the margin. On SMB-scale data it is close to
decorative.

---

## A. Corrected tolerance

### Recommendation

Replace the single `_tolerance_for` with a **unit-aware pair**, and drop the
dollar floor entirely:

| Unit | Tolerance | Rationale |
|---|---|---|
| Money | `max($0.01, 1e-6 × abs(ref))` | `$0.01` absorbs cent-rounding between `round(x, 2)` and the float in `pandas_summary`. The `1e-6` relative term only becomes the binding constraint above `$10,000` and exists solely to absorb float64 representation error — at `$1M` it is `$1.00`, still four orders of magnitude tighter than today. |
| Percent | `0.01` percentage points | `variance_pct` is already `round(..., 2)` at `comparison.py:82`. Copying it verbatim is exact; `0.01pp` covers the same float noise. |

The justification for near-exact matching is not aggression for its own sake —
it is that **the prompt already demands verbatim copying.**
`narrative_prompt.txt:61` says *"Use ONLY the exact numeric values provided…
Do not round or abbreviate numbers in numbers_used."* Today's tolerance permits
a drift the prompt forbids. Tightening aligns the check with the stated
contract rather than inventing a new one.

### Why not a smaller dollar floor (e.g. `$50` or `$10`)?

Because at SMB scale there is no floor value that is both safe and useful.
Real field-service accounts in the fixture above include Bank Charges at `$95`
and Software at `$890`. A `$50` floor still lets a `$95` charge be reported as
`$145`. A floor exists to absorb *rounding*, and rounding at cent precision
needs `$0.01`, not `$50`. Any larger floor is absorbing *error*, which is the
thing being tested for.

### Measured effect

```
TODAY    max(1%, $1,000)        invented-value pass rate: 40.860%
PROPOSED max($0.01, 1e-6×ref)   invented-value pass rate:  0.005%
```

An ~8,000× reduction in false-acceptance, with **zero** false rejections on
verbatim copies (all 21 reference values in the fixture still validate against
themselves — see §G).

### Unit separation is the structural half of this fix

Tightening the number alone leaves the cross-unit collision: a claimed `$50.00`
still validates against a `variance_pct` of `50.0`, because both live in one
untyped list. Confirmed under the proposed tolerance.

Proposal: make flattening **key-aware** and return two buckets.

- Keys matching `variance_pct`, `delta_pct`, `*_pct`, `*_percent`,
  `*margin*` → percent bucket.
- Everything else → money bucket.

Money tokens then match only money references; percent tokens only percent
references. This is grounded in real field names — `AccountSummary.variance_pct`
(`contracts.py:53`), `ReconciliationItem.delta_pct` (`contracts.py:193`), and
quarterly's `yoy_revenue_pct` / `yoy_gross_margin_delta` / `yoy_opex_pct`
(`quarterly.py:346-348`).

**Side benefit that closes a real bug:** `ReconciliationItem.delta_pct` is a
percentage that is currently **not** in the interpreter's reference list at all
(`interpreter.py:307` only collects `gl_amount`, `non_gl_total`, `delta`). A
narrative citing a delta percentage fails today and is masked only by the
`$1,000` floor accidentally matching something else. Unit separation forces this
to be handled explicitly.

### Zero-value handling — must be fixed in the same change

`verify_guardrail` filters references with `if p_val != 0`. Under today's floor
a claimed `0.0` matches anything within `$1,000`, so this is invisible. Under a
tight tolerance **a claimed `0.0` can never match any reference**, because zero
references are excluded and no non-zero reference is within `$0.01` of zero.

This is not hypothetical — `tests/integration/test_account_mapper_flow.py:289`
has `numbers_used=[10000.0, 10500.0, 5000.0, 500.0, 0.0]`. Confirmed:

```
claimed 0.0 passes today ($1,000 floor)?  True
claimed 0.0 passes under proposal?        False
```

`$0.00` is a legitimate thing for a report to state (a zero fee, a fully-matched
account — Item 1's PZ-500 worked example literally says *"shows a 0.00 fee"*).
Fix: stop filtering zero references and compare with the same absolute
tolerance, so `0.0` matches a real `0.0` reference and nothing else.

---

## B. Verifying narrative content, not just `numbers_used`

### The contract already exists; only the enforcement is missing

`narrative_prompt.txt:62`: *"Every number mentioned in narrative must also
appear in numbers_used. The numbers_used array is how we verify your output."*
And line 52 for reconciliations: *"Every dollar amount in the reconciliation
narrative must appear in numbers_used."*

So this is not a new requirement to negotiate with the model. It is an existing
instruction with no enforcement behind it. That materially lowers the risk of
the change: we are not asking Claude to behave differently, we are checking
whether it did what it was already told.

### Recommended approach: two-stage check

**Stage 1 — consistency.** Parse the narrative for numeric tokens. Every token
must appear in `numbers_used` (within the same tolerance). Fails closed on the
`numbers_used=[]` bypass.

**Stage 2 — value.** Every entry in `numbers_used` must match a reference value.
This is today's check, with §A's tolerance and unit separation.

Both stages are needed. Stage 2 alone is today's hole. Stage 1 alone would let
Claude declare a consistent set of invented numbers.

### Trade-offs of the two options in the brief

| Approach | Pros | Cons |
|---|---|---|
| **Parse narrative, diff against `numbers_used`** (recommended) | Closes the bypass completely. Enforces an instruction that already exists. No prompt renegotiation. Failure message can name the exact unlisted token. | Parsing is heuristic. Must not trip on dates, item counts, or period labels. A number written in an unparseable form (`"twenty-four hundred"`, `"2400"` bare) is missed — the check is a strong filter, not a proof. |
| **Declare `numbers_used` exhaustive and enforce structurally** | No parsing, no false positives. Clean contract. | **Cannot actually be enforced.** "Exhaustive" is a claim about the relationship between two fields; with no narrative inspection there is no way to test it. This is what the code does today, and the `$999,999` bypass is the result. It is a documentation change wearing an engineering change's clothes. |

The second option is not a real alternative. It is the current design.

### Parsing design, validated against the real templates

I built a narrative from the actual templates in `narrative_prompt.txt`
(timing_cutoff, accrual_mismatch, the Part 1 variance format) plus the demo
expectations in `CLAUDE.md`, and compared a naive parser to a unit-aware one:

```
NAIVE (every numeric token) — 19 tokens:
  ['2026','61.07','3','1,490.00','2,400.00','-34.00','14.47','6','38,000.00',
   '43,500.00','4','250.00','1,140.00','890.00','2026','-03','-31.',
   '12,000.00','1,000.00']

UNIT-AWARE money (9): 1,490.00  2,400.00  38,000.00  43,500.00  250.00
                      1,140.00  890.00  12,000.00  1,000.00
UNIT-AWARE pct   (3): 61.07  -34.00  14.47

Correctly ignored:  2026, -03, -31, 3, 6, 4
                    (period label, ISO date parts, "3-period", "6-period",
                     "4 items were within normal range")
```

The naive parser produces six false positives, every one of which would be a
spurious guardrail failure. The unit-aware parser produces none on this input.

**Token rules:**
- *Money* — a `$`-prefixed number, **or** a two-decimal number, **or** a
  comma-grouped number. Not followed by `%`.
- *Percent* — a number followed by optional space and `%`.
- Everything else is ignored, including bare integers.

**This requires one prompt addition, and it is the load-bearing dependency of
the whole approach:** every dollar amount in the narrative must be written with
two decimals or a `$` prefix. Without that, `"Travel rose to 2400"` parses as a
bare integer and is skipped — a residual bypass. This should be added to the
GLOBAL HARD RULES block and stated as a formatting requirement, not a style
preference.

**Known residual gaps, stated plainly:** numbers spelled as words; a bare
integer dollar amount if the model ignores the formatting rule; a number inside
an account name (`"Account 4500"`). Stage 1 is a strong filter that closes the
demonstrated `numbers_used=[]` hole, not a proof of narrative integrity. It
should be described that way in the docstring so a future reader does not
over-trust it.

---

## C. The `implied_monthly` gap

### Exact location

`backend/agents/interpreter.py`, in `_run_with_guardrail` — working-tree line
**307** (the audit cites `334-347` at `31492f9`; the block is the same, the file
offset differs):

```python
recon_values: list[float] = []
for item in reconciliations or []:
    for field in ("gl_amount", "non_gl_total", "delta"):   # <- line 307
        v = item.get(field)
        if v is not None:
            recon_values.append(float(v))
            recon_values.append(float(abs(v)))
    for src in item.get("sources", []):
        recon_values.append(float(src.get("amount", 0)))
```

### The obvious one-line fix does not work

Adding `"implied_monthly"` to that tuple would be a **silent no-op**.
`implied_monthly` is **not a field on `ReconciliationItem`** — it lives on the
nested hints object, at `contracts.py:177`, inside `ReconciliationHints`
(`contracts.py:168-183`). `ReconciliationItem.hints` is a separate sub-model
(`contracts.py:198`). So `item.get("implied_monthly")` returns `None` and the
loop skips it, exactly as today, with no error and no test failure.

The correct read is from the hints sub-dict:

```
item.get("hints", {}).get("implied_monthly")
```

This is worth calling out precisely because it would look correct in review.

### Does this widen tolerance elsewhere?

**No.** Three reasons, each checkable:

1. `recon_values` is passed as `reconciliation_values` and appended to the
   *reference* pool. It adds one more legal target value per annual-prepayment
   item; it does not change any tolerance.
2. `implied_monthly` is only non-`None` when `looks_like_annual_prepayment` is
   true (`hint_computer.py:134,153`), which the Kova 1 audit confirmed is gated
   on a same-item ±10% 12× ratio with deposit/fee exclusions. It is not a
   free-floating value.
3. It is pandas-derived — `max(|GL|, |source|) / 12` per the comment at
   `contracts.py:176` — so admitting it as a reference is admitting a pandas
   number, which is exactly what the reference pool is for.

The one thing it *does* widen is the pool by one small-magnitude value per
affected item. Under today's `$1,000` floor that would be another ±$1,000
whitelist band. **Under §A's tolerance it is a point value.** This is a concrete
argument for landing §A and §C together, or §A first — never §C alone.

### Also add `delta_pct`

While in this block: `delta_pct` (`contracts.py:193`) is a percentage on the
item that is never added to the reference pool. With §A's unit separation it
belongs in the percent bucket. Same fix site, same justification.

---

## D. The reinforced retry prompt

### Confirmed gap

`backend/prompts/narrative_prompt_reinforced.txt` contains **no reconciliation
content whatsoever.** Grepping it for `reconcil|classification|card_kind|
coverage|hints` returns nothing. Its declared output shape is:

```json
{
  "narrative": "<full report text>",
  "numbers_used": [<every number you mentioned, as float, verbatim from pandas_summary>]
}
```

No `reconciliation_classifications` key. Meanwhile `interpreter.py:325-329`
switches to this prompt on **every** attempt after the first.

### Why the retry path is not safe today

`NarrativeJSON.reconciliation_classifications` is
`dict[...] | None = None` (`contracts.py:66-68`) — **optional with a `None`
default.** So a retry response that omits it entirely is a valid `NarrativeJSON`,
passes schema validation, passes the guardrail (fewer numbers to check, and the
guardrail never inspects classifications), and persists. A multi-file run whose
first attempt trips the guardrail can therefore silently downgrade to a
variance-only report with every reconciliation finding dropped, and report
success.

That is the same class of defect as the main finding: a check that passes
because there is less to check.

### Recommendation — fix the prompt, do not rationalise the path

Add to `narrative_prompt_reinforced.txt`:

1. The PART 2 reconciliation section and the six-class taxonomy, or an explicit
   instruction to retain the reconciliation findings from the prior attempt
   unchanged except for the corrected numbers.
2. `reconciliation_classifications` in the declared JSON shape.
3. The two-decimal money formatting rule from §B.

**Plus a structural guard**, because a prompt instruction is not enforcement:
if `reconciliations` was non-empty in the context, require
`reconciliation_classifications` to be non-empty in the result. That is a check
in the interpreter, not the guardrail — the guardrail verifies numbers, and
loading it with shape assertions blurs its single responsibility.

**Do not** make the field non-optional on `NarrativeJSON`. It is legitimately
`None` for single-file runs, which are the common case.

---

## E. Existing tests that assert today's loose behavior

Baseline confirmed before proposing changes: `tests/agents/test_quarterly.py`,
`tests/tools/test_guardrail.py`, `tests/integration/test_account_mapper_flow.py`
→ **25 passed**.

### `tests/tools/test_guardrail.py` — 10 tests, 6 need changes

| Test | Line | Fate | Why |
|---|---|---|---|
| `test_tolerance_for_small_value_uses_dollar_floor` | 15 | **Rewrite** | Asserts `_tolerance_for(200.0) == 1_000.0` — the exact behavior being removed. |
| `test_tolerance_for_large_value_uses_percentage` | 20 | **Rewrite** | Asserts `1%` of `500k` = `5_000.0`. |
| `test_tolerance_for_boundary_value` | 25 | **Rewrite** | Asserts the `$1,000` boundary at `100k`. |
| `test_tolerance_for_negative_value_uses_absolute` | 30 | **Update value, keep intent** | Symmetry on negatives is still correct and worth keeping; only the expected number changes. |
| `test_small_value_within_dollar_floor_passes` | 40 | **Invert** | Claude writes `500`, pandas says `487` → asserts **pass** today. Under the proposal this **fails** — correctly. Note this test currently asserts Claude may round `487`→`500`, which `narrative_prompt.txt:61` explicitly forbids. The test encodes behavior the prompt bans. |
| `test_small_value_outside_dollar_floor_fails` | 49 | Unchanged | Still fails. Verified. |
| `test_large_value_within_one_pct_passes` | 63 | **Invert** | `4,800,000` vs `4,760,000` — a `$40,000` drift. Asserts pass today; fails under the proposal, which is the point. |
| `test_large_value_beyond_one_pct_fails` | 72 | Unchanged | Still fails. Verified. |
| `test_all_numbers_matched_returns_success_tuple` | 86 | Unchanged | Exact matches. Verified. |
| `test_empty_numbers_used_always_passes` | 95 | **Rewrite — this is the vulnerability as a test** | It asserts that `numbers_used=[]` always passes. That is the `$999,999` bypass, currently pinned as intended behavior. Should become two tests: empty `numbers_used` **with a number-free narrative** passes; empty `numbers_used` **with numbers in the narrative** fails. |
| `test_mismatch_returns_false_with_message` | 103 | Unchanged | Verified. |

Verified mechanically against the proposed tolerance:

```
test_small_value_within_dollar_floor_passes    asserts True  -> proposal False  *** BREAKS ***
test_small_value_outside_dollar_floor_fails    asserts False -> proposal False  UNCHANGED
test_large_value_within_one_pct_passes         asserts True  -> proposal False  *** BREAKS ***
test_large_value_beyond_one_pct_fails          asserts False -> proposal False  UNCHANGED
test_all_numbers_matched_returns_success_tuple asserts True  -> proposal True   UNCHANGED
test_mismatch_returns_false_with_message       asserts False -> proposal False  UNCHANGED
```

### Beyond that file

| Test | Line | Risk | Why |
|---|---|---|---|
| `tests/integration/test_account_mapper_flow.py` | 289 | **Will break** | `numbers_used=[..., 0.0]`. Confirmed: passes today, fails under a tight tolerance until §A's zero-handling fix lands. Its `narrative` is `"March 2026 close: payroll vs GL reconciliation."` — number-free, so Stage 1 is satisfied; only the `0.0` is at issue. |
| `tests/agents/test_quarterly.py` | 396 | **At risk — verify during implementation** | `numbers_used=[300000.0, 60.0]` with `narrative="Test"`. `300000.0` is the aggregated revenue and will match. `60.0` currently passes only because something in `aggregated_summary` is within `$1,000` of it. Whether it survives depends on the exact aggregate, which I did not fully trace. Flagging as at-risk rather than asserting either way. |
| `tests/agents/test_quarterly.py` | 100, 176, 263, 341, 479 | Low | Values look like round aggregates (`250000.0`, `100000.0`, `300000.0`) that should match exactly. Re-run to confirm; do not assume. |

**No test currently exercises `implied_monthly` through the guardrail** — that
is finding 3 in the audit, and the absence is the bug. A new integration test is
required, not an updated one.

---

## F. Confirming the blast radius

| Question | Answer | Evidence |
|---|---|---|
| New `ReconciliationClassification`? | **No** | The fix changes how numbers are verified. It does not classify anything. The six literals at `contracts.py:9-16` are untouched. |
| New migration? | **No** | Nothing persisted changes shape. Reports still write `narrative` + `numbers_used` into existing columns. Highest migration stays `0009` on `main` / `0010` on the stack. |
| Schema change? | **No** — with one caveat | `NarrativeJSON` (`contracts.py:63-68`) is unchanged. `reconciliation_classifications` **stays optional** (§D) — making it required would be a breaking contract change and is explicitly not proposed. |

### Files in scope

- `backend/tools/guardrail.py` — tolerance, unit buckets, narrative parsing, zero handling.
- `backend/agents/interpreter.py` — reference building (~line 307): `hints.implied_monthly`, `delta_pct`; plus the §D structural guard on retry.
- `backend/prompts/narrative_prompt.txt` — money formatting rule.
- `backend/prompts/narrative_prompt_reinforced.txt` — reconciliation section + JSON shape + formatting rule.
- `tests/tools/test_guardrail.py`, `tests/integration/test_account_mapper_flow.py`, `tests/agents/test_quarterly.py` — expected values per §E.

### Two callers outside the interpreter — do not miss these

`verify_guardrail` has **three** call sites, not one:

| Caller | Line | Passes `reconciliation_values`? | Risk |
|---|---|---|---|
| `interpreter.py` | 336 | Yes | Lowest — richest reference pool. |
| `opus_upgrade.py` | 115 | Yes — builds its own `delta`/`gl_amount`/`non_gl_total` loop at 109-113 | Medium — needs the same `implied_monthly`/`delta_pct` additions or it drifts from the interpreter. |
| `quarterly.py` | 318 | **No** — `pandas_summary` only | **Highest.** |

Quarterly is the sharpest risk in the whole change. It passes no supplemental
references, it raises `GuardrailError` on failure (`quarterly.py:333`, so
failures are hard, not logged-and-continued), and Tour 1 §B.5 found its prompt
asks Claude to produce `{N} of {M}` and `year-1` values rather than receiving
them. Tightening the tolerance under a prompt that asks for derived numbers is
how you get a wave of hard failures on a previously-working path.

**Recommendation: exclude `quarterly.py` from the first change.** Either keep it
on the current tolerance via an explicit parameter, or fix
`quarterly_report_prompt.txt` to receive `{N}`/`{M}` as pandas values first.
Pulling quarterly's prompt into compliance is its own piece of work and should
not ride along.

---

## G. False-rejection risk — measured, not asserted

### Verbatim copies: zero risk

Against the 21-value SMB fixture, every reference value validates against itself
under the proposed tolerance:

```
verbatim copies rejected under proposal: 0 / 21
```

This is true by construction — the tolerance exceeds float error — but it was
run rather than assumed.

### Rounding: this is where the real risk lives, and it is entirely percentages

Simulating a model that rounds instead of copying:

```
round to 1dp        ->  4/21 rejected   e.g. 14.47->14.5, 6.67->6.7, 61.07->61.1
round to whole      ->  6/21 rejected   e.g. 2.7->3.0, 14.47->14.0, 6.67->7.0
round to nearest 100-> 12/21 rejected
```

**Every rejection in the 1-decimal case is a `variance_pct`.** No dollar amount
is affected, because dollars in the fixture are already whole or two-decimal.

This is the concrete risk estimate: false rejections will come from Claude
writing *"Travel is up 61.1%"* when pandas says `61.07`, not from dollar drift.
Which is precisely why §A separates units — percentages can carry their own
tolerance without loosening money verification at all.

**Decision required before implementation** (flagging, not deciding
unilaterally): either

- **(i)** hold percentages to `0.01pp` and rely on the existing
  *"Do not round or abbreviate"* instruction — maximum strictness, higher
  expected retry rate on the first attempt; or
- **(ii)** allow percentages `±0.05pp`, absorbing one-decimal rounding
  (`61.07`→`61.1` is a `0.03pp` delta) while still rejecting a fabricated
  percentage.

I lean to **(ii)**. It removes the dominant false-rejection source at a cost of
`0.05pp` of precision on a number that is already a derived ratio, and it keeps
money verification at cent precision where it matters. Worth noting the retry
path is not free: a first-attempt failure sends the run to
`narrative_prompt_reinforced.txt`, which per §D is currently missing its
reconciliation section — so **§D should land before or with §A**, or tightening
the tolerance will increase traffic down the one path that is known to drop
content.

### Risk against the Kova 1 / Item 5 fixtures specifically

Checked as the brief asked. The Kova 1 and Item 5 test suites are **not exposed**
to this change:

- `tests/agents/test_comparison.py`, `tests/tools/test_account_tags.py`,
  `tests/api/test_companies_band.py` (Item 5) — none imports or calls
  `verify_guardrail`. Item 5's gates never reach Claude at all (Tour 2 §B).
- `tests/tools/test_deposit_vs_fee.py`, `test_annual_prepayment.py`,
  `test_hint_computer.py`, `tests/agents/test_consolidator.py`,
  `test_interpreter_classify.py` (Kova 1) — the Tour 3 grep for guardrail usage
  across these files found none; they test hint computation and classification
  forcing, both upstream of narrative verification.

The exposed set is exactly the three files named in §E. That is a small,
enumerable blast radius — verified by grep across `tests/`, where only
`test_guardrail.py`, `test_quarterly.py`, and `test_account_mapper_flow.py`
reference `guardrail` or `numbers_used` at all.

### Net assessment

Low false-rejection risk for dollar amounts (measured zero on verbatim copies),
concentrated and mitigable risk on percentages (measured, with a proposed
mitigation), and one high-risk caller (`quarterly.py`) recommended for explicit
exclusion from the first change. The change is **not** safe to ship as a single
undifferentiated commit across all three callers.

---

## Proposed sequencing

| Step | Contents | Target | Gate |
|---|---|---|---|
| 1 | §D reinforced prompt: reconciliation section, JSON shape, structural guard | `main` | Land first — the retry path must be safe before tightening increases traffic to it. |
| 2 | §A tolerance + unit buckets + zero handling; §B narrative parsing; money formatting rule in `narrative_prompt.txt`; `quarterly.py` explicitly excluded | `main` | The core fix. |
| 3 | §C `hints.implied_monthly` + `delta_pct` references, in `interpreter.py` and `opus_upgrade.py` | stack / post-merge | Requires the annual-prepayment feature to exist. |
| 4 | `quarterly_report_prompt.txt` compliance, then remove quarterly's exclusion | `main` | Separate work; do not bundle. |

## Open questions for the go-ahead

1. **Percentage tolerance: `0.01pp` (strict) or `0.05pp` (absorbs 1-decimal rounding)?** My recommendation is `0.05pp` — §G.
2. **Quarterly: exclude from step 2 as recommended, or fix its prompt first and do it all at once?** Recommendation is exclude; it is a bigger job than it looks.
3. **Should Stage 1 (narrative parsing) fail the run, or log-and-warn for one release** so we can measure the real violation rate on live reports before making it blocking? Failing closed is correct in principle; a measurement window would de-risk the rollout. No strong preference — this is a product call.

**No code has been written. Awaiting go-ahead.**
