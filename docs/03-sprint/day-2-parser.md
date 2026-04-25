# Day 2 — Parser Agent + Comparison Agent
*IronLedger 6-Day Sprint — Built with Opus 4.7 Hackathon, April 2026*

## Goal

Parser agent reads DRONE files end-to-end — strict pipeline order with PII stripped, Haiku-mapped to US GAAP, pandera-validated, written to `monthly_entries` via DELETE-then-INSERT. Comparison agent calculates variance in pure Python, writes anomalies, and emits `PandasSummary` as the frozen handoff to Day 3. Run status transitions through `RunStateMachine` at every step.

## End-of-Day Acceptance Check

> Using the demo user:
> 1. Upload `drone_feb_2026.xlsx` (period = `2026-02-01`). Verify it loads as baseline — all accounts have `severity="no_history"` in anomalies; `monthly_entries` populated; run reaches `comparing` status.
> 2. Upload `drone_mar_2026.xlsx` (period = `2026-03-01`). Verify **G&A −34%** and **Travel +61%** appear in `anomalies` with correct severity (G&A medium, Travel high).
> 3. Re-upload `drone_mar_2026.xlsx`. Verify DELETE-then-INSERT ran: `SELECT COUNT(*) FROM monthly_entries WHERE company_id=<drone> AND period='2026-03-01'` equals the row count of a fresh parse (no duplicates).
> 4. Run status transitions visible via SQL: `SELECT id, status, step, step_label FROM runs ORDER BY created_at DESC LIMIT 5` shows `pending → parsing → mapping → comparing` for each upload.
> 5. Inject a test file with a column named `SSN` containing SSN-pattern values. Verify the `event="pii_sanitization"` log fires with `columns_dropped=['SSN']` (**no cell values logged**), and Claude's mapping context does not include the SSN column.
> 6. Comparison agent returns a valid `PandasSummary` Pydantic instance — print it, confirm shape matches Day 1's frozen contract. ✅

## Preconditions (from Day 1)

All must be shipped and green before Day 2 starts:

- [x] `domain/entities.py`, `contracts.py` (`PandasSummary` + `NarrativeJSON` shapes frozen), `ports.py` (9 Protocols), `errors.py` (7-exception taxonomy), `run_state_machine.py`
- [x] Supabase schema + RLS + Auth + `demo@dronedemo.com` user + DRONE Inc. row
- [x] Storage bucket `financial-uploads` + RLS policy keyed on `auth.uid()`
- [x] `adapters/supabase_repos.py` with `EntriesRepo`, `AnomaliesRepo`, `RunsRepo`, `CompaniesRepo`, `AccountsRepo`
- [x] `adapters/supabase_storage.py` with 3-attempt retry
- [x] `adapters/anthropic_llm.py` (may still be a stub — Day 2 wires it to Haiku)
- [x] `POST /upload` stores file to Storage and creates `runs` row with `status=pending`
- [x] `tools/pii_sanitizer.py`, `tools/file_reader.py`, `tools/validator.py`
- [x] `backend/messages.py` has keys: `MAPPING_FAILED`, `PARSE_FAILED`, `FILE_HAS_NO_VALID_COLUMNS`
- [x] `logger.py` + `trace_id` contextvar

External pre-requisites:
- `ANTHROPIC_API_KEY` valid and has Haiku quota
- `docs/demo_data/drone_feb_2026.xlsx` and `drone_mar_2026.xlsx` exist and upload cleanly in Bruno

---

## Tasks

### 1. Prompts

- [ ] `backend/prompts/mapping_prompt.txt` — Haiku system prompt for column → US GAAP category mapping.
  - **Input context sent to Claude:** sanitized column headers + 2–3 sample rows (PII already stripped) + aggregated totals (`df.groupby('account')['amount'].sum().to_dict()`)
  - **Output contract:** JSON — `{"mappings": [{"column": str, "category": "REVENUE"|"COGS"|"OPEX"|"G&A"|"R&D"|"OTHER_INCOME"|"OTHER", "confidence": float}]}`
  - Rule in prompt: "Use only the categories listed. If unsure, assign `OTHER` with low confidence. Do not invent categories."
  - **Why file-based:** every prompt is versioned and the git SHA is logged per call (per CLAUDE.md and `scope.md`).
- [ ] `backend/prompts/narrative_prompt.txt` — **scaffold only** (Day 3 finalizes). Empty file with a comment header so the git-SHA logger has a target path.
  - **Why today:** keeps `anthropic_llm.py` path uniform between Haiku (Day 2) and Opus (Day 3).

### 2. LLM Adapter — Wire to Haiku

- [ ] Finalize `adapters/anthropic_llm.py` (was a stub Day 1). Must support:
  - Loading prompt file by name from `backend/prompts/`
  - Logging git SHA of the prompt file per call (use `git hash-object <path>` or read from file metadata)
  - Model dispatched by caller: `claude-haiku-4-5-20251001` for mapping, `claude-opus-4-7` for narrative (Day 3)
  - Network retry only (per CLAUDE.md) — **no semantic retry** (that lives in the Interpreter use case Day 3)
  - Structured output parsing — returns typed Pydantic if schema passed, else raw text
- [ ] Hard-coded model constants at top of `parser.py` and `interpreter.py`:
  ```python
  MAPPING_MODEL = "claude-haiku-4-5-20251001"  # no user toggle in MVP
  ```

### 3. Parser Agent (`agents/parser.py`)

Parser is a **Python orchestrator** that enforces a strict pipeline order. Within that pipeline, exactly one step (column mapping) calls Haiku. The "Anthropic SDK tool-use loop" is scoped to the mapping phase — the rest of the pipeline is deterministic Python.

- [ ] Agent constructor accepts ports via DI (per CLAUDE.md): `FileStorage`, `LLMClient`, `EntriesRepo`, `AccountsRepo`, `RunsRepo`, `CompaniesRepo`
  - **Why:** no direct SDK imports in agents.
- [ ] **Strict pipeline order** (enforced in Python, not the prompt):
  1. **Read file from Storage** — via `FileStorage` port
  2. **Detect format** — via `tools/file_reader.py` (NetSuite 2-byte check)
  3. **Open with correct engine** — openpyxl / xlrd / XML parser
  4. **Skip ERP metadata rows** (first 0–10) — heuristic from `agent-flow.md`
  5. **Detect header row**
  6. **STRIP PII** — via `tools/pii_sanitizer.py`. Drops columns entirely; raises `FileHasNoValidColumns` if nothing survives.
  7. **Pandera validate** — on the sanitized DataFrame only. `amount: float`, `period: date`, `account: str`. Plain-English error via `messages.PARSE_FAILED` on failure.
  8. **Aggregate for mapping context**: `df.groupby('account')['amount'].sum().to_dict()` — reduces a 50,000-row Excel to a 20-key dict. This is what Claude sees, **not raw rows**.
  9. **Call Haiku** via `map_to_accounts` (described below)
  10. **Normalize** — currency symbols, thousand separators, empty rows, blank-space trimming
  11. **DELETE-then-INSERT** — see §4 below
  12. **Write** to `monthly_entries` via `EntriesRepo`, populating **`source_column`** per row with the original header from the uploaded file. This feeds the Day 4 AnomalyCard provenance tooltip (`drone_mar_2026.xlsx — column 'Amount'`). `source_file` is the storage key; `source_column` is the verbatim header.
  13. **Persist confirmed mappings** to `accounts` — same column header from same source auto-maps next month
- [ ] **`map_to_accounts` — Haiku invocation**
  - Build context: sanitized headers + 2–3 sample rows + aggregated totals
  - Send to Haiku via `LLMClient.call(prompt="mapping_prompt.txt", model=MAPPING_MODEL, context=..., schema=MappingOutput)`
  - Parse response into `MappingOutput` Pydantic: `{mappings: [{column, category, confidence}]}`
  - Split mappings by confidence:
    - ≥0.80 → apply silently; persist to `accounts` with `created_by='agent'`
    - <0.80 → populate `runs.low_confidence_columns` JSONB field (see §5); **apply MVP fallback: map to `OTHER`**
  - On Haiku network failure after retries: raise `MappingAmbiguous` → state `parsing_failed`, surface `messages.MAPPING_FAILED`
- [ ] **State transitions via `RunStateMachine.transition()`**:
  - On Parser start: `pending → parsing`
  - After pandera validation succeeds: `parsing → mapping`
  - After Haiku mapping + write completes: `mapping → comparing` (Comparison agent picks up from here — see §7 for background-task handoff)
  - On any unrecoverable failure before `mapping` completes: `→ parsing_failed`
  - On `FileHasNoValidColumns`: `→ parsing_failed` with `error_message = messages.FILE_HAS_NO_VALID_COLUMNS`
- [ ] **Progress fields** on `runs` row updated per transition: `step`, `step_label`, `progress_pct`
  - `parsing`: step=1, label="Reading files...", pct=25
  - `mapping`: step=2, label="Mapping accounts...", pct=50
  - `comparing`: step=3, label="Comparing to history...", pct=75
  - (`generating` / step 4 lives in Day 3)
- [ ] **Error handling** (per CLAUDE.md):
  - `DuplicateEntryError` surfaces immediately — **never retry**. Signals dup-upload (but DELETE-then-INSERT prevents this in practice; a surfaced error means the DELETE skipped or race condition).
  - `TransientIOError` from Storage → `upload_failed` (already handled in adapter)
  - `MappingAmbiguous` → `parsing_failed`
  - `FileHasNoValidColumns` → `parsing_failed`

### 4. Re-Upload Policy — DELETE-then-INSERT

- [ ] Before writing `monthly_entries`, Parser **must** issue:
  ```sql
  DELETE FROM monthly_entries WHERE company_id = :company_id AND period = :period;
  ```
  - **Why (per CLAUDE.md):** leaves zero stale rows from any prior failed run. UPSERT / ON CONFLICT would leak stale rows. This is explicit and auditable.
  - **Why not UPSERT:** stale rows from a prior partial parse could survive with UPSERT but be silently mismatched on a fresh parse.
  - The `UNIQUE(company_id, account_id, period)` constraint stays in place — within a single run it prevents double-insert; across re-uploads the delete-first rule keeps it compatible.
- [ ] Surface this as a repo method: `EntriesRepo.replace_period(company_id, period, entries)` — atomic delete + insert in a single transaction.
- [ ] **Smoke test:** upload `drone_mar_2026.xlsx`, inspect row count. Upload again. Row count unchanged (no duplicates).

### 5. MappingConfirmModal Contract — MVP Fallback

This is a **known design gap**. `design.md` specifies the modal blocks the pipeline until the user confirms; the current state machine in `db-schema.md` has no `awaiting_mapping` status. Resolving the full flow adds a stateful pause/resume that is risky to build on Day 2.

**Decision for MVP: ship the fallback. Escalate to aspirational design post-MVP if time permits Day 5.**

- [ ] **Fallback (ship today):**
  - Low-confidence columns (<0.80) auto-mapped to `OTHER` during parsing
  - `runs.low_confidence_columns` JSONB field populated with: `[{column: str, agent_guess: str, confidence: float}]`
  - Pipeline continues uninterrupted to `comparing`
  - Day 4 frontend surfaces the modal as a **post-hoc review panel** (non-blocking). User correction updates `accounts.category_id` and triggers a fresh run.
  - **Add schema.sql migration:** `ALTER TABLE runs ADD COLUMN low_confidence_columns JSONB DEFAULT '[]'::jsonb;`
- [ ] **Aspirational (only if Day 5 has slack):**
  - Add `awaiting_mapping` to `RunStatus` + allowed transitions: `mapping → awaiting_mapping → mapping → comparing`
  - New endpoint `POST /runs/{run_id}/confirm-mapping` accepting `[{column, category}]`
  - Parser pauses after Haiku call if any low-confidence columns exist
  - Frontend modal blocks until confirmation, then POSTs to resume
  - **Do NOT attempt today.** Flag in `risks.md` as tech debt if shipping the fallback.

### 6. Comparison Agent (`agents/comparison.py`) — pure Python, no Claude

Zero Claude calls. All math is Python.

- [ ] Agent constructor accepts ports: `EntriesRepo`, `AnomaliesRepo`, `RunsRepo`, `AccountsRepo`
- [ ] `get_history(company_id, current_period)` — **standard SQL joins**, NOT pgvector:
  - Query: last 3–6 prior periods of `monthly_entries` for this `company_id`, joined to `accounts` for category context
  - Returns: dict keyed by `account_id` with list of `{period, actual_amount}`
  - **Why SQL not pgvector:** `scope.md` explicitly excludes pgvector from Week 1. SQL joins are sufficient for the 3–6 period lookback.
- [ ] `calculate_variance(current, historical_avg)` — Python formula:
  ```python
  if historical_avg == 0 or historical_avg is None:
      return {"variance_pct": None, "severity": "no_history", "flag": False}
  variance_pct = ((current - historical_avg) / abs(historical_avg)) * 100
  severity = (
      "high"   if abs(variance_pct) > 30 else
      "medium" if abs(variance_pct) > 15 else
      "low"
  )
  return {"variance_pct": round(variance_pct, 2), "severity": severity, "flag": abs(variance_pct) > 15}
  ```
- [ ] **Threshold rules (per `agent-flow.md`):**
  - First 3 months of history: fixed ±20% threshold (limited history regime)
  - After 3+ months: dynamic — outside ±1.5σ of company's own stdev = flag
  - **Day 2 ships the fixed rule.** Dynamic stdev is cut-line — defer to post-MVP if time is tight (document in `risks.md`).
- [ ] No-history case: all baseline entries get `severity="no_history"`, `variance_pct=null`. Write to anomalies anyway so the Interpreter can narrate "no historical comparison available".
  - **Alternative:** skip writing no-history anomalies entirely, let Interpreter query `monthly_entries` directly. Cleaner. **Go with this — only write anomalies where `flag=True` or severity in (low, medium, high)**.
- [ ] `write_anomaly` via `AnomaliesRepo`. Fields: `company_id`, `account_id`, `period`, `anomaly_type='anomaly'` (or `'error'`/`'warning'`), `severity`, `description` (plain-English placeholder — Interpreter rewrites Day 3), `variance_pct`, `status='open'`.
- [ ] **Emit `PandasSummary`** (Pydantic from `domain/contracts.py`, shape frozen Day 1):
  - Build the full summary dict keyed by account
  - Validate through Pydantic before returning (catches shape drift)
  - Return to the background task orchestrator for handoff to Interpreter (Day 3)
- [ ] **State transitions:**
  - On Comparison start: `mapping → comparing` (Parser already transitioned — Comparison confirms it's in `comparing`)
  - On completion: **leave at `comparing`**. Day 3's Interpreter transitions `comparing → generating`.
  - On unrecoverable failure: — no dedicated `comparing_failed` state in the current state machine; use `parsing_failed` or extend the machine. **Day 2 decision:** raise and let the background task handler transition to `parsing_failed` with a plain error message; flag in `risks.md`.
- [ ] **DRONE smoke test data points** (these must come out right):
  - G&A Feb 2026: ~$7.2M → Mar 2026: ~$4.73M → variance ≈ −34% → severity `high` (favorable direction, but severity ladder is absolute)
  - Travel Feb 2026: ~$28K avg → Mar 2026: ~$45K → variance ≈ +61% → severity `high`

### 7. Orchestration — Wire Parser + Comparison to `POST /upload`

Day 1's `POST /upload` returned a `run_id` but didn't kick off the pipeline. Day 2 wires the agents.

- [ ] Modify `POST /upload`:
  - After file is written to Storage + run row created, schedule Parser + Comparison to run **after** response is sent
  - Use **FastAPI `BackgroundTasks`** (per CLAUDE.md — "Do not use Celery. FastAPI background tasks only.")
  - Response returns immediately with `{run_id, status: "processing"}` — user polls `/runs/{run_id}/status` for progress
- [ ] Background task function: `run_parser_then_comparison(run_id, storage_key)`
  - Wrap in top-level `try/except`:
    - On any unhandled exception: log with `trace_id` + `run_id`, transition run to appropriate `*_failed` terminal state with `error_message` populated
  - Call Parser → call Comparison → return
  - Parser and Comparison communicate via Supabase (per `tech-stack.md` — "Supabase is the message bus"). Parser writes `monthly_entries`; Comparison reads them.
- [ ] **Do not** chain Parser → Comparison via direct function call with shared objects. Route through Supabase — this is the architecture invariant.
- [ ] `PandasSummary` is the **one exception** — it's returned in-memory from Comparison so the Day 3 Interpreter (running in the same background task) can consume it without a round-trip. Store it on an in-memory handoff or pass as a return value to the orchestrator.

### 8. Schema Migration

- [ ] `backend/db/schema.sql` — add the `low_confidence_columns` column to `runs`:
  ```sql
  ALTER TABLE runs ADD COLUMN low_confidence_columns JSONB DEFAULT '[]'::jsonb;
  ```
- [ ] Re-run schema against Supabase
- [ ] Update `db-schema.md` to reflect the new field (post-Day-2 doc sync)

### 9. Smoke Tests (sanity, not the full Day 5 test suite)

- [ ] DRONE Feb 2026 → Mar 2026 end-to-end with the real demo files
- [ ] Re-upload DRONE Mar 2026 → verify no duplicates
- [ ] Inject a synthetic file with `SSN` column → verify strip + log + no leak
- [ ] Inject a malformed CSV (non-numeric amount) → verify pandera surfaces plain-English error via `messages.PARSE_FAILED`
- [ ] `RunStateMachine` illegal transition test (e.g. `complete → parsing`) → raises `InvalidRunTransition`

---

## Internal Sequencing

1. **Prompt files (§1)** — `mapping_prompt.txt` + `narrative_prompt.txt` scaffold. No code dependencies.
2. **Wire Haiku in `anthropic_llm.py` (§2)** — blocks Parser §3 step 9.
3. **Schema migration (§8)** — `runs.low_confidence_columns` column. Blocks §5.
4. **Parser skeleton (§3)** with pipeline steps 1–7 (deterministic path, no Haiku yet) — can be tested end-to-end on DRONE Feb 2026 before wiring the Haiku call.
5. **Haiku mapping (§3 step 9)** — wire `map_to_accounts` + confidence split + persistence to `accounts`.
6. **DELETE-then-INSERT (§4)** — `EntriesRepo.replace_period` atomic op. Ship before the first real write.
7. **Orchestration — BackgroundTasks (§7)** — wire `POST /upload` to kick off the Parser. Now upload → parse → (write) flows end-to-end.
8. **Comparison skeleton (§6)** — variance math + severity. Run standalone against seeded data first.
9. **Comparison via orchestrator (§7 chain)** — wire Parser → Comparison in the same background task.
10. **`PandasSummary` emission (§6)** — validate against Day 1's frozen Pydantic shape. This is the Day 3 handoff — if it's wrong, Day 3 breaks.
11. **`RunStateMachine` transitions (§3)** at every step — verify via SQL log.
12. **Smoke tests (§9)** — DRONE Feb → Mar, re-upload, PII injection, pandera error, illegal transition.

Rule of thumb: **wire the deterministic pipeline end-to-end first, then add Haiku, then add Comparison.** If Haiku fails or is slow, the rest of the pipeline is already proven.

---

## Contracts Produced Today

### Parser output (internal — returned from agent to orchestrator)
```python
class ParserOutput(BaseModel):
    run_id: UUID
    rows_parsed: int
    mapped_columns: dict[str, dict]  # {column: {category, confidence}}
    metadata_rows_skipped: int
    pandera_errors: list[str]
    warnings: list[str]
    low_confidence_columns: list[dict]  # mirrors runs.low_confidence_columns
```

### `PandasSummary` emission (from Comparison)
Shape frozen Day 1. Day 2 **proves** the emission matches. Day 3 guardrail depends on this.

### `runs.low_confidence_columns` JSONB shape
```json
[
  {"column": "Misc Acct Adj", "agent_guess": "OTHER_INCOME", "confidence": 0.72},
  {"column": "T&E Reclass",    "agent_guess": "OPEX",         "confidence": 0.68}
]
```

Rendered Day 4 in `MappingConfirmModal` (post-hoc review panel in the MVP fallback).

### `mapping_prompt.txt` output JSON contract
```json
{
  "mappings": [
    {"column": "Revenue",       "category": "REVENUE",      "confidence": 0.95},
    {"column": "Salaries",      "category": "G&A",          "confidence": 0.88},
    {"column": "Misc Acct Adj", "category": "OTHER_INCOME", "confidence": 0.72}
  ]
}
```

### `accounts` table — agent-persisted mappings
After successful mapping, each column header → category pair is written to `accounts`. Next month's upload auto-maps any header already in `accounts` without calling Haiku.

### Background-task orchestration pattern
```
POST /upload → write to Storage → create run (pending) → schedule BG task → return
  (async) BG task: run_parser_then_comparison(run_id, storage_key)
    Parser.run() → state transitions → write monthly_entries
    Comparison.run() → state transition → write anomalies → emit PandasSummary
    (Day 3 will extend this to: Interpreter.run(PandasSummary))
```

This pattern is reused Day 3 for the Interpreter and Day 5 for mail (post-report BackgroundTask per CLAUDE.md).

---

## Cut Line

### Must ship today (non-negotiable)
- Parser happy path on DRONE Feb + Mar 2026: PII → pandera → Haiku → normalize → DELETE-then-INSERT → write
- `RunStateMachine` transitions at each step, visible in `runs` table
- Comparison happy path: variance math + severity (fixed threshold) + `PandasSummary` emission
- Anomalies written with correct severity for G&A and Travel
- Re-upload produces zero duplicates
- Background-task orchestration wired to `POST /upload`
- `mapping_prompt.txt` committed and loaded by `anthropic_llm.py` with git SHA

### Deferrable to Day 3 morning
- Dynamic-stdev severity (after 3+ months history) — ship fixed ±20% threshold for Day 2; `post-MVP` OK
- `narrative_prompt.txt` content — scaffold file is enough today; Day 3 writes it

### Deferrable to Day 5
- Formal PII E2E test covering all blacklist categories (Day 2 ships a smoke test on SSN only)
- Formal re-upload duplicate test (Day 2 ships informal manual verification)
- RLS isolation test between two users (Day 2 ships one-user smoke only)

### Defer to post-MVP
- Aspirational MappingConfirmModal pause/resume (`awaiting_mapping` state + `POST /runs/{run_id}/confirm-mapping`). MVP fallback is the post-hoc review panel.
- Dynamic stdev severity ladder
- Real-data-aware anomaly reasoning (Claude writes the one-sentence business reason Day 3 — keep it stateless on historical context for MVP)
- Agent self-healing on Haiku low-confidence (re-prompt with more context)

---

## Risks (this day)

| Risk | Impact | Mitigation |
|---|---|---|
| PII sanitizer skipped or runs after Haiku | PII values leaked to Anthropic — disqualifying | Pipeline order is hard-coded in Python (not in prompt); Day 5 E2E test catches regression |
| `PandasSummary` shape drifts from Day 1 | Day 3 guardrail has nothing to verify against; full report pipeline breaks | Validate through Pydantic at emission point; unit-test shape against a fixed fixture |
| Haiku rate limits / quota exhaustion | Parser fails in demo; no fallback mapping | Cache prior mappings in `accounts` so re-uploads don't re-call Haiku; add a "basic" fallback that maps everything to `OTHER` with confidence 0.5 if Haiku is unavailable |
| `DELETE-then-INSERT` missed on re-upload | Duplicates (or unique constraint violations) on same `(company_id, account_id, period)` | Ship `EntriesRepo.replace_period()` as the atomic op; manual re-upload smoke test |
| MappingConfirmModal contract gap | Frontend Day 4 has nowhere to render low-confidence columns; user gets `OTHER` mappings without awareness | MVP fallback populates `runs.low_confidence_columns`; `GET /runs/{run_id}/status` (Day 3) exposes it; Day 4 renders post-hoc review panel |
| Background task swallows errors silently | User sees `processing` forever; no error surfaces on `/runs/{run_id}/status` | Top-level `try/except` in BG task; always transition run to a terminal `*_failed` state on unhandled exceptions |
| `no_history` anomalies clutter the report | First-time users see dozens of "no comparison available" entries — design intent is that this is the Empty State | Do NOT write anomalies for `severity=no_history`; Day 4 Empty State screen handles the zero-history case |
| Dynamic stdev complexity seduces | Day 2 scope creep; dynamic math is tricky under time pressure | Explicitly cut to fixed ±20%; document in `risks.md` as post-MVP |
| State machine lacks a `comparing_failed` terminal | No clean failure mode if Comparison crashes mid-run | Use `parsing_failed` as the catch-all terminal for Day 2 pipeline failures; flag in `risks.md` |
| Pandera error messages too technical for users | Users see stack-trace-style errors | Translate in `messages.py`: `PARSE_FAILED = "We couldn't read one of the columns in your file. Please check for non-numeric values or unexpected header rows."` |
| Mid-run crash leaves file in Storage AND partial rows in `monthly_entries` | Dirty state across re-upload | DELETE-then-INSERT handles stale rows; file-in-Storage is intentional on failure (Retry Analysis reuses it, per CLAUDE.md) |

Cross-day risks (tracked in `risks.md`): Haiku quota exhaustion during demo, MappingConfirmModal full-flow post-MVP upgrade, dynamic stdev severity post-MVP.

---

## Reference Docs

Read these before starting Day 2 tasks.

- **`CLAUDE.md`** — Agent Architecture, Critical Files (`pii_sanitizer.py`, pipeline order), Retry & Error Handling (DELETE-then-INSERT rule, `DuplicateEntryError` no-retry), Model Strategy (Haiku hard-coded)
- **`docs/scope.md`** — Zero-friction mapping, PII sanitization pipeline order, Re-upload policy, Two-model pipeline
- **`docs/tech-stack.md`** — Orchestration (three agents, Supabase as message bus), Numeric Guardrail (Day 3 but understand the handoff), File Format Support
- **`docs/agent-flow.md`** — **Agent 1 Parser** (full Step 0–7 pipeline + NetSuite edge case), **Agent 2 Comparison** (variance formula, severity ladder, `PandasSummary` shape)
- **`docs/db-schema.md`** — `monthly_entries` unique constraint + DELETE-then-INSERT rule, `anomalies` fields, `runs` states + progress fields
- **`docs/api.md`** — `GET /runs/{run_id}/status` (Day 3 exposes it; understand the `low_confidence_columns` field today so the contract matches)
- **`docs/design.md`** — `MappingConfirmModal` (trigger, max 3 rows, persistence to `accounts`)
- **`docs/sprint.md`** — Day 2 section (reconciled v3)
