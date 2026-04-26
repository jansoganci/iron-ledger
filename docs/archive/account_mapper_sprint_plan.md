# AccountMapper — Sprint Plan

> ## ▶️ STATUS: RESUMED
>
> **Resumed:** 2026-04-25 — post-hackathon demo.
>
> **Why resumed:** Three-sector demo shipped successfully (Sentinel, Vandelay, Helix). All reconciliation classifications working. The remaining gap: "No formatting required" — every file still needs a clean `Account` column pre-populated. AccountMapper closes this gap and makes the headline pitch literally true.
>
> **What changed since pause:** Deep code audit surfaced 6 new implementation blockers not in the original plan (see Pre-execution Code Audit below). All 6 are resolved with concrete decisions before execution begins. Plan is updated accordingly.
>
> ---

---

## Decisions Log

All decisions from the first audit cycle remain in force unless explicitly overridden below.

### 🔴 Original demo-breakers — all resolved

1. **Orchestrator is free functions, not a class** → Phase 5 written as new sibling functions `run_multi_file_parser_with_mapping()` and `apply_mapping_decisions()`. No class.
2. **`file_types[]` plumbing** → **OVERRIDDEN.** See B5 below. Filename heuristic used instead of user dropdown. Upload route unchanged.
3. **Phase 0.2 data verification** → Done. All 4 classifications verified across 3 sectors in demo.
4. **Description-append cut** → Confirmed cut. Already removed.
5. **Cache pre-warm mandatory** → Confirmed. Pre-run script required before any live demo.

### 🟡 Original should-fix — resolved

6. **JSONB not parquet scratch** → **OVERRIDDEN.** See B3 below. Double-parse approach used. No JSONB serialization of DataFrames needed.
7. **Cache writes user's final decision** → Confirmed. Whatever user submits is cached, not just unchanged rows.

---

## Pre-execution Code Audit — 6 New Blockers Found

Deep reading of `parser.py`, `orchestrator.py`, `routes.py`, and `mapping_prompt.txt` revealed 6 issues not in the original plan. All resolved before implementation begins.

---

### B1 — `parse_file_silently` already calls Haiku for category mapping

**What we found:**

`parser.py:532` — every file silently calls `_map_accounts()` which sends `mapping_prompt.txt` to Haiku. This prompt maps account names to **GAAP categories** (REVENUE, COGS, OPEX...).

```python
# parser.py — inside parse_file_silently
mapped_columns, _ = self._map_accounts(run_id, company_id, df_validated)
```

AccountMapper does a **different job**: it maps vendor/employee/customer names to **specific GL account names** ("AlarmTech Industries" → "Equipment COGS"). Two different prompts, two different outputs.

**Decision:** AccountMapper runs as a separate call, before `_map_accounts`. A new `account_mapping_prompt.txt` is created — completely separate from `mapping_prompt.txt`. Do not touch the existing prompt.

---

### B2 — Timing: AccountMapper must run before `groupby()`

**What we found:**

`parse_file_silently` flow:
```
normalizer.apply_plan()
↓
validator.validate()
↓
_map_accounts()  ← Haiku, categories
↓
df_validated.groupby("account")["amount"].sum()  ← aggregation
↓
preview_rows returned
```

AccountMapper must rewrite `df_validated["account"]` **after validation, before `_map_accounts`** — otherwise "AlarmTech Industries" gets aggregated under its raw name, then passed to consolidator, where nothing matches.

**Decision:** Add optional parameter `account_name_map: dict[str, str] | None = None` to `parse_file_silently`. If provided, insert this step between validator and `_map_accounts`:

```python
if account_name_map:
    df_validated["account"] = df_validated["account"].map(
        lambda x: account_name_map.get(str(x).strip(), x)
    )
```

This is a 3-line change inside `parse_file_silently`. Non-breaking (parameter is optional, default None).

---

### B3 — Phase A → Phase B DataFrame serialization

**What we found:**

Phase A (background task, runs after upload) has parsed DataFrames in memory. Phase B is triggered by a different HTTP request (`POST /runs/{id}/confirm-mappings`). Between them, DataFrames must be passed somehow.

Original plan proposed: parquet scratch → rejected (multi-worker risk). JSONB serialization → complex for large files.

**Decision: Double-parse approach.**

- **Phase A:** Run AccountMapper, build `MappingDraft` (unique source values + Haiku suggestions). Store draft in `parse_preview["mapping_draft"]`. **Do not consolidate yet.** Also store which `storage_keys` correspond to which file (label → storage_key map) in `parse_preview["file_keys"]`. Transition to `AWAITING_MAPPING_CONFIRMATION`.

- **Phase B (after user confirms):** Re-download files from Supabase Storage using the stored `file_keys`. Re-run `parse_file_silently` with `account_name_map` = user's approved decisions. Then consolidate and continue existing pipeline.

**Trade-off:** Each non-GL file is downloaded and parsed twice (Phase A for mapping, Phase B for final parse). For 4 small demo files, this adds ~15-30 seconds. Acceptable. Files remain in Storage until COMPLETE per existing architecture.

---

### B4 — `mapping_prompt.txt` does the wrong job

**What we found:**

`mapping_prompt.txt` maps account names to GAAP categories:
```json
"Software Revenue" → "REVENUE"
"Travel & Entertainment" → "G&A"
```

AccountMapper needs to map vendor/employee/customer names to **specific GL account names**:
```json
"AlarmTech Industries" → "Equipment COGS"
"T. Rivera" → "Salaries & Wages"
```

Completely different purpose, different output format, different validation logic.

**Decision:** Create `account_mapping_prompt.txt` from scratch (see Phase 3). Do not modify `mapping_prompt.txt`.

---

### B5 — `file_types[]` not in upload route, orchestrator doesn't know file types

**What we found:**

`routes.py` upload endpoint takes only `files` and `period`. No `file_types[]`. Orchestrator receives only `storage_keys: list[str]`. `_is_gl_label()` already exists for GL detection, but "payroll" vs "supplier_invoices" distinction has no infrastructure.

**Decision: Filename heuristic. No user dropdown. No upload route changes.**

New function `_detect_file_type(filename: str) -> str`:
```python
_FILE_TYPE_PATTERNS = {
    "general_ledger": ["gl", "general_ledger", "quickbooks", "qb", "gl_export"],
    "payroll":        ["payroll", "salary", "salaries", "wages", "gusto", "adp", "rippling"],
    "contracts":      ["contract", "subscription", "recurring", "roster"],
    "supplier_invoices": ["invoice", "supplier", "vendor", "purchase", "bill", "ap"],
}

def _detect_file_type(filename: str) -> str:
    stem = filename.lower().replace("-", "_").replace(" ", "_").split(".")[0]
    for file_type, patterns in _FILE_TYPE_PATTERNS.items():
        if any(p in stem for p in patterns):
            return file_type
    return "supplier_invoices"  # safe default
```

This covers all realistic demo filenames (sentinel_gl, helix_payroll, vandelay_shopify, etc.). Saves 30 minutes of dropdown UI and upload route wiring.

---

### B6 — `AWAITING_MAPPING_CONFIRMATION` state machine missing

**What we found:**

`RunStatus` enum in `run_state_machine.py` does not have `AWAITING_MAPPING_CONFIRMATION`. The existing `_ALLOWED` transitions don't include it.

**Decision:** Add as planned. Transitions:
- `PARSING → AWAITING_MAPPING_CONFIRMATION` (new)
- `AWAITING_MAPPING_CONFIRMATION → AWAITING_CONFIRMATION`
- `AWAITING_MAPPING_CONFIRMATION → PARSING_FAILED`

No other state machine changes needed.

---

## Updated Locked Decisions

These supersede the original "Decisions baked in" list:

| Decision | Value |
|---|---|
| File type detection | **Filename heuristic** (not user dropdown) |
| DataFrame serialization | **Double-parse** (not parquet, not JSONB frames) |
| Description append | **Cut** (confirmed) |
| rapidfuzz pre-filter | **Cut** (post-MVP) |
| Cache table | **Cut** (post-MVP — every run calls Haiku) |
| Hallucinated GL accounts | Demote to `confident: false` |
| User confirmation | Always shown; `confident: true` rows pre-checked |
| GL files first | Sort by `_is_gl_label()` before parse loop |
| Fallback GL list | `DEFAULT_GL_CATEGORIES` (6 GAAP categories) when no GL |
| `mapping_draft` location | `runs.parse_preview["mapping_draft"]` JSONB |
| `file_keys` location | `runs.parse_preview["file_keys"]` JSONB |
| Estimate | **7–8 hours** (stripped: no cache table, no dropdown, no double-parse parquet) |

---

## PHASE 0 — Pre-flight (20 min)

### 0.1 Branch setup
```bash
git checkout -b feat/account-mapper
pytest -q  # must be green before any change
```

### 0.2 Verify demo data still works
- Run one quick Sentinel smoke test (upload → confirm → report)
- Confirm all 4 classifications still fire
- If broken: fix before adding AccountMapper

### 0.3 Acceptance
- Branch exists, tests green, existing demo clean

---

## PHASE 1 — Database: NO MIGRATION NEEDED

The original plan included an `account_mappings` table for the cache. **Cache is cut for this sprint.** No migration required.

If cache is added post-MVP, migration file is `supabase/migrations/0008_account_mappings.sql` (spec in the archive section at the bottom of this document).

---

## PHASE 2 — Domain layer (30 min)

### 2.1 Modify `backend/domain/run_state_machine.py`

Add new state:
```python
class RunStatus(str, Enum):
    # ... existing states ...
    AWAITING_MAPPING_CONFIRMATION = "awaiting_mapping_confirmation"  # NEW
```

Add transitions to `_ALLOWED`:
```python
RunStatus.PARSING: frozenset({
    RunStatus.DISCOVERING,
    RunStatus.AWAITING_MAPPING_CONFIRMATION,   # NEW
    RunStatus.AWAITING_CONFIRMATION,
    RunStatus.PARSING_FAILED,
}),
RunStatus.AWAITING_MAPPING_CONFIRMATION: frozenset({   # NEW
    RunStatus.AWAITING_CONFIRMATION,
    RunStatus.PARSING_FAILED,
}),
```

### 2.2 Modify `backend/domain/contracts.py`

Add types and models (no database backing — cache is post-MVP):

```python
# File type taxonomy — detected from filename, not user input
SourceFileType = Literal[
    "general_ledger",
    "payroll",
    "supplier_invoices",
    "contracts",
]

DEFAULT_GL_CATEGORIES = [
    "REVENUE", "COGS", "OPEX", "G&A", "R&D", "OTHER_INCOME",
]

class AccountMappingDecision(BaseModel):
    gl_account: str | None
    confident: bool

class AccountMappingResponse(BaseModel):
    """Haiku output: {raw_value: {gl_account, confident}}."""
    mappings: dict[str, AccountMappingDecision]

class MappingDraftItem(BaseModel):
    source_pattern: str          # raw value from file ("AlarmTech Industries")
    source_file: str             # which file it came from
    file_type: SourceFileType    # detected from filename
    suggested_gl_account: str | None
    confident: bool

class MappingDraft(BaseModel):
    items: list[MappingDraftItem]
    gl_account_pool: list[str]   # valid GL account names for dropdown
```

### 2.3 Modify `backend/domain/ports.py`

No new repo protocol (cache cut). No changes needed.

### 2.4 Acceptance
```bash
pytest tests/domain/ -q  # all green
python -c "from backend.domain.contracts import SourceFileType, MappingDraft; print('OK')"
```
Add 2 state machine tests:
- `PARSING → AWAITING_MAPPING_CONFIRMATION` → valid
- `AWAITING_MAPPING_CONFIRMATION → COMPARING` → raises `InvalidRunTransition`

---

## PHASE 3 — New prompt (20 min)

### 3.1 New file: `backend/prompts/account_mapping_prompt.txt`

**Purpose:** Map raw source values (vendor names, employee names, customer names) to **specific GL account names** from the company's chart of accounts. This is DIFFERENT from `mapping_prompt.txt` which maps to GAAP categories.

```
You are a US GAAP account-mapping assistant for financial reconciliation.

You will receive:
- "values": list of raw text values from a source file's identifier column (vendor names, employee names, customer names, or similar)
- "file_type": the type of source file — one of "payroll", "supplier_invoices", "contracts"
- "gl_accounts": the company's chart of accounts — these are the EXACT names you must use in your output

Your job: for each value in "values", identify the single best matching GL account name from "gl_accounts".

Rules:
- Output ONLY names from "gl_accounts". Do not invent or paraphrase account names.
- Match based on business context and file_type:
  * payroll → individual employee names map to salary/wage/bonus GL accounts
  * supplier_invoices → vendor company names map to the expense category they sell (equipment, software, services, etc.)
  * contracts → customer names map to the corresponding revenue GL account
- If no plausible match exists in gl_accounts, set gl_account to null and confident to false.
- confident: true = clear, unambiguous match. confident: false = uncertain or no match.
- Structural values ("TOTAL", "Subtotal", blank strings) → null + confident: false.
- Do not perform arithmetic. Do not modify the value strings.

Return ONLY valid JSON:
{
  "mappings": {
    "<value exactly as provided>": {"gl_account": "<name from gl_accounts or null>", "confident": <true|false>}
  }
}

One entry per input value. No prose outside the JSON.
```

### 3.2 Acceptance
- File exists, non-zero size
- Manually test: send sample context to Haiku, verify output format

---

## PHASE 4 — AccountMapper agent (2 hours)

### 4.1 New file: `backend/agents/account_mapper.py`

```python
"""AccountMapper — translate raw source values to canonical GL account names.

Called from the orchestrator BEFORE parse_file_silently's final aggregation.
Operates on unique account values only; applies result via pandas .map().

Pipeline (per non-GL file):
  1. Extract df['account'].unique() from the partially-normalized DataFrame.
  2. Single Haiku call with GL account pool + unique values + file_type context.
  3. Validate: any gl_account NOT in pool → demote to confident=false.
  4. Build MappingDraft items for user review.
  5. Return mapping dict {raw_value: gl_account_or_None} for parse_file_silently to apply.
"""

MAPPING_MODEL = "claude-haiku-4-5-20251001"

class AccountMapper:
    def __init__(self, llm_client: LLMClient) -> None:
        self._llm = llm_client

    def build_draft(
        self,
        unique_values: list[str],
        file_type: SourceFileType,
        source_file: str,
        gl_pool: list[str],
    ) -> tuple[dict[str, str | None], MappingDraft]:
        """Call Haiku, validate output, return (mapping_dict, draft).

        mapping_dict: {raw_value: gl_account_name_or_None}
        draft: for user review UI
        """
        if not unique_values:
            return {}, MappingDraft(items=[], gl_account_pool=gl_pool)

        ctx = {
            "values": unique_values,
            "file_type": file_type,
            "gl_accounts": gl_pool,
        }
        resp: AccountMappingResponse = self._llm.call(
            "account_mapping_prompt.txt",
            MAPPING_MODEL,
            ctx,
            AccountMappingResponse,
        )

        mapping_dict: dict[str, str | None] = {}
        draft_items: list[MappingDraftItem] = []

        for value in unique_values:
            decision = resp.mappings.get(value)
            if decision is None:
                # Haiku missed this value
                gl = None
                confident = False
            else:
                gl = decision.gl_account
                confident = decision.confident
                # Hallucination guard: reject if not in pool
                if gl is not None and gl not in gl_pool:
                    gl = None
                    confident = False

            mapping_dict[value] = gl
            draft_items.append(
                MappingDraftItem(
                    source_pattern=value,
                    source_file=source_file,
                    file_type=file_type,
                    suggested_gl_account=gl,
                    confident=confident,
                )
            )

        draft = MappingDraft(items=draft_items, gl_account_pool=gl_pool)
        return mapping_dict, draft
```

**Important:** AccountMapper does NOT read from or write to `account_mappings` table (cache is post-MVP). It only calls Haiku and returns results.

### 4.2 Modify `backend/agents/parser.py` — `parse_file_silently` signature

Add optional parameter `account_name_map`:

```python
def parse_file_silently(
    self,
    storage_key: str,
    company_id: str,
    period: date,
    run_id: str,
    account_name_map: dict[str, str] | None = None,  # NEW
) -> tuple[list[dict], str, pd.DataFrame]:
```

Inside, after `df_validated = validator.validate(df_normalized)` and BEFORE `_map_accounts`:

```python
# Apply AccountMapper decisions if provided (B2 fix — must run before groupby)
if account_name_map:
    df_validated["account"] = df_validated["account"].map(
        lambda x: account_name_map.get(str(x).strip(), x)
    )
```

**That's the entire parser change: 3 lines.**

### 4.3 Acceptance

Unit tests in `tests/agents/test_account_mapper.py`:
- Single Haiku call with all uniques (assert LLM called once)
- Hallucinated gl_account not in pool → demoted to confident=False
- Empty unique list → empty draft, no Haiku call
- GL pool empty → falls back to `DEFAULT_GL_CATEGORIES`
- Haiku returns null gl_account → confident=False in draft

Minimum 5 unit tests.

---

## PHASE 5 — Orchestrator integration (2.5 hours)

This is the most complex phase. Two new functions are added to `orchestrator.py`. The existing `run_multi_file_parser_until_preview` is **not modified**.

### 5.1 New helper: `_detect_file_type(filename: str) -> str`

Add to `orchestrator.py` module level:

```python
_FILE_TYPE_PATTERNS: dict[str, list[str]] = {
    "general_ledger":    ["gl", "general_ledger", "quickbooks", "qb", "gl_export", "ledger"],
    "payroll":           ["payroll", "salary", "salaries", "wages", "gusto", "adp", "rippling"],
    "contracts":         ["contract", "subscription", "recurring", "roster", "customer"],
    "supplier_invoices": ["invoice", "supplier", "vendor", "purchase", "bill", "ap"],
}

def _detect_file_type(filename: str) -> str:
    stem = filename.lower().replace("-", "_").replace(" ", "_").split(".")[0]
    for file_type, patterns in _FILE_TYPE_PATTERNS.items():
        if any(p in stem for p in patterns):
            return file_type
    return "supplier_invoices"
```

### 5.2 New function: `run_multi_file_parser_with_mapping()`

**Phase A function.** Called from upload route for multi-file runs (replaces `run_multi_file_parser_until_preview` as the background task — that function stays unchanged for backward compatibility).

```python
def run_multi_file_parser_with_mapping(
    run_id: str,
    storage_keys: list[str],
    company_id: str,
    period: date,
) -> None:
    """Phase A: parse all files, run AccountMapper for non-GL files,
    store mapping draft, pause at AWAITING_MAPPING_CONFIRMATION.

    Phase B is triggered by POST /runs/{id}/confirm-mappings.
    """
```

**Phase A flow:**

1. Transition `PENDING → PARSING`
2. Sort storage_keys: GL files first (by `_is_gl_label(label)`)
3. For each storage_key:
   - `label = key.split("/")[-1]`
   - `file_type = _detect_file_type(label)`
   - `preview_rows, source_column, raw_df = parser.parse_file_silently(key, company_id, period, run_id)` — **standard call, no account_name_map yet**
   - If GL file: accounts_repo now populated → continue
   - If non-GL file: collect `preview_rows` for later AccountMapper input
4. After all files parsed, get GL account pool: `gl_pool = list(accounts_repo.list_for_company(company_id).keys()) or list(DEFAULT_GL_CATEGORIES)`
5. For each non-GL file's preview_rows: extract `unique_values = [row["account"] for row in preview_rows]` (already unique, one per account from groupby)
6. Call `mapper.build_draft(unique_values, file_type, label, gl_pool)` → get `(mapping_dict, draft_items)`
7. Collect all draft_items into aggregate `MappingDraft`
8. Store to `parse_preview`:
   ```python
   parse_preview = {
       "mapping_draft": draft.model_dump(mode="json"),
       "file_keys": {label: key for label, key in zip(labels, storage_keys)},
       "is_multi_file": True,
   }
   runs_repo.set_parse_preview(run_id, parse_preview)
   ```
9. If all files are GL (no draft items): skip mapping step, run consolidation directly, go to `AWAITING_CONFIRMATION`
10. Else: Transition `PARSING → AWAITING_MAPPING_CONFIRMATION`

### 5.3 New function: `apply_mapping_and_consolidate()`

**Phase B function.** Called from `POST /runs/{id}/confirm-mappings` as a BackgroundTask.

```python
def apply_mapping_and_consolidate(
    run_id: str,
    company_id: str,
    period: date,
    user_decisions: dict[str, str],
) -> None:
    """Phase B: apply user-approved mappings, re-parse files,
    consolidate, reconcile, transition to AWAITING_CONFIRMATION.

    user_decisions: {source_pattern: gl_account_name}
    """
```

**Phase B flow:**

1. Validate state: must be `AWAITING_MAPPING_CONFIRMATION`
2. Load `parse_preview` → get `file_keys` dict (label → storage_key)
3. Determine which files are GL (by `_is_gl_label(label)`)
4. For each file:
   - If GL: call `parse_file_silently(key, company_id, period, run_id)` — no mapping
   - If non-GL: call `parse_file_silently(key, company_id, period, run_id, account_name_map=user_decisions)` — with approved mappings
5. Collect `(label, preview_rows, source_column, raw_df)` for all files
6. Run existing consolidation pipeline (same as `run_multi_file_parser_until_preview` lines 159–220)
7. Build `parse_preview` with reconciliations (same shape as existing multi-file preview)
8. Clear `mapping_draft` from `parse_preview` (replace with final preview)
9. Transition `AWAITING_MAPPING_CONFIRMATION → AWAITING_CONFIRMATION`

### 5.4 Failure modes

- Parse fails on any file in Phase B → `PARSING_FAILED`
- Haiku errors in Phase A → `TransientIOError` → `PARSING_FAILED` with `messages.MAPPING_FAILED`
- user_decisions contains gl_account not in pool → reject 400 at API layer (Phase 6)

### 5.5 Acceptance

Tests in `tests/agents/test_orchestrator_mapping.py`:
- Pure GL upload → no `AWAITING_MAPPING_CONFIRMATION`, goes to `AWAITING_CONFIRMATION`
- GL + payroll → passes through `AWAITING_MAPPING_CONFIRMATION`
- Phase B applies user decisions to df["account"] before consolidation
- GL files always bypass the mapper (no account_name_map passed)

---

## PHASE 6 — API routes (45 min)

### 6.1 Modify `backend/api/routes.py` — upload route

Change the multi-file background task from `run_multi_file_parser_until_preview` to `run_multi_file_parser_with_mapping`:

```python
else:
    background_tasks.add_task(
        run_multi_file_parser_with_mapping,  # was: run_multi_file_parser_until_preview
        run_id=run_id,
        storage_keys=storage_keys,
        company_id=company_id,
        period=period_date,
    )
```

**No other changes to the upload endpoint.**

### 6.2 New endpoint: `POST /runs/{run_id}/confirm-mappings`

```python
@router.post("/runs/{run_id}/confirm-mappings")
@limiter.limit("20/minute")
async def confirm_mappings(
    run_id: str,
    request: Request,
    body: ConfirmMappingsRequest,
    background_tasks: BackgroundTasks,
    user_id: str = Depends(get_current_user),
    company_id: str = Depends(get_company_id),
):
    ...
```

**`ConfirmMappingsRequest`** (add to routes.py or a schemas module):
```python
class ConfirmMappingsRequest(BaseModel):
    decisions: dict[str, str]
    # {source_pattern: gl_account_name}
    # Flat — no per-file-type nesting (heuristic handles file type)
```

**Validation:**
- Run must be in `AWAITING_MAPPING_CONFIRMATION` state
- All `gl_account` values must be in the `gl_account_pool` from `parse_preview["mapping_draft"]` (API guard against hallucinated names)
- Empty decisions → 400 (at least one mapping required)

**Response (immediate):**
```json
{"status": "applying_mappings", "run_id": "..."}
```
BackgroundTask calls `apply_mapping_and_consolidate(run_id, company_id, period, body.decisions)`.

### 6.3 Modify `GET /runs/{id}/status`

When state is `awaiting_mapping_confirmation`, include `mapping_draft` in response:
```python
if run["status"] == "awaiting_mapping_confirmation":
    parse_preview = run.get("parse_preview") or {}
    response["mapping_draft"] = parse_preview.get("mapping_draft")
```

### 6.4 Modify `backend/messages.py`

Add:
```python
MAPPING_FAILED = "We couldn't classify your accounts. Please re-upload."
MAPPING_INVALID_GL_ACCOUNT = "One or more selected GL accounts is no longer valid."
```

### 6.5 Acceptance

New route tests:
- Confirm-mappings with bad gl_account not in pool → 400
- Confirm-mappings on wrong-state run → 409
- Confirm-mappings success → 200 + background task starts

---

## PHASE 7 — DI wiring (15 min)

### 7.1 Modify `backend/api/deps.py`

Add AccountMapper factory:
```python
def get_account_mapper() -> AccountMapper:
    return AccountMapper(llm_client=get_llm_client())
```

Import `run_multi_file_parser_with_mapping` and `apply_mapping_and_consolidate` in `routes.py`.

### 7.2 Modify `backend/agents/orchestrator.py`

Import AccountMapper and use in the new functions:
```python
from backend.agents.account_mapper import AccountMapper
```

AccountMapper is instantiated inline in the orchestrator functions (same pattern as ParserAgent).

### 7.3 Acceptance

- Server starts: `uvicorn backend.main:app --reload`
- `GET /health` → 200
- No import errors

---

## PHASE 8 — Backend integration test (30 min)

### 8.1 New file: `tests/integration/test_account_mapper_flow.py`

Stub Haiku response. Walk:
1. Upload GL + payroll (2 files)
2. Assert run reaches `AWAITING_MAPPING_CONFIRMATION`
3. GET status → assert `mapping_draft` populated with payroll employee names
4. POST confirm-mappings with `{employee_name: "Salaries & Wages"}` for all
5. Assert run reaches `AWAITING_CONFIRMATION`
6. POST /runs/{id}/confirm
7. Assert run reaches `complete`
8. Assert reconciliation items use GL account names (not employee names)

### 8.2 Acceptance

- This test green
- Full unit suite still green: `pytest -q`

---

## PHASE 9 — Frontend (2 hours)

### 9.1 Modify `frontend/src/components/LoadingProgress.tsx`

Add `awaiting_mapping_confirmation` to the terminal-state check so polling continues through it:
```typescript
const isTerminal = (status: string) =>
  status === "complete" ||
  status === "guardrail_failed" ||
  status === "awaiting_mapping_confirmation" ||  // NEW — pause for user review
  status === "awaiting_confirmation" ||
  ...
```

Add callback:
```typescript
onAwaitingMappingConfirmation?: (runId: string, draft: MappingDraft) => void;
```

In the status handler:
```typescript
if (status === "awaiting_mapping_confirmation" && mapping_draft) {
  onAwaitingMappingConfirmation?.(runId, mapping_draft);
}
```

### 9.2 New file: `frontend/src/components/MappingReview.tsx`

**Layout:**
```
AI Account Mapping Review
─────────────────────────────────────────────────────────
The system identified the following values in your files.
Review and confirm the suggested GL account for each.
─────────────────────────────────────────────────────────

[Payroll — helix_payroll_mar_2026.xlsx]
  Source Value          Suggested GL Account      Status
  Alice Johnson         [Salaries & Wages   ▾]    ✓ Confident
  Nathan Cruz           [Salaries & Wages   ▾]    ✓ Confident
  David Lee (Bonus)     [Bonuses            ▾]    ✓ Confident

[Supplier Invoices — helix_vendor_invoices_mar_2026.xlsx]
  TechPros Inc.         [Subcontractor Costs ▾]   ✓ Confident
  DataBridge LLC        [Subcontractor Costs ▾]   ✓ Confident
  CableMax Corp         [-- choose --        ▾]   ⚠ Unsure

[Confirm Mappings]
```

**Visual rules:**
- `confident: true` → green check, pre-selected, tinted neutral
- `confident: false` → yellow warning, placeholder `-- choose --`, tinted yellow
- Dropdown options: `mapping_draft.gl_account_pool` (sorted A-Z)
- "Confirm Mappings" disabled until all `confident: false` rows have a selection

**On submit:**
```typescript
const decisions: Record<string, string> = {};
items.forEach(item => {
  if (selectedValues[item.source_pattern]) {
    decisions[item.source_pattern] = selectedValues[item.source_pattern];
  }
});
await apiFetch(`/runs/${runId}/confirm-mappings`, {
  method: "POST",
  body: JSON.stringify({ decisions }),
});
// Poll until awaiting_confirmation, then show existing ParsePreviewPanel
```

**TypeScript interface:**
```typescript
interface MappingDraftItem {
  source_pattern: string;
  source_file: string;
  file_type: string;
  suggested_gl_account: string | null;
  confident: boolean;
}

interface MappingDraft {
  items: MappingDraftItem[];
  gl_account_pool: string[];
}
```

### 9.3 Modify `frontend/src/pages/UploadPage.tsx`

Add `mapping-review` view state and handler:
```typescript
function handleAwaitingMappingConfirmation(runId: string, draft: MappingDraft) {
  setMappingDraft(draft);
  setView("mapping-review");
}

// In JSX:
if (view === "mapping-review" && mappingDraft && currentRunId) {
  return (
    <MappingReview
      runId={currentRunId}
      draft={mappingDraft}
      onConfirmed={handleMappingConfirmed}
    />
  );
}
```

`handleMappingConfirmed` → `setView("processing")` (resumes polling, pipeline continues to `AWAITING_CONFIRMATION`).

### 9.4 No changes to `FileUpload.tsx`

File type dropdown **not added** (heuristic-based). Upload form unchanged.

### 9.5 Acceptance

- Upload form unchanged: no new dropdown, no regression
- Upload GL + payroll → MappingReview renders with employee names grouped by file
- Confident rows pre-selected
- Unsure rows blocked until user selects
- Submit → polls → ParsePreviewPanel renders with reconciliations
- Network tab confirms `decisions` flat dict payload

---

## PHASE 10 — End-to-end smoke test (30 min)

### 10.1 Test with Helix (IT Consulting)

Upload `helix_gl_mar_2026.xlsx` + `helix_payroll_mar_2026.xlsx` + `helix_vendor_invoices_mar_2026.xlsx` — **the original files, with employee names and vendor names as-is (no pre-added Account column)**.

Expected flow:
1. Run → `AWAITING_MAPPING_CONFIRMATION`
2. MappingReview shows employee names (T. Rivera, M. Chen...) → suggested "Salaries & Wages"
3. Vendor names (TechPros Inc., DataBridge LLC...) → suggested "Subcontractor Costs"
4. User confirms → `AWAITING_CONFIRMATION`
5. Confirm → `COMPLETE`
6. Report shows cross-source reconciliation with REAL vendor/employee names mapped to GL accounts

### 10.2 Acceptance criteria

- `run.status == "complete"` ✅
- `reconciliations[].account` contains GL account names (not employee/vendor names) ✅
- `reconciliations[].classification` includes ≥2 distinct types ✅
- `missing_je`: vendor invoice not in GL ✅
- `categorical_misclassification`: bonus misclassified in payroll ✅

---

## File-change inventory

### Backend — new
| File | Purpose |
|---|---|
| `backend/agents/account_mapper.py` | AccountMapper agent |
| `backend/prompts/account_mapping_prompt.txt` | Haiku prompt for GL name mapping |
| `tests/agents/test_account_mapper.py` | Unit tests |
| `tests/integration/test_account_mapper_flow.py` | Integration test |

### Backend — modified
| File | Change |
|---|---|
| `backend/domain/run_state_machine.py` | Add `AWAITING_MAPPING_CONFIRMATION` state |
| `backend/domain/contracts.py` | Add `SourceFileType`, `MappingDraft`, `MappingDraftItem`, `AccountMappingResponse` |
| `backend/agents/parser.py` | Add `account_name_map` param to `parse_file_silently` (3 lines) |
| `backend/agents/orchestrator.py` | Add `_detect_file_type()`, `run_multi_file_parser_with_mapping()`, `apply_mapping_and_consolidate()` |
| `backend/api/routes.py` | Add `POST /runs/{id}/confirm-mappings`; modify upload to call new orchestrator fn; expose `mapping_draft` in status |
| `backend/messages.py` | Add `MAPPING_FAILED`, `MAPPING_INVALID_GL_ACCOUNT` |
| `backend/api/deps.py` | Add `get_account_mapper()` |

### Frontend — new
| File | Purpose |
|---|---|
| `frontend/src/components/MappingReview.tsx` | Mapping approval UI |

### Frontend — modified
| File | Change |
|---|---|
| `frontend/src/components/LoadingProgress.tsx` | Handle `awaiting_mapping_confirmation` state |
| `frontend/src/pages/UploadPage.tsx` | Add `mapping-review` view, `handleAwaitingMappingConfirmation` |

### Database
**No migration required.** Cache table deferred to post-MVP.

---

## API surface changes

### Modified
- `POST /upload`: no interface change — internally routes to new orchestrator function
- `GET /runs/{id}/status`: includes `mapping_draft` when state is `awaiting_mapping_confirmation`

### New
- `POST /runs/{run_id}/confirm-mappings`
  - Body: `{"decisions": {"source_pattern": "gl_account_name"}}`
  - Validates: all gl_accounts ∈ `gl_account_pool`; state == `AWAITING_MAPPING_CONFIRMATION`
  - Returns immediately: `{"status": "applying_mappings", "run_id": "..."}`
  - Background: `apply_mapping_and_consolidate()`

---

## Execution order

Each phase has explicit acceptance criteria. Do not advance until criteria are green.

```
Phase 0  → pre-flight (20 min)
Phase 1  → no-op (no migration)
Phase 2  → domain: state machine + contracts (30 min)
Phase 3  → new prompt (20 min)
Phase 4  → AccountMapper agent + parser change (2 hrs)
Phase 5  → orchestrator new functions (2.5 hrs)
Phase 6  → API routes (45 min)
Phase 7  → DI wiring (15 min)
Phase 8  → integration test (30 min)
Phase 9  → frontend (2 hrs)
Phase 10 → smoke test (30 min)

Total: ~9 hours
```

---

## Risk register

| Risk | Mitigation |
|---|---|
| Double-parse adds 30s per run | Acceptable for MVP; files are small (4-5 files, <200 rows each) |
| Haiku doesn't recognize vendor names in specific industry | Fallback: confident=false → user selects manually from dropdown |
| `parse_file_silently` interface change breaks existing flow | Parameter is optional (default None) — existing callers unaffected |
| MappingReview blocks on all-unsure rows | "Skip" option in dropdown maps to no change; user can submit with original names |
| `_detect_file_type` heuristic mismatch | Edge case: file labeled wrong → wrong context to Haiku → lower mapping quality → more unsure rows → user corrects. Acceptable. |

---

## Post-MVP backlog (do not build now)

- `account_mappings` cache table — spec archived below
- Per-file type dropdown in FileUpload UI
- `rapidfuzz` pre-filter to reduce Haiku calls
- Stale mapping override UI ("previously approved" pill)
- Multi-worker safe re-parse via storage key persistence (already works via runs.storage_key)

---

## Archive: `account_mappings` cache table (post-MVP)

```sql
CREATE TABLE account_mappings (
  id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  company_id        UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
  source_pattern    TEXT NOT NULL,
  gl_account        TEXT NOT NULL,
  source_file_type  TEXT NOT NULL,
  created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CONSTRAINT account_mappings_unique
    UNIQUE (company_id, source_pattern, source_file_type)
);
CREATE INDEX idx_account_mappings_lookup ON account_mappings (company_id, source_file_type);
ALTER TABLE account_mappings ENABLE ROW LEVEL SECURITY;
CREATE POLICY account_mappings_owner ON account_mappings FOR ALL USING (
  EXISTS (SELECT 1 FROM companies c WHERE c.id = account_mappings.company_id AND c.owner_id = auth.uid())
);
```

When cache is added: `AccountMapper.build_draft()` checks cache first, only calls Haiku for cache misses. `apply_mapping_and_consolidate()` writes approved decisions to cache after user confirmation.
