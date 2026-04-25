# AccountMapper — Sprint Plan

> ## ⏸ STATUS: PAUSED FOR HACKATHON DEMO
>
> **Decision date:** 2026-04-25 — ~24 hours before the live demo.
>
> **Why paused:** Engineering review surfaced 18 issues in this plan. Realistic build cost was re-estimated at 14–17 hours of focused work, against a 24-hour wall clock. The team chose the lower-risk path: **demo three sectors (E-commerce, Security Services, IT Consulting) with curated demo data through the existing pipeline.** That path requires zero new code and preserves the smoke-tested foundation.
>
> **The "AI infers your chart of accounts" feature this plan describes is genuinely valuable** — but it is a v1.1 feature, not a hackathon MVP feature. This document is preserved verbatim below as the build spec for the post-hackathon push.
>
> **Active execution plan now lives at:** `docs/02-planning/three_sector_demo_plan.md`.
>
> ---
>
> ## Decisions log — pre-execution audit (locked in before pause)
>
> A senior engineer reviewed this plan and surfaced 18 potential issues. We triaged them into three buckets. **All decisions below stand for v1.1 implementation.** When execution resumes, start by applying these 7 fixes to the plan as written.
>
> ### 🔴 Demo-breakers — MUST fix before any code is written (5 items)
>
> 1. **Orchestrator structure mismatch.** The plan assumes `Orchestrator.start_run()` / `apply_mapping_decisions()` class methods. The actual code (`backend/agents/orchestrator.py`) is a module of free functions. Phase 5 must be rewritten to **extend the existing `run_multi_file_parser_until_preview()` function** and add a sibling `apply_mapping_decisions()` function — not split a class.
>
> 2. **`file_types[]` plumbing is missing end-to-end.** The upload route accepts `UploadFile`s, persists to Supabase Storage, and hands the orchestrator only `storage_keys: list[str]`. The user-supplied `file_type` per file gets dropped on the floor. **Fix:** persist `file_types` as a parallel array on the `runs` row at upload time (new column or `parse_preview` JSONB key), then read it back in the orchestrator. Without this, the mapper cannot distinguish GL vs payroll vs supplier.
>
> 3. **Phase 0.2 verification is incomplete.** Currently checks `stale_reference` and `timing_cutoff` against demo data; **misses `categorical_misclassification`**. All four classifications must be verified against demo data before coding starts. Add a check: at least one supplier/contract line whose dollar amount, when mapped, lands under a different GL account than the GL booked it under.
>
> 4. **Description-append step is broken.** The plan says "append `{original} | {existing}` to the `description` column," but `parse_file_silently()` returns aggregated `preview_rows` (grouped by account via `groupby("account").sum()`). There is no row-level `description` column at the point AccountMapper runs. **Decision: cut the description-append from MVP entirely.** Provenance lives in `source_breakdown_by_account` already.
>
> 5. **Cache pre-warm is mandatory, not optional.** *(Promoted from yellow → red.)* A fresh Haiku call on stage with no cache is a 30-second silence away from killing the demo. **Build:** a one-shot script that runs the full demo flow against each sector's data 5 minutes before going on stage, populating `account_mappings`. Live demo replays the cached path. Without this, the AI demo moment is one network hiccup away from disaster.
>
> ### 🟡 Should-fix — low effort, meaningful confidence boost (2 items)
>
> 6. **JSONB instead of `/tmp/ironledger_runs/` parquet scratch.** The original plan introduces a temp scratch directory. This is brand-new infrastructure with cleanup risk (Railway containers cycle on deploy → orphan parquets). **Fix:** persist the per-file aggregated DataFrames inside the existing `runs.parse_preview` JSONB column under a `parsed_frames` key. Same column already in production, no new infra, multi-worker safe.
>
> 7. **Cache writes the user's final decision.** The plan's step "cache approved mappings where the user didn't change Haiku's suggestion" is wrong. Cache **whatever the user submitted** — that's the source of truth, regardless of whether they accepted or overrode the AI suggestion.
>
> ### 🟢 Ignored for hackathon MVP (11 items — accept as known limitations)
>
> Single-file upload edge case (only multi-file produces reconciliations anyway), concurrent runs (single-user demo), user mislabeling file types (rehearsed presenter), corrupt files (curated demo data), double-click idempotency on confirm-mappings (state-machine guard catches it), all-mappings-confident-false (cache pre-warm covers it), all-NaN account columns (logger warning is enough), unused `MAPPING` enum value (cosmetic), filename heuristic for default file_type (default to `supplier_invoices` and let user override), description-append (already cut as item #4), orphan parquet cleanup on server crash (eliminated by item #6).
>
> None of these will surface in a rehearsed 6-minute demo. They are documented here so they don't get re-litigated post-hackathon.
>
> ### Strategic decision — 3 sectors instead of AccountMapper
>
> The triage above proves that AccountMapper can be built cleanly, but the time cost (14–17 hours) consumes the entire hackathon runway. **The team's headline pitch is "this works across three different industries" — that story is best told by demoing E-commerce + Security Services + IT Consulting through the existing (smoke-tested) pipeline with curated data, not by deepening the AI sophistication on a single sector.**
>
> Execution moves to `docs/02-planning/three_sector_demo_plan.md`. AccountMapper resumes after the hackathon.
>
> ---
> ---

**Scope:** Insert an AI-powered account mapping layer between Parser and Consolidator so that vendor/employee/customer names from messy files get translated to canonical GL account names before reconciliation.

**Constraint:** Plan must be specific enough that Sonnet 4.6 can execute each phase in isolation without re-deriving design decisions.

**Decisions baked in (locked):**
- File type chosen by user at upload (dropdown per file)
- 6 US-GAAP categories as fallback when no GL exists in the run
- Two-step confirmation: AWAITING_MAPPING_CONFIRMATION → AWAITING_CONFIRMATION
- Description column appended (`{original} | {existing}`), no schema change
- Hallucinated GL accounts → silently demoted to `confident: false`
- All mappings shown for review, `confident: true` ones pre-checked
- No rapidfuzz pre-filter (post-MVP)
- GL files first in orchestrator; GL bypasses mapper
- Mapping draft persisted in `runs.parse_preview` JSONB under `mapping_draft` key
- File type validated via Pydantic `Literal`, stored as `TEXT NOT NULL` in DB

**Estimated total effort:** 8–10 hours of focused work (was originally pitched as 3.5h — that estimate undercounted file blast radius).

---

## PHASE 0 — Pre-flight (30 min)

**Goal:** Branch hygiene + verify the demo data can actually fire all 4 classifications.

### 0.1 Branch setup
- Create branch `feat/account-mapper`
- Confirm `main` is green: `pytest -q` → all 94 tests pass

### 0.2 Demo data verification
Open `docs/demo_data/sentinel/sentinel_contracts_mar_2026.xlsx`. Compute:
- Sum of all contract amounts where status = "active"
- Compare to GL "Service Revenue" total in `sentinel_gl_mar_2026.xlsx`
- **Required:** non-zero delta to fire `stale_reference`

Open all sentinel files. Find:
- At least one row with `date > 2026-03-31` to fire `timing_cutoff` (uses `crosses_period_boundary` hint)

**If either condition fails:** edit the demo files (one-time fix) before starting Phase 1. Don't write code that the data won't exercise.

### 0.3 Acceptance
- Branch exists
- Pre-existing tests green
- Demo data confirmed to support all 4 classifications

---

## PHASE 1 — Database migration (30 min)

### 1.1 New file: `supabase/migrations/0008_account_mappings.sql`

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

CREATE INDEX idx_account_mappings_lookup
  ON account_mappings (company_id, source_file_type);

ALTER TABLE account_mappings ENABLE ROW LEVEL SECURITY;

CREATE POLICY account_mappings_owner ON account_mappings
  FOR ALL
  USING (
    EXISTS (
      SELECT 1 FROM companies c
      WHERE c.id = account_mappings.company_id
        AND c.owner_id = auth.uid()
    )
  );

CREATE TRIGGER set_account_mappings_updated_at
  BEFORE UPDATE ON account_mappings
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();
```

### 1.2 Run migration
```bash
supabase db push
```

### 1.3 Acceptance
- `\d account_mappings` in psql shows the table
- Insert one test row via service key → succeeds
- Insert duplicate `(company_id, source_pattern, source_file_type)` → fails with unique-violation
- Authenticated select with another user → returns zero rows (RLS)

---

## PHASE 2 — Domain layer (45 min)

Domain has zero I/O. All changes are type/contract/state-machine.

### 2.1 Modify `backend/domain/contracts.py`

Add at top, near `ReconciliationClassification`:

```python
SourceFileType = Literal[
    "general_ledger",
    "payroll",
    "supplier_invoices",
    "contracts",
]

# Used as fallback target list when no GL is present in the run.
DEFAULT_GL_CATEGORIES = [
    "REVENUE",
    "COGS",
    "OPEX",
    "G&A",
    "R&D",
    "OTHER_INCOME",
]
```

Add new models near the existing `MappingResponse`:

```python
class AccountMappingDecision(BaseModel):
    gl_account: str | None
    confident: bool


class AccountMappingResponse(BaseModel):
    """Haiku output: {raw_value: {gl_account, confident}}."""
    mappings: dict[str, AccountMappingDecision]


class MappingDraftItem(BaseModel):
    source_pattern: str          # raw value from file (e.g. "AlarmTech Industries")
    source_file_type: SourceFileType
    suggested_gl_account: str | None
    confident: bool              # pre-check the row in UI when True
    cached: bool = False         # came from account_mappings, not Haiku


class MappingDraft(BaseModel):
    items: list[MappingDraftItem]
    gl_account_pool: list[str]   # what mapper offered as the dropdown options
```

### 2.2 Modify `backend/domain/run_state_machine.py`

Add the new state and transitions. Replace the `_ALLOWED` map:

```python
class RunStatus(str, Enum):
    PENDING = "pending"
    PARSING = "parsing"
    DISCOVERING = "discovering"
    AWAITING_DISCOVERY_CONFIRMATION = "awaiting_discovery_confirmation"
    MAPPING = "mapping"
    AWAITING_MAPPING_CONFIRMATION = "awaiting_mapping_confirmation"   # NEW
    AWAITING_CONFIRMATION = "awaiting_confirmation"
    COMPARING = "comparing"
    GENERATING = "generating"
    COMPLETE = "complete"
    UPLOAD_FAILED = "upload_failed"
    PARSING_FAILED = "parsing_failed"
    GUARDRAIL_FAILED = "guardrail_failed"
```

Update `_ALLOWED`:
- `PARSING` → adds `AWAITING_MAPPING_CONFIRMATION` (keep existing `AWAITING_CONFIRMATION` for the GL-only flow)
- New: `AWAITING_MAPPING_CONFIRMATION` → `{AWAITING_CONFIRMATION, PARSING_FAILED}`

### 2.3 Modify `backend/domain/ports.py`

Add new Protocol:

```python
class AccountMappingsRepo(Protocol):
    def get_for_company(
        self, company_id: str, source_file_type: str
    ) -> dict[str, str]:
        """Return {source_pattern: gl_account} cache for a (company, file_type) scope."""
        ...

    def upsert_many(
        self,
        company_id: str,
        source_file_type: str,
        mappings: dict[str, str],
    ) -> None:
        """Idempotent: ON CONFLICT (company_id, source_pattern, source_file_type) DO UPDATE."""
        ...
```

### 2.4 Modify `backend/domain/errors.py`

No new errors. Hallucinated accounts handled silently as `confident: false`. Haiku I/O errors already covered by `TransientIOError`.

### 2.5 Acceptance
- `pytest tests/domain/` green
- `python -c "from backend.domain.contracts import SourceFileType, AccountMappingResponse, MappingDraft"` succeeds
- New state machine transitions are unit-tested in `tests/domain/test_run_state_machine.py` (add 2 tests: PARSING→AWAITING_MAPPING_CONFIRMATION valid, AWAITING_MAPPING_CONFIRMATION→COMPARING invalid)

---

## PHASE 3 — Adapter layer (45 min)

### 3.1 Modify `backend/adapters/supabase_repos.py`

Add new class:

```python
class SupabaseAccountMappingsRepo:
    def __init__(self, client: Client) -> None:
        self._client = client

    def get_for_company(
        self, company_id: str, source_file_type: str
    ) -> dict[str, str]:
        resp = (
            self._client.table("account_mappings")
            .select("source_pattern, gl_account")
            .eq("company_id", company_id)
            .eq("source_file_type", source_file_type)
            .execute()
        )
        return {r["source_pattern"]: r["gl_account"] for r in (resp.data or [])}

    def upsert_many(
        self,
        company_id: str,
        source_file_type: str,
        mappings: dict[str, str],
    ) -> None:
        if not mappings:
            return
        rows = [
            {
                "company_id": company_id,
                "source_pattern": pattern,
                "gl_account": gl,
                "source_file_type": source_file_type,
            }
            for pattern, gl in mappings.items()
        ]
        (
            self._client.table("account_mappings")
            .upsert(rows, on_conflict="company_id,source_pattern,source_file_type")
            .execute()
        )
```

Wrap calls in the same try/except pattern other repos use; raise `TransientIOError` on connection failures.

### 3.2 New file: `backend/prompts/account_mapping_prompt.txt`

```
You are a US GAAP account-mapping assistant. You will receive:
- "values": a list of raw text values extracted from a source file's primary identifier column (e.g. employee names, vendor names, customer names)
- "file_type": one of "payroll", "supplier_invoices", "contracts"
- "gl_accounts": the company's chart of accounts (canonical names)

Your job: for each value, return the single best GL account name from gl_accounts.

Rules:
- Use ONLY names from the provided gl_accounts list. Do not invent new accounts.
- If no plausible match exists in gl_accounts, set gl_account to null and confident to false.
- "confident" is true only when the mapping is unambiguous given file_type context:
  * payroll → individual people map to a salaries/wages account
  * supplier_invoices → vendors map to the cost-of-goods or expense category they sell
  * contracts → customers map to the corresponding revenue account
- If a value is structural (a header row, a subtotal label, "TOTAL") return null + confident=false.
- Do not perform arithmetic. Do not modify the value strings.

Return ONLY valid JSON with this exact shape:
{
  "mappings": {
    "<value exactly as given>": {"gl_account": "<name from gl_accounts or null>", "confident": <true|false>}
  }
}

One entry per input value. No prose outside the JSON.
```

### 3.3 Acceptance
- New repo class importable
- Unit test: stub `Client`, call `get_for_company` and `upsert_many`, assert correct query shape
- Prompt file exists with non-zero size

---

## PHASE 4 — AccountMapper agent (1.5 hr)

### 4.1 New file: `backend/agents/account_mapper.py`

Module docstring:
```
"""AccountMapper — translate raw source values to canonical GL account names.

Pipeline per file:
  1. Extract df['account'].unique() → set of raw values.
  2. Cache lookup against account_mappings — instant resolution for known patterns.
  3. Remaining unknowns → single Haiku call with the company's GL list.
  4. Validate Haiku's outputs: any gl_account NOT in the supplied pool → demote to confident=false.
  5. Apply: df['account'] = df['account'].map(resolved). Append original to description.
  6. Return (mapped_df, MappingDraft).
"""
```

Public API:

```python
MAPPING_MODEL = "claude-haiku-4-5-20251001"

class AccountMapper:
    def __init__(
        self,
        llm_client: LLMClient,
        mappings_repo: AccountMappingsRepo,
        accounts_repo: AccountsRepo,
    ) -> None: ...

    def apply(
        self,
        df: pd.DataFrame,
        company_id: str,
        source_file_type: SourceFileType,
    ) -> tuple[pd.DataFrame, MappingDraft]:
        ...
```

Internal flow:

1. `uniques = sorted({str(v).strip() for v in df["account"].dropna().unique()})`
2. `cached = self._mappings_repo.get_for_company(company_id, source_file_type)`
3. `gl_pool = self._accounts_repo.list_account_names(company_id) or list(DEFAULT_GL_CATEGORIES)`
4. `unknown = [u for u in uniques if u not in cached]`
5. If `unknown`:
   - `ctx = {"values": unknown, "file_type": source_file_type, "gl_accounts": gl_pool}`
   - `resp: AccountMappingResponse = self._llm.call("account_mapping_prompt.txt", MAPPING_MODEL, ctx, AccountMappingResponse)`
   - For each value in `resp.mappings`:
     - if `gl_account` is not None and not in `gl_pool` → set `gl_account=None, confident=False` (hallucination guardrail)
6. Build `MappingDraft.items`:
   - cached entries → `confident=True, cached=True, suggested=cached[v]`
   - haiku entries → `confident=resp.confident, cached=False, suggested=resp.gl_account`
7. Apply mapping to DataFrame:
   - Build `resolved = {v: cached_or_haiku_or_None for v in uniques}`
   - `df["account_original"] = df["account"]` (temp column)
   - `df["account"] = df["account_original"].map(resolved)` (None preserved as NaN; row stays)
   - Append: `df["description"] = df.apply(lambda r: f"{r['account_original']} | {r['description']}" if pd.notna(r['description']) else r['account_original'], axis=1)`
   - Drop `account_original`
8. Return `(df, MappingDraft(items=..., gl_account_pool=gl_pool))`

**Important details:**
- Rows where the resolved value is `None` (Haiku said `confident=False, gl_account=None`) keep `account` as NaN. Consolidator already drops NaN-account rows. They re-enter the picture only after the user corrects them in the review UI.
- `df['account'].map(d)` does the unique-only work — no per-row LLM calls.
- Logger: emit one event per file with `event="account_mapping"`, `cached_count`, `haiku_count`, `unmapped_count`. **Never log raw values.**

### 4.2 Acceptance
- `tests/agents/test_account_mapper.py` covers:
  - Cache hit → no Haiku call (assert mock not called)
  - Pure unknown → single Haiku call with all uniques
  - Mixed cache + unknown → Haiku gets only the unknowns
  - Haiku returns hallucinated `gl_account` not in pool → demoted to `confident=False`
  - Description append when description already populated
  - Description fill when description is None
  - Empty df → returns empty draft, no Haiku call
  - GL pool empty → falls back to `DEFAULT_GL_CATEGORIES`
- Minimum 8 unit tests

---

## PHASE 5 — Orchestrator integration (1.5 hr)

This is the largest blast radius — the orchestrator splits into two phases.

### 5.1 Modify `backend/agents/orchestrator.py`

**Function signatures (sketch):**

```python
def start_run(self, run_id, company_id, period, files: list[UploadedFile]) -> None:
    """Phase A: parse → map → AWAITING_MAPPING_CONFIRMATION (or AWAITING_CONFIRMATION if all GL).

    Files arrive with .file_type already set by the upload route.
    """

def apply_mapping_decisions(
    self, run_id, user_decisions: dict[str, dict[str, str]]
) -> None:
    """Phase B: apply user-edited mappings → consolidate → reconcile → AWAITING_CONFIRMATION.

    user_decisions structure (per file_type):
      {"payroll": {"T. Rivera": "Salaries & Wages", ...}, "supplier_invoices": {...}}
    """
```

**Phase A flow (start_run):**

1. State: `PENDING → PARSING`
2. Sort files: `files.sort(key=lambda f: 0 if f.file_type == "general_ledger" else 1)`
3. For each file:
   - `df = parser.parse_file_silently(f)` (existing)
   - Serialize parsed df to a temp parquet at `/tmp/ironledger_runs/{run_id}/{file_id}.parquet` (survives multi-worker, cheap, no DB pressure)
   - If `f.file_type == "general_ledger"`: parser already wrote to accounts_repo → continue to next file
   - Else: `mapped_df, draft = mapper.apply(df, company_id, f.file_type)` — store the `MappingDraft` per file_type in an aggregator
4. Build aggregate `MappingDraft` (concat per-file items into one list; gl_pool is the union)
5. If `draft.items` is empty (e.g., GL-only run):
   - Skip mapping confirm: continue inline to consolidate + reconcile (existing path)
   - Transition `PARSING → AWAITING_CONFIRMATION` (existing transition)
6. Else:
   - Persist draft to `runs.parse_preview` JSONB under `mapping_draft` key
   - Transition `PARSING → AWAITING_MAPPING_CONFIRMATION`
   - Return — orchestrator pauses

**Phase B flow (apply_mapping_decisions):**

1. Validate state: must be `AWAITING_MAPPING_CONFIRMATION`
2. Pull `parse_preview.mapping_draft` for the original draft (so we can detect what the user changed)
3. Pull every parquet from `/tmp/ironledger_runs/{run_id}/`
4. For each non-GL parquet:
   - Apply user decisions: `df["account"] = df["account_original"].map(user_decisions[file_type])`
   - Rows where the user-supplied mapping is empty → drop (those become a `MappingsRejected` skip, logged)
5. Concatenate all dfs → run existing consolidator + hint computer
6. Persist results to `runs.parse_preview.reconciliations` (existing pattern)
7. **Cache approved mappings:** for every (file_type, value, gl_account) where the user accepted (didn't change), call `mappings_repo.upsert_many(company_id, file_type, accepted)`
8. Remove `mapping_draft` from `parse_preview` (keep it in runs.events log if useful for audit; not required for MVP)
9. Clean up `/tmp/ironledger_runs/{run_id}/` parquets
10. Transition `AWAITING_MAPPING_CONFIRMATION → AWAITING_CONFIRMATION`
11. (Existing path resumes from here on the user's next confirm)

**Failure modes:**
- Parse fails on any file → `PARSING_FAILED` (existing)
- Haiku errors → `TransientIOError` from adapter → `PARSING_FAILED` with `messages.MAPPING_FAILED`
- User submits decisions referencing GL accounts not in pool → reject 400 at API layer (Phase 6)

### 5.2 Acceptance
- `tests/agents/test_orchestrator.py` covers:
  - Pure GL upload → no AWAITING_MAPPING_CONFIRMATION state, goes direct to AWAITING_CONFIRMATION
  - GL + payroll → state passes through AWAITING_MAPPING_CONFIRMATION
  - Files uploaded in `[payroll, GL]` order → orchestrator processes GL first (assert call order on parser mock)
  - Phase B with user decisions different from Haiku → final df has user's choices, cache stores user's choices
  - Phase B drops rows the user left unmapped

---

## PHASE 6 — API routes (1 hr)

### 6.1 Modify `backend/api/routes.py` — `POST /upload`

Current contract: multipart `files` + `period`. Add per-file `file_types` field.

Multipart shape:
- `files[]`: file uploads
- `file_types[]`: same length as files, parallel array of `SourceFileType` strings
- `period`: ISO date

Validation:
- `len(files) == len(file_types)` else 400
- Every `file_types[i] in SourceFileType.__args__` else 400
- Exactly zero or one `file_types[i] == "general_ledger"` (we don't support multiple GLs in one run for MVP) else 400

Wire `file_type` onto each `UploadedFile` before passing to orchestrator.

### 6.2 Modify `backend/api/routes.py` — new endpoint

```python
@router.post("/runs/{run_id}/confirm-mappings")
async def confirm_mappings(
    run_id: str,
    body: ConfirmMappingsRequest,
    user_id: str = Depends(get_user_id),
):
    ...
```

`ConfirmMappingsRequest` schema:
```python
class ConfirmMappingsRequest(BaseModel):
    decisions: dict[SourceFileType, dict[str, str]]
    # {"payroll": {"T. Rivera": "Salaries & Wages", ...}, ...}
```

Validation:
- All `gl_account` values must be in the saved `mapping_draft.gl_account_pool` — reject otherwise (this is the API-layer guard against the user submitting hallucinated names)
- Run must be in state `AWAITING_MAPPING_CONFIRMATION`

Call `orchestrator.apply_mapping_decisions(run_id, body.decisions)` as a **FastAPI BackgroundTask** so the response returns immediately. The user's UI will poll `/runs/{id}/status` for state changes.

Response (immediate):
```json
{"status": "applying_mappings", "run_id": "..."}
```

### 6.3 Modify `backend/api/routes.py` — `GET /runs/{id}/status`

Already exists. Make sure it surfaces `parse_preview.mapping_draft` to the frontend when state == `AWAITING_MAPPING_CONFIRMATION`. If it doesn't currently, add it.

### 6.4 Modify `backend/messages.py`

Add:
- `MAPPING_FAILED = "We couldn't classify your accounts. Please re-upload."`
- `MAPPING_INVALID_GL_ACCOUNT = "One or more selected GL accounts is no longer valid."`

### 6.5 Acceptance
- `pytest tests/api/` green
- New tests:
  - Upload with mismatched files/file_types lengths → 400
  - Upload with two `general_ledger` files → 400
  - Confirm-mappings with bad gl_account → 400
  - Confirm-mappings on wrong-state run → 409

---

## PHASE 7 — DI wiring (15 min)

### 7.1 Modify `backend/api/deps.py`

Build once, inject into orchestrator and routes:

```python
def get_account_mappings_repo() -> AccountMappingsRepo:
    return SupabaseAccountMappingsRepo(_supabase_client)

def get_account_mapper() -> AccountMapper:
    return AccountMapper(
        llm_client=get_llm_client(),
        mappings_repo=get_account_mappings_repo(),
        accounts_repo=get_accounts_repo(),
    )

def get_orchestrator() -> Orchestrator:
    return Orchestrator(
        ...
        account_mapper=get_account_mapper(),
        ...
    )
```

### 7.2 Acceptance
- Server starts: `uvicorn backend.main:app --reload`
- `GET /health` returns 200
- No import errors

---

## PHASE 8 — Backend integration test (45 min)

### 8.1 New file: `tests/integration/test_account_mapper_e2e.py`

Spin up the orchestrator with real adapters but stubbed Haiku (return canned JSON). Walk:
1. Upload 3 files (GL + payroll + supplier)
2. Assert run reaches `AWAITING_MAPPING_CONFIRMATION`
3. GET status → assert `mapping_draft` populated with non-zero items
4. POST confirm-mappings with a mix of accept-haiku and override-haiku decisions
5. Assert run reaches `AWAITING_CONFIRMATION`
6. Assert `account_mappings` table has the user's choices (not Haiku's, where they differ)
7. POST /runs/{id}/confirm
8. Assert run reaches `complete`
9. GET /report → assert `reconciliations[].classification` includes `categorical_misclassification` AND/OR `stale_reference` (i.e., not all `missing_je`)

### 8.2 Acceptance
- This test green
- Full unit suite still green

---

## PHASE 9 — Frontend (1.5 hr)

### 9.1 Modify `frontend/src/components/FileUpload.tsx`

For each selected file, render a row:
```
[filename]  [file_type dropdown ▾]  [✕]
```

Dropdown options (label / value):
- "General Ledger" / `general_ledger`
- "Payroll" / `payroll`
- "Supplier Invoices" / `supplier_invoices`
- "Contracts" / `contracts`

Default: filename heuristic suggestion (e.g., contains "gl" → `general_ledger`), but user can override. Default to `supplier_invoices` if no heuristic match.

On submit, build multipart with parallel `files[]` and `file_types[]` arrays.

### 9.2 New file: `frontend/src/components/MappingReview.tsx`

Triggered when run status === `awaiting_mapping_confirmation`. Layout:

```
Group by source_file_type:
  ┌─ Payroll ────────────────────────────────────────────┐
  │ Original Value     │ Suggested GL Account │ Confidence │
  │ T. Rivera          │ [Salaries & Wages ▾] │ ✓ confident│
  │ M. Chen            │ [Salaries & Wages ▾] │ ✓ confident│
  │ J. Patel           │ [Salaries & Wages ▾] │ ✓ confident│
  └──────────────────────────────────────────────────────┘
  ┌─ Supplier Invoices ──────────────────────────────────┐
  │ AlarmTech Industries │ [Equipment COGS ▾] │ ✓        │
  │ CableMax Corp        │ [-- choose --   ▾] │ ⚠ unsure │
  └──────────────────────────────────────────────────────┘
[Confirm All Mappings]
```

Visual rules:
- `confident: true` rows: green check, dropdown pre-selected, row tinted neutral
- `confident: false` rows: yellow warning, dropdown shows `-- choose --` placeholder, row tinted yellow
- Cached rows (`item.cached === true`): show "previously approved" pill — still editable
- Dropdown options: `mapping_draft.gl_account_pool` (sorted, with optional "-- skip this row --" sentinel that maps to no entry)

On submit:
- Build `decisions: dict[file_type, dict[value, gl_account]]`
- POST `/runs/{run_id}/confirm-mappings`
- Show spinner, poll status until state changes to `awaiting_confirmation` or `parsing_failed`

### 9.3 Modify the run-status polling component

Wherever the existing AWAITING_CONFIRMATION → ParsePreviewPanel routing lives, add a sibling case: `awaiting_mapping_confirmation` → `<MappingReview .../>`.

### 9.4 Acceptance
- `npm run dev` → upload form shows file_type dropdown per file
- Submit 3 sentinel files → MappingReview renders with grouped tables
- Confident rows show green check, pre-selected
- Override one Haiku suggestion → submit → polls → AWAITING_CONFIRMATION renders with reconciliations as before
- Network tab confirms `decisions` payload contains user's override

---

## PHASE 10 — End-to-end smoke test (30 min)

Repeat the smoke test we ran earlier, but with the mapping layer in place.

### 10.1 Test script
```bash
# Upload
curl POST /upload with 3 files + file_types[] = [general_ledger, payroll, supplier_invoices]

# Poll until awaiting_mapping_confirmation
# Get status, dump mapping_draft

# Confirm all suggested mappings as-is (accept Haiku output)
curl POST /runs/{id}/confirm-mappings with decisions matching draft.suggested_gl_account

# Poll until awaiting_confirmation
# Confirm reconciliations
curl POST /runs/{id}/confirm

# Poll until complete
# GET /report → query Supabase directly via service key
```

### 10.2 Assertions
- `run.status == "complete"`
- `reconciliations[].classification` distribution includes ≥3 of: `missing_je`, `categorical_misclassification`, `stale_reference`, `timing_cutoff`
- `account_mappings` table has rows for the company with `created_at` from this run
- Re-run the same upload → second run's mapping draft shows `cached: true` for the values approved in run 1, and Haiku call count drops accordingly (verify via log event `event="account_mapping"`)

### 10.3 Acceptance
- All assertions pass
- Logs show `cached_count`, `haiku_count`, `unmapped_count` per file
- No `null` accounts in the final consolidated DataFrame

---

## PHASE 11 — Demo dry run (30 min)

### 11.1 Walk-through
- Run the demo flow exactly as it will be presented:
  1. Upload 3 messy files with file-type dropdowns
  2. MappingReview screen shows AI-suggested mappings
  3. User approves → reconciliations appear with diverse classifications
  4. Confirm reconciliations → narrative includes `missing_je`, `stale_reference`, `categorical_misclassification`, `timing_cutoff`
- Time the full flow end-to-end (target: under 90 seconds)
- Screen-record the demo

### 11.2 Failure mode rehearsal
- Bad network mid-upload → graceful error
- Haiku 5xx → retry → eventually `PARSING_FAILED` with friendly message
- User cancels mid-mapping → run sits in `AWAITING_MAPPING_CONFIRMATION` indefinitely (acceptable for MVP — no expiry)

### 11.3 Acceptance
- Demo runs clean twice in a row from a clean state
- Cache hit visible on second run (`cached: true` pills appear)

---

## File-change inventory

### Backend — modified
| File | Change |
|---|---|
| `backend/domain/contracts.py` | Add `SourceFileType`, `DEFAULT_GL_CATEGORIES`, `AccountMappingDecision`, `AccountMappingResponse`, `MappingDraftItem`, `MappingDraft` |
| `backend/domain/run_state_machine.py` | Add `AWAITING_MAPPING_CONFIRMATION` enum + transitions |
| `backend/domain/ports.py` | Add `AccountMappingsRepo` Protocol |
| `backend/adapters/supabase_repos.py` | Add `SupabaseAccountMappingsRepo` class |
| `backend/agents/orchestrator.py` | Split into `start_run` (Phase A) + `apply_mapping_decisions` (Phase B); GL-first sort; parquet scratch |
| `backend/api/routes.py` | Modify `POST /upload`, modify `GET /runs/{id}/status`, add `POST /runs/{id}/confirm-mappings` |
| `backend/api/deps.py` | Wire `AccountMappingsRepo` and `AccountMapper` |
| `backend/messages.py` | Add `MAPPING_FAILED`, `MAPPING_INVALID_GL_ACCOUNT` |

### Backend — new
| File |
|---|
| `backend/agents/account_mapper.py` |
| `backend/prompts/account_mapping_prompt.txt` |
| `supabase/migrations/0008_account_mappings.sql` |
| `tests/agents/test_account_mapper.py` |
| `tests/integration/test_account_mapper_e2e.py` |

### Frontend — modified
| File | Change |
|---|---|
| `frontend/src/components/FileUpload.tsx` | Per-file `file_type` dropdown; multipart payload includes `file_types[]` |
| Run-status polling component | Add `awaiting_mapping_confirmation` → `<MappingReview/>` routing |

### Frontend — new
| File |
|---|
| `frontend/src/components/MappingReview.tsx` |

### Database
| File | Change |
|---|---|
| `supabase/migrations/0008_account_mappings.sql` | New table + unique constraint + RLS + updated_at trigger |

---

## API surface changes

### Modified
- `POST /upload`
  - Add multipart field `file_types[]` (parallel to `files[]`)
  - Validate length match, valid enum values, max one general_ledger
- `GET /runs/{id}/status`
  - When state == `awaiting_mapping_confirmation`, response includes `parse_preview.mapping_draft`

### New
- `POST /runs/{run_id}/confirm-mappings`
  - Body: `{decisions: {file_type: {source_pattern: gl_account}}}`
  - Validates all gl_accounts ∈ saved `gl_account_pool`
  - Validates run state == `AWAITING_MAPPING_CONFIRMATION`
  - Returns `{status: "applying_mappings", run_id}` immediately
  - Background task runs orchestrator Phase B

---

## Risk register

| Risk | Mitigation |
|---|---|
| Multi-worker FastAPI loses in-memory state | All state in DB or `/tmp/ironledger_runs/{run_id}/` parquets |
| Haiku hallucinates GL account name | AccountMapper validates against gl_pool, demotes to `confident=False` |
| Stale cache (vendor reclassified) | UI shows "previously approved" pill; user can override; upsert updates row |
| Parquet scratch dir fills up | Cleanup in Phase B step 9; cron sweep post-MVP |
| Bad demo data → not all 4 classifications fire | Phase 0.2 verifies before code is written |
| Time estimate slips | Phases are independently testable; ship Phases 0–8 (backend complete) before touching frontend |

---

## Execution order for Sonnet 4.6

1. **Phase 0** — pre-flight (human check)
2. **Phase 1** — migration (can run in parallel with Phase 2)
3. **Phase 2** — domain
4. **Phase 3** — adapter + prompt
5. **Phase 4** — AccountMapper agent + tests
6. **Phase 5** — orchestrator integration + tests
7. **Phase 6** — API routes
8. **Phase 7** — DI wiring (smoke test: server starts)
9. **Phase 8** — integration test (full backend green)
10. **Phase 9** — frontend (parallel with Phase 10 prep)
11. **Phase 10** — E2E smoke
12. **Phase 11** — demo dry run

Each phase has explicit acceptance criteria. Sonnet 4.6 should not advance to phase N+1 until phase N's acceptance criteria are green.
