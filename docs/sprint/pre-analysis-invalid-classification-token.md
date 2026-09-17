# Pre-analysis — Invalid classification token (“uydurma sınıf”)

**SONUÇ: implementation landed on this branch, 16 September 2026.** Six-class
Literal unchanged. Unknown tokens are dropped at `NarrativeJSON`. Interpreter
retries schema errors like Discovery. Match-carrying accounts are omitted from
the class dict in both monthly prompts. `guardrail.py` untouched.

*Originally planning only. Implementation follows the locked choices in §10.*

---

## One-sentence diagnosis

The six-class schema is correct. The bug is that Claude inventing a seventh
token (`exception_three_way_matches`) fails Pydantic **before** pandas can
throw that token away, the interpreter does not retry schema errors, and the
run is mislabeled as a guardrail failure.

---

## Scope lock

| In this slice | Out of this slice |
|---|---|
| Unknown `reconciliation_classifications` values must not kill the run | A seventh `ReconciliationClassification` value |
| Interpreter retry must treat schema errors like Discovery already does | Changing what pandas residue / hints force |
| Prompt: omit match-carrying accounts from the class dict (like coverage) | Weakening `guardrail.py` |
| Tests for the live token `exception_three_way_matches` | Close-flow, mapping memory, Item 2/3/6 |
| Same schema coercion applies to Opus upgrade for free | Rewriting Opus prose, quarterly reports |
| Do not report this failure as “numbers could not be verified” | A new run status enum (unless a later slice wants it) |

**Do not add `exception_three_way_matches`.** That string is a Claude typo
fusing `card_kind: "exception"` with nested three-way `matches`. Coverage is
already `card_kind`, not a class. Per-batch classes already live on each
match, set by pandas.

---

## 1. What the six classes actually are

`ReconciliationClassification` is a closed vocabulary. It is not a file-type
list and not `card_kind`. Every exception card that needs a human story gets
exactly one of these tokens:

| Token | Meaning in the close |
|---|---|
| `timing_cutoff` | Date is after period end, or a customer deposit / 50% peşinat |
| `categorical_misclassification` | Same money, wrong GL line |
| `missing_je` | Supporting file has it, GL does not |
| `stale_reference` | Roster / price list / ambiguous match does not match the GL |
| `accrual_mismatch` | Annual lump booked in one month (pandas 12× hint only) |
| `structural_explained` | Processor/platform fee gap (pandas fee hint only) |

Coverage cards (`card_kind: "coverage"`) are **not** a seventh class. They
leave `classification` null and are omitted from Claude's dict.

Three-way cash matches (Item 1 / Riverbend) also do **not** need a seventh
class. Each nested match already carries one of the six, computed by
`batch_matcher`. The account-level class is the most action-requiring residue
among those matches (`_residue_from_matches`). Claude is not allowed to pick
it.

Declared at `backend/domain/contracts.py`:

```python
ReconciliationClassification = Literal[
    "timing_cutoff",
    "categorical_misclassification",
    "missing_je",
    "stale_reference",
    "accrual_mismatch",
    "structural_explained",
]

class NarrativeJSON(BaseModel):
    narrative: str
    numbers_used: list[float]
    reconciliation_classifications: dict[str, ReconciliationClassification] | None = None
```

`NarrativeJSON` is what `anthropic_llm.py` validates with
`schema.model_validate(parsed)`. Any other string in that dict is a
`ValidationError`.

---

## 2. What actually happened (live evidence)

Riverbend HVAC, period `2026-03-01`, three-way cash files.

- First run `7636747a` died in the interpreter.
- Second run `c0f269d6` completed; report `6df86861`; six nested matches, all
  C1–C11 outcomes correct.

Failure log (verbatim from C.0c):

```
interpreter unexpected error
1 validation error for NarrativeJSON
reconciliation_classifications.Undeposited Funds
  Input should be 'timing_cutoff', 'categorical_misclassification',
  'missing_je', 'stale_reference', 'accrual_mismatch' or
  'structural_explained'
  [input_value='exception_three_way_matches']
```

`exception_three_way_matches` does not exist anywhere in this repo. Claude
coined it. Roughly one Riverbend run in two. Redhawk never hits it because
Redhawk has no nested `matches`.

A local fix was claimed in `pending-decisions-audit.md` §1.5. It was never
committed or pushed. `main` has no patch. Treat the bug as open.

---

## 3. Why the run dies (the real problem)

Four independent facts stack. Any one of them would be annoying; together they
kill a close that pandas had already classified correctly.

### 3.1 The invented token is discarded anyway

On an item that carries `matches`, `_apply_reconciliation_classifications`
overwrites Claude's class with the pandas residue and `continue`s. Claude's
value for Undeposited Funds is never stored on the card.

```173:176:backend/agents/interpreter.py
        residue = _residue_from_matches(item.get("matches"))
        if residue is not None:
            item["classification"] = residue
            continue
```

`test_matches_force_the_account_class_over_claude` already proves a *valid*
Claude token cannot override residue. The live bug is that an *invalid* token
never reaches this function.

Same shape as gap 9 (Opus upgrade): fail closed on a field that is not the
persisted product.

### 3.2 Validation happens inside `llm.call`, before the interpreter can recover

```102:103:backend/adapters/anthropic_llm.py
        parsed = json.loads(text)
        return schema.model_validate(parsed)
```

There is no `ValidationError` handling in the adapter. The exception leaves
`llm.call` as a raw Pydantic error.

### 3.3 Semantic retry only watches the guardrail

`_run_with_guardrail` loops twice: base prompt, then reinforced prompt. The
loop only continues when `verify_guardrail` returns False. If `llm.call`
raises, the loop never starts attempt 2 and the reinforced prompt never runs.

Discovery already does the right thing: catch `(ValidationError,
json.JSONDecodeError)`, retry once, then raise a typed domain error.

Monthly interpreter does not.

### 3.4 The failure is mislabeled

`InterpreterAgent.run` maps:

| Exception | Run status | User message |
|---|---|---|
| `GuardrailError` | `guardrail_failed` | Number-mismatch copy from `_guardrail_user_message` |
| any other `Exception` | `guardrail_failed` | `messages.INTERNAL_ERROR` (“Something went wrong on our end”) |

The live run took the second path. Numbers were never checked. The user sees
an internal error. Storage stays (guardrail_failed policy), so Retry Analysis
works — but the diagnosis is a lie.

---

## 4. Why prompt-only will not fix this

`narrative_prompt.txt` already lists the six tokens and already tells Claude
not to choose a class for three-way matches:

> Each match already has its classification set by Python — you do NOT choose
> it and you must NOT contradict it.

The JSON example still asks for:

```
"<classification string from the taxonomy above>"
```

That is a soft vocabulary. Claude fused nearby words (`exception` +
`three_way` + `matches`) into a new identifier. Prompt pinning helped Opus
(gap 9: prose labels like `"missing journal entry"`), and
`test_opus_prompt_pins_the_six_classification_tokens` exists — but Opus still
validates the same strict Literal. A second invented token still kills the
upgrade.

Prompt edits are a useful belt. They are not the suspenders.

---

## 5. What is *not* the problem

- **Not a missing 7th class.** Item 1 / Kova 2 / orphan policy all lock “six
  classes only, no seventh enum.” Coverage is `card_kind`. Match classes are
  on `matches[].classification`.
- **Not a pandas / matcher bug.** Run `c0f269d6` produced the six expected
  cards. The matcher is sound.
- **Not a guardrail miss.** `verify_guardrail` never ran on `7636747a`.
- **Not Redhawk.** Only cards with nested `matches` look exposed.
- **Not Claude doing arithmetic.** The invented token is a label, not a
  number. Golden-rule math is intact. Do not touch `guardrail.py`.

---

## 6. Recommended fix (after approval)

Primary, then backup, then copy. All three are small. None add a class.

### A. Coerce unknown class values at `NarrativeJSON` (primary)

Before the Literal is enforced, drop any dict entry whose value is not one of
the six tokens. Keep the key out of the map so `_classify_from_hints` /
residue can fill it.

Consequences:

- `exception_three_way_matches` on Undeposited Funds → key dropped → residue
  stamps `missing_je` (or whichever match is most action-requiring). Run
  continues.
- A wrong-but-valid token (`timing_cutoff` when residue is `missing_je`) is
  unchanged: pandas still overwrites on match / coverage / fee / deposit /
  annual / roster-gap cards. That path is already tested.
- Account-total cards with no force hint: unknown token → hint fallback.
  That is the same path as “Claude omitted the key.”
- Opus upgrade uses the same schema. Coercion unblocks upgrades that only
  persist `result.narrative` anyway (`opus_upgrade.py` never writes
  `reconciliation_classifications` onto the report).

Do this with a Pydantic v2 `field_validator(..., mode="before")` on
`reconciliation_classifications`. Do not widen the Literal. Do not log the
invented token's surrounding narrative. Logging the **token string and the
account name** at WARNING is enough (`event="invalid_classification_token"`).
Cell values stay out of logs.

### B. Catch schema errors inside `_run_with_guardrail` (backup)

Mirror Discovery:

```python
except (ValidationError, json.JSONDecodeError) as exc:
    last_message = f"schema violation: {exc}"
    continue  # attempt 2 with reinforced prompt
```

This covers remaining schema failures (wrong types, broken JSON, extra nested
objects) that coercion of one field will not save. After both attempts, raise
a typed error — not a raw Pydantic dump into `INTERNAL_ERROR`.

Do **not** treat a remaining schema failure as a number mismatch. Prefer
`GuardrailError` only when `verify_guardrail` failed. For exhausted schema
retries, still land in `guardrail_failed` (Retry Analysis + keep the file)
but use a dedicated `messages.py` string: the report could not be written
from the model output, data is safe, try again. Do not say the numbers failed
verification if they were never checked.

### C. Prompt (belt)

In `narrative_prompt.txt` and `narrative_prompt_reinforced.txt`:

- Omit accounts that have a non-empty `matches` list from
  `reconciliation_classifications`, same rule as coverage.
- Replace `"<classification string from the taxonomy above>"` with an
  explicit “copy one of these six tokens verbatim” list, matching the Opus
  prompt.
- State that any other string is dropped.

Prompt-only is not sufficient. Do A and B even if C is approved.

### Files that would change (implementation, not now)

| File | Change |
|---|---|
| `backend/domain/contracts.py` | Before-validator: drop unknown class values |
| `backend/agents/interpreter.py` | Catch ValidationError/JSONDecodeError in the retry loop; distinct user copy for exhausted schema retries |
| `backend/messages.py` | One new user-facing string for schema exhaustion |
| `backend/prompts/narrative_prompt.txt` | Omit match-carrying accounts; pin the six tokens |
| `backend/prompts/narrative_prompt_reinforced.txt` | Same |
| `tests/domain/` or `tests/agents/` | New tests listed in §7 |
| `docs/sprint/test-plan-full-product.md` gap 7b | Mark resolved after verification |

`backend/tools/guardrail.py` — **do not change.**

`opus_upgrade.py` — no code change required if A lands on the shared schema.
Optional follow-up: catch ValidationError there too so a non-class schema
miss does not mark `opus_status=failed`. Out of the minimum slice.

---

## 7. Tests this slice must add

Narrowest first, then the interpreter loop.

1. **Intentional mismatch (required).** `NarrativeJSON.model_validate` with
   `reconciliation_classifications={"Undeposited Funds": "exception_three_way_matches"}`
   succeeds. The key is absent after validation. Narrative and `numbers_used`
   are kept.
2. **Valid tokens still round-trip.** Each of the six literals survives
   validation unchanged.
3. **Mixed dict.** One valid key + one invented key → only the valid key
   remains.
4. **Residue still wins.** After coercion, `_apply_reconciliation_classifications`
   on a match-carrying Undeposited Funds item still stamps pandas residue.
   Reuse the helpers in `tests/agents/test_interpreter_matches.py`.
5. **Hint fallback.** Unknown token on an account-total stale-reference item
   (no matches, no force hints) → `_classify_from_hints` fills
   `stale_reference`.
6. **Interpreter retry.** Stub `llm.call` to raise `ValidationError` on
   attempt 1 and return a valid `NarrativeJSON` on attempt 2. Run completes.
   Attempt 2 uses the reinforced prompt.
7. **Guardrail still fails closed.** A valid schema with a number that is not
   in the pandas pool still raises `GuardrailError` after two attempts. Do
   not let this slice become a way around the guardrail.
8. **Opus prompt pin stays.** Existing
   `test_opus_prompt_pins_the_six_classification_tokens` must still pass.

Do not call Anthropic. Do not hit Supabase. Do not re-run Riverbend live as a
gate for merge.

---

## 8. Options considered and rejected

| Option | Why not |
|---|---|
| Add `exception_three_way_matches` to the Literal | Invents a 7th class. Product lock forbids it. The token is a typo, not a speech act. |
| Prompt-only | Already lists the six. Still failed live ~1/2. | 
| Catch in `anthropic_llm.py` and return a partial object | Adapter would guess how to repair domain contracts. Repair belongs on `NarrativeJSON` or in the use case. |
| Let the adapter swallow ValidationError and return None | Interpreter already treats unexpected errors as internal failure. Silent None is worse. |
| Widen the dict to `dict[str, str]` | Removes the closed vocabulary. Claude could persist garbage on account-total cards that have no pandas force. Coerce-unknown keeps the Literal for values that survive. |
| New run status `schema_failed` | Useful later, not required to stop Riverbend dying. `guardrail_failed` already keeps the file and enables Retry Analysis. Fix the copy, not the enum, in this slice. |

---

## 9. Risk if we ship A without B

Coercion fixes the live token. A different schema break (Claude wrapping the
JSON, typing `numbers_used` as strings, sending a list instead of a dict)
still takes the unexpected-error path. B is small and copies a pattern that
already exists in Discovery. Recommend A+B+C as one piece.

Risk if we ship B without A: retry often works (~1/2), but both attempts can
invent a token and the run still dies. The live failure is specifically an
unknown class value. A is the actual fix; B is the safety net.

---

## 10. Approval checklist

Reply with yes/no. Implementation starts only after this list is locked.

- [ ] Do **not** add a 7th class.
- [ ] Primary fix is drop-unknown at `NarrativeJSON` (A).
- [ ] Backup is ValidationError retry in `_run_with_guardrail` (B).
- [ ] Prompt omits match-carrying accounts and pins the six tokens (C).
- [ ] Do not touch `guardrail.py`.
- [ ] Exhausted schema retries may stay in `guardrail_failed` (so Retry
      Analysis works) but must not use the number-mismatch or
      “something went wrong on our end” copy.
- [ ] Tests in §7, no live LLM.

If any box is “no,” say which option from §8 (or a new one) to use instead.
