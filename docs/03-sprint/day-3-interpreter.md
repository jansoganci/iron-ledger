# Day 3 — Interpreter Agent + Numeric Guardrail + Full API
*IronLedger 6-Day Sprint — Built with Opus 4.7 Hackathon, April 2026*

## Goal

Interpreter agent produces a plain-English CFO-persona narrative with Claude Opus 4.7. Numeric guardrail verifies every number in the narrative against `PandasSummary` (2% tolerance, 2-attempt retry with reinforced prompt). On success, `reports` row is written, run transitions to `complete`, and Storage file is cleaned up via `BackgroundTask`. On guardrail failure, **no report is written**, file **stays in Storage**, run transitions to `guardrail_failed`. Full API surface is live — `/runs/{id}/status`, `/runs/{id}/raw`, `/report/*`, `/anomalies/*`, `/mail/send` scaffold — all rate-limited, all mapping the exception taxonomy to correct HTTP status codes, all carrying `trace_id`.

## End-of-Day Acceptance Check

> Using the demo user, with DRONE Feb 2026 baseline loaded (from Day 2):
> 1. Upload `drone_mar_2026.xlsx` (period = `2026-03-01`). Poll `GET /runs/{run_id}/status`. Verify status progresses: `pending → parsing → mapping → comparing → generating → complete` with correct `step`, `step_label`, and `progress_pct`.
> 2. After `complete`: `GET /report/<drone_company_id>/2026-03-01` returns a plain-English narrative mentioning G&A and Travel with US-accounting-formatted numbers. Narrative is **verified** — every number in `numbers_used` matched `PandasSummary` within 2%.
> 3. `SELECT * FROM reports WHERE company_id=<drone> AND period='2026-03-01'` shows exactly one row. `runs.report_id` points to it.
> 4. Confirm Storage cleanup ran: Supabase Storage no longer contains `financial-uploads/{uid}/2026-03-01/drone_mar_2026.xlsx` (deleted by BackgroundTask after `complete`).
> 5. **Force a guardrail failure**: edit `narrative_prompt.txt` to inject a number not in `PandasSummary` (e.g. "Revenue rose 200%"). Upload again. Verify: attempt 1 fails, prompt is reinforced, attempt 2 still fails, run transitions to `guardrail_failed`, **no `reports` row written**, **file still in Storage**. `GET /runs/{run_id}/status` returns `guardrail_failed` with `raw_data_url`. `GET /runs/{run_id}/raw` returns the raw pandas summary with a `raw_` file-header prefix.
> 6. `GET /anomalies/<drone>/2026-03-01` returns Travel (+61% high) and G&A (−34% high severity, favorable direction).
> 7. Rate-limit check: fire 10× `POST /upload` in under a minute. 6th request returns 429 with `Retry-After` header and `messages.RATE_LIMITED` body.
> 8. Exception-taxonomy check: request `GET /report/<someone-elses-company>/2026-03-01` — returns 403, not 500.
> 9. CORS smoke: issue a cross-origin preflight from Bruno with `Origin: http://localhost:5173` → 200, correct `Access-Control-Allow-*` headers. ✅

## Preconditions (from Day 1 & Day 2)

All must be shipped and green before Day 3 starts:

From Day 1:
- [x] `domain/` frozen: entities, contracts (`PandasSummary`, `NarrativeJSON`), ports, errors, `run_state_machine`
- [x] `adapters/supabase_repos.py` (all 6 repos), `supabase_storage.py`, `anthropic_llm.py`, `resend_email.py` (scaffold)
- [x] `api/middleware.py` (trace_id), `auth.py` (JWT), `deps.py`, `rate_limit.py` (Limiter + composite key_func)
- [x] `backend/messages.py`, `logger.py`, `settings.py`
- [x] `tools/guardrail.py` — stub from Day 1 OR landing Day 3 for the first time (see §3)
- [x] Supabase schema + RLS + Auth + DRONE Inc., Storage bucket + RLS

From Day 2:
- [x] `agents/parser.py` + `agents/comparison.py` — both green on DRONE Feb + Mar
- [x] `PandasSummary` emission verified against the Day 1 Pydantic shape
- [x] `POST /upload` wired to `BackgroundTasks` running `Parser → Comparison`
- [x] `runs.low_confidence_columns` JSONB column exists
- [x] `accounts` auto-persistence working (same column header auto-maps next run)
- [x] `mapping_prompt.txt` committed + Haiku wired in `anthropic_llm.py`

External pre-requisites:
- `ANTHROPIC_API_KEY` has **Opus quota** (Haiku verified Day 2)
- `FRONTEND_URL` env var set (can be localhost placeholder today; real Vercel URL Day 6)

---

## Tasks

### 1. Prompt — Narrative (Opus)

- [ ] `backend/prompts/narrative_prompt.txt` — CFO-persona report writer. Full content (Day 2 only scaffolded the file).
  - **Input context:** `PandasSummary` (full nested dict) + `Anomaly[]` from Comparison
  - **Output contract:** JSON matching `domain.contracts.NarrativeJSON` — `{narrative: str, numbers_used: list[float]}`
  - **Persona:** "You are a CFO assistant writing a month-end variance commentary for a non-technical finance team."
  - **Hard rules in the prompt** (written verbatim):
    - "Use ONLY the exact numeric values provided in the pandas_summary. Do not round or abbreviate numbers in the `numbers_used` array."
    - "Every number mentioned in `narrative` must also appear in `numbers_used`. The `numbers_used` array is how we verify your output."
    - "Write in plain English. Do not use jargon. Do not use acronyms without explanation."
    - "For each anomaly, write ONE sentence explaining the likely business reason. Do not classify severity — severity is already set."
    - "Report format: start with a one-line summary, then list anomalies ranked by severity (high first), then end with a one-line 'other items within normal range' note."
  - **Do NOT include math:** prompt must never ask Claude to calculate, compare, or derive anything. Numbers come from `PandasSummary` unchanged.
- [ ] Commit `narrative_prompt.txt` — `anthropic_llm.py` logs its git SHA per call.

### 2. Interpreter Agent (`agents/interpreter.py`)

- [ ] Agent constructor accepts ports: `LLMClient`, `ReportsRepo`, `RunsRepo`, `EntriesRepo`, `AnomaliesRepo`, `FileStorage` (for post-success cleanup).
- [ ] Hard-coded model constant at top of file:
  ```python
  NARRATIVE_MODEL = "claude-opus-4-7"  # no user toggle in MVP
  ```
- [ ] **`run(pandas_summary, anomalies, run_id)`** — entry point called by background task (picks up where Day 2's Comparison left off).
- [ ] **State transition on start:** `comparing → generating` via `RunStateMachine.transition()`. Update progress: step=4, label="Generating report...", progress_pct=95.
- [ ] **Wrap the Opus call in `run_with_guardrail()`** (see §3). Do NOT call Opus directly — always go through the guardrail wrapper.
- [ ] **On guardrail success:**
  - Validate output is a `NarrativeJSON` Pydantic instance (catches shape drift)
  - Write `reports` row via `ReportsRepo`: `summary`, `anomaly_count`, `error_count`, `period`, `company_id`
  - Transition run: `generating → complete`, `progress_pct=100`, set `runs.report_id = reports.id`
  - **Schedule Storage cleanup** as FastAPI `BackgroundTask` (see §5) — user response already sent
- [ ] **On guardrail failure** (`GuardrailError` raised after attempt 2):
  - Do **NOT** write to `reports`
  - Transition run: `generating → guardrail_failed`
  - Populate `runs.error_message = messages.GUARDRAIL_FAILED` and `runs.raw_data_url = /runs/{run_id}/raw`
  - File stays in Storage (intentional — Retry Analysis reuses it)
  - **Do NOT raise upward** — the BG task has already handled the failure by transitioning state; frontend polls and sees `guardrail_failed`
- [ ] Anomaly severity is **already set** by Day 2 Comparison. Interpreter does NOT classify severity — it only writes the one-sentence business reason as part of `narrative`.

### 3. Numeric Guardrail (`tools/guardrail.py`) — DO NOT CHANGE after Day 3

This is the heart of the Golden Rule. Every design decision in this file is load-bearing.

- [ ] `flatten_summary(d: dict) -> list[float]` — recursive extraction of all numeric leaf values from a nested dict. Takes `PandasSummary` (or its `.dict()`) and returns every `current`, `historical_avg`, `variance_pct` value.
- [ ] `verify_guardrail(claude_json: dict, pandas_summary: dict, tolerance=0.02) -> tuple[bool, str]`:
  ```python
  def verify_guardrail(claude_json, pandas_summary, tolerance=0.02):
      flat_values = flatten_summary(pandas_summary)
      for num in claude_json["numbers_used"]:
          exists = any(
              abs(num - p_val) / abs(p_val) < tolerance
              for p_val in flat_values
              if p_val != 0
          )
          if not exists:
              return False, f"Mismatch: {num} not found in pandas output"
      return True, "Success"
  ```
  - **Tolerance = 0.02 (2%)** — per CLAUDE.md. Do not raise to 3% as a normal-path fix; raising tolerance is the **demo-day emergency risk mitigation** only.
- [ ] **`run_with_guardrail(pandas_summary, anomalies, max_retries=2)`** — the semantic retry loop:
  ```python
  def run_with_guardrail(pandas_summary, anomalies, max_retries=2):
      for attempt in range(max_retries):
          prompt_variant = "narrative_prompt.txt" if attempt == 0 else "narrative_prompt_reinforced.txt"
          claude_json = llm_client.call(prompt=prompt_variant, model=NARRATIVE_MODEL,
                                         context={"pandas_summary": pandas_summary, "anomalies": anomalies},
                                         schema=NarrativeJSON)
          success, message = verify_guardrail(claude_json.dict(), pandas_summary)
          if success:
              return claude_json
          logger.warning("guardrail_attempt_failed", attempt=attempt+1, reason=message,
                         trace_id=..., run_id=...)
      raise GuardrailError(f"Report could not be verified after {max_retries} attempts. Last mismatch: {message}")
  ```
- [ ] **Reinforced prompt on retry** — `backend/prompts/narrative_prompt_reinforced.txt` contains the base prompt PLUS this suffix appended:
  > "Your previous response contained a number that did not match the source data. Use ONLY the exact values from the pandas_summary provided. Do not round or abbreviate numbers in the numbers_used array. Every number in your narrative prose must be present — to the decimal — in numbers_used."
- [ ] **Semantic retry lives HERE, not in the adapter.** `anthropic_llm.py` retries on network failures only. Guardrail retries on content failures. Two separate concerns.
- [ ] **Claude never receives raw DataFrame rows.** Only the aggregated `PandasSummary` dict.
- [ ] Structured log on each attempt: `event="guardrail_attempt"`, `attempt`, `success`, `mismatch_detail` (no cell values).

### 4. API Endpoints

All endpoints except `/health` require JWT (Day 1). All responses carry `trace_id` header. All rate-limit violations return 429 with `Retry-After` and `messages.RATE_LIMITED`.

#### `GET /runs/{run_id}/status`
- [ ] Handler reads `runs` row via `RunsRepo`, returns:
  ```json
  {
    "run_id": "uuid",
    "status": "parsing|mapping|comparing|generating|complete|upload_failed|parsing_failed|guardrail_failed",
    "step": 1-4,
    "total_steps": 4,
    "step_label": "Reading files...",
    "progress_pct": 0-100,
    "report_id": "uuid | null",
    "error_message": "string | null",
    "raw_data_url": "/runs/{run_id}/raw | null",
    "low_confidence_columns": []
  }
  ```
- [ ] RLS enforces company ownership — if another user's run, returns 403 via `RLSForbiddenError`
- [ ] Rate limit: **120/min per user** (polling endpoint, generous limit)
- [ ] `low_confidence_columns` populated from Day 2's JSONB field — Day 4 frontend renders `MappingConfirmModal` from this

#### `GET /runs/{run_id}/raw`
- [ ] **guardrail_failed runs ONLY** — return 404 if run status is anything else
- [ ] Returns the raw `PandasSummary` as a downloadable text file
- [ ] Filename header: `raw_{period}_{run_id_short}.txt` — the `raw_` prefix is a **visual trust signal** per `design.md`
- [ ] File content starts with an unverified banner:
  ```
  === IronLedger Raw Data — UNVERIFIED ===
  Run ID: {run_id}
  Period: {period}
  Company: {company_name}
  Generated: {timestamp}
  
  This data was NOT verified by the numeric guardrail.
  The automated report could not be produced. See /report for verified reports only.
  ===
  ```
- [ ] Followed by the flat `PandasSummary` dump as human-readable text (not JSON — judges and users can read it)
- [ ] Rate limit: **60/min per user**

#### `GET /report/{company_id}/{period}`
- [ ] **Verified reports only** — 404 if none. Never serve a guardrail_failed or partial report from this endpoint.
- [ ] Returns:
  ```json
  {
    "report_id": "uuid",
    "company_id": "uuid",
    "period": "2026-03-01",
    "generated_at": "2026-03-15T14:32:00Z",
    "summary": "March 2026 shows two items...",
    "anomaly_count": 2,
    "error_count": 0,
    "anomalies": [
      {
        "account": "Travel & Entertainment",
        "severity": "high",
        "direction": "unfavorable",
        "current": 45000,
        "historical_avg": 28000,
        "variance_pct": 60.7,
        "description": "Travel expense is 61% above the 3-period average."
      }
    ]
  }
  ```
- [ ] Authorization: verify JWT resolves to the `company_id` in the URL, else 403
- [ ] Rate limit: **60/min per user**
- [ ] **Note on `company_id` in URL:** `api.md` puts `company_id` in the path for convenience, but the value is cross-checked against the JWT-resolved company. Client-supplied `company_id` is never trusted.

#### `GET /anomalies/{company_id}/{period}`
- [ ] Returns:
  ```json
  {
    "company_id": "uuid",
    "period": "2026-03-01",
    "anomalies": [
      { "id": "uuid", "account": "Travel & Entertainment", "severity": "high",
        "variance_pct": 60.7, "status": "open", "direction": "unfavorable" }
    ]
  }
  ```
- [ ] Same RLS check as `/report`
- [ ] Rate limit: **60/min per user**

#### `POST /mail/send` — scaffold only (Day 5 wires fully)
- [ ] Accepts `{report_id: UUID, to_email: string}`
- [ ] Returns a placeholder `{status: "scaffolded", message: "Day 5 will wire Resend"}` for now
- [ ] Rate limit: **10/hour per user** — set today, works even though underlying call isn't wired
- [ ] Day 5 will add: Resend call, mark `reports.mail_sent=true`, success/error response mapping

### 5. Post-Success Storage Cleanup (BackgroundTask)

- [ ] Triggered **only** by the Interpreter on the `generating → complete` transition, after the `reports` row write succeeds
- [ ] Runs in a FastAPI `BackgroundTask` — response is sent first, cleanup happens after
- [ ] Top-level `try/except Exception` wrapper around the cleanup:
  - On success: log `event="storage_cleanup_success"` with `trace_id`, `run_id`, `storage_key`
  - On failure: log at **WARNING** with `trace_id`, `run_id`, `storage_key`, and the adapter's error. **Do NOT raise.** Run stays `complete`.
- [ ] **On `guardrail_failed`: do NOT schedule cleanup.** File stays in Storage so Retry Analysis (Day 4) can reuse it without re-upload.
- [ ] Post-MVP: TTL sweep for abandoned `guardrail_failed` runs — tracked in `risks.md`, not built today.

### 6. HTTP Status Mapping for Exception Taxonomy

Centralized exception handler in FastAPI — every domain exception maps to a correct HTTP status with a user-facing message from `messages.py`.

- [ ] Register a global exception handler in `main.py`:
  ```python
  @app.exception_handler(TransientIOError)         # 503
  @app.exception_handler(DuplicateEntryError)      # 409
  @app.exception_handler(RLSForbiddenError)        # 403
  @app.exception_handler(InvalidRunTransition)     # 500 (programmer error)
  @app.exception_handler(FileHasNoValidColumns)    # 422 — surfaces as messages.FILE_HAS_NO_VALID_COLUMNS
  @app.exception_handler(MappingAmbiguous)         # 422 — surfaces as messages.MAPPING_FAILED
  ```
- [ ] `GuardrailError` is **NOT** surfaced as an HTTP error. It transitions the run to `guardrail_failed` and the status polling endpoint reports it (per CLAUDE.md — "surfaces as `guardrail_failed` run status, not a 5xx").
- [ ] Authentication failures:
  - Missing/invalid JWT → 401 `messages.UNAUTHORIZED`
  - Valid JWT but wrong company → 403 `messages.FORBIDDEN`
- [ ] Every error response includes `trace_id` in both the header (from middleware) and the JSON body:
  ```json
  {"error": "guardrail_failed", "message": "...", "trace_id": "uuid"}
  ```
- [ ] **Never leak stack traces or technical language to users.** All user-facing strings come from `messages.py`.

### 7. Rate Limits — Apply to Endpoints

Day 1 shipped the `Limiter` + composite `key_func`. Day 3 decorates every endpoint.

- [ ] `POST /upload`: 5/min per user, 20/hour per user, 10/min per IP fallback
- [ ] `GET /runs/{run_id}/status`: 120/min per user
- [ ] `GET /runs/{run_id}/raw`: 60/min per user
- [ ] `GET /report/{company_id}/{period}`: 60/min per user
- [ ] `GET /anomalies/{company_id}/{period}`: 60/min per user
- [ ] `POST /mail/send`: 10/hour per user
- [ ] `GET /health`: **uncapped** (no rate limit, no auth)
- [ ] 429 response shape: `{"error": "rate_limited", "message": <messages.RATE_LIMITED>, "retry_after_seconds": <int>}` + `Retry-After` HTTP header
- [ ] **Test harness:** a smoke script that fires 10× `/upload` in 30s, expects 5× success then 5× 429

### 8. CORS Verification (first real test)

Day 1 configured CORS. Day 3 proves it works cross-origin.

- [ ] From Bruno (or `curl`), issue an `OPTIONS` preflight with `Origin: http://localhost:5173`:
  ```bash
  curl -X OPTIONS http://localhost:8000/upload \
    -H "Origin: http://localhost:5173" \
    -H "Access-Control-Request-Method: POST" \
    -H "Access-Control-Request-Headers: authorization,content-type" -v
  ```
- [ ] Expect 200 + `Access-Control-Allow-Origin: http://localhost:5173`, `Access-Control-Allow-Headers: authorization, content-type, ...`, `Access-Control-Allow-Methods: POST, GET, OPTIONS, ...`
- [ ] Repeat with an unauthorized origin (e.g. `Origin: http://evil.example`) — expect no `Allow-Origin` header
- [ ] **Why today:** per `api.md` — "Forgetting CORS will cause silent failures on Day 4 frontend integration." Catching this Day 3 prevents wasted Day 4 debugging.

### 9. Integration Smoke Tests

- [ ] DRONE Mar 2026 full pipeline: `POST /upload` → poll `/status` → `complete` → `GET /report/.../2026-03-01` returns narrative with G&A (−34%) and Travel (+61%) mentioned
- [ ] Force guardrail failure: swap `narrative_prompt.txt` with a prompt that instructs Claude to say "Revenue rose 200%" (number not in summary). Verify `guardrail_failed`, file preserved, `/runs/{id}/raw` serves unverified dump.
- [ ] Rate limit: 6th `/upload` in a minute returns 429 with `Retry-After`
- [ ] RLS: second user's JWT cannot read DRONE's report — `GET /report/<drone_company_id>/2026-03-01` returns 403
- [ ] Invalid state transition: manually insert `runs` row with `status=complete`, try to transition to `parsing` — `InvalidRunTransition` raised, returns 500
- [ ] Storage cleanup: verify file deleted after `complete`, preserved after `guardrail_failed`

---

## Internal Sequencing

1. **Prompt — `narrative_prompt.txt` (§1)** — content first so Day-2 stub file is fully populated. No code dependencies.
2. **`narrative_prompt_reinforced.txt` (§3)** — the retry-variant prompt file. Commit alongside the base prompt.
3. **`tools/guardrail.py` (§3)** — `flatten_summary` + `verify_guardrail` + `run_with_guardrail`. Unit-test in isolation against fixtures (hard-coded `PandasSummary` + hard-coded `NarrativeJSON` with known mismatches).
4. **`agents/interpreter.py` (§2)** — depends on guardrail and on Opus wiring in `anthropic_llm.py`.
5. **Opus wiring in `anthropic_llm.py`** — extend Day 2's Haiku support to dispatch Opus model. Same adapter, same prompt loader, same git-SHA logging.
6. **Extend Day 2 BG task** — after `Comparison`, call `Interpreter.run(pandas_summary, anomalies)`. The orchestrator now runs `Parser → Comparison → Interpreter` end-to-end.
7. **HTTP status handlers (§6)** — register in `main.py`. Test with synthetic raises.
8. **Rate-limit decorators (§7)** — decorate every endpoint. Test with smoke script.
9. **API endpoints (§4)** — `GET /runs/{id}/status` first (blocks §2 verification since no way to observe pipeline progress without it), then `/raw`, `/report`, `/anomalies`, `/mail/send` scaffold.
10. **Storage cleanup BackgroundTask (§5)** — wire after Interpreter's `complete` transition. Verify deletion + preservation-on-fail.
11. **CORS verification (§8)** — first cross-origin test, before Day 4.
12. **Integration smoke tests (§9)** — full pipeline, happy + guardrail-failed + rate-limited + RLS paths.

Rule of thumb: **guardrail before Interpreter, Interpreter before orchestration, orchestration before endpoints.** If the guardrail is wrong, the entire report pipeline is untrustworthy — so build and test it in isolation first.

---

## Contracts Produced Today

### `NarrativeJSON` — Opus's structured output (shape frozen Day 1)

```python
class NarrativeJSON(BaseModel):
    narrative: str
    numbers_used: list[float]
```

Validated at emission. Guardrail verifies `numbers_used` against `PandasSummary` flat values.

### Guardrail retry pattern
```
run_with_guardrail(pandas_summary, anomalies, max_retries=2)
  attempt 1: prompt=narrative_prompt.txt → verify → fail? → retry
  attempt 2: prompt=narrative_prompt_reinforced.txt → verify → fail? → GuardrailError
```

Semantic retry only. Network retry stays in the adapter. **Two-attempt total — do not extend.**

### `GET /runs/{run_id}/status` response
```json
{
  "run_id": "uuid",
  "status": "...",
  "step": 1-4, "total_steps": 4,
  "step_label": "...",
  "progress_pct": 0-100,
  "report_id": "uuid|null",
  "error_message": "string|null",
  "raw_data_url": "/runs/{run_id}/raw|null",
  "low_confidence_columns": [{"column": str, "agent_guess": str, "confidence": float}]
}
```

Day 4 `LoadingProgress` polls this. Day 4 `MappingConfirmModal` renders from `low_confidence_columns`. Day 4 `GuardrailWarning` triggers on `status=guardrail_failed`.

### `GET /runs/{run_id}/raw` contract
- **guardrail_failed only.** 404 for any other status.
- Text file. `Content-Type: text/plain; charset=utf-8`
- Filename: `raw_{period}_{run_id_short}.txt`
- Content: unverified banner header + flat `PandasSummary` dump

### `GET /report/{company_id}/{period}` response
Shape per `api.md` §3. **Verified reports only — never returns a `guardrail_failed` placeholder.**

### `GET /anomalies/{company_id}/{period}` response
Shape per `api.md` §4.

### `POST /mail/send` scaffold
- Input: `{report_id, to_email}` — validated shape today
- Output: placeholder `{status: "scaffolded"}` today; Day 5 returns real `{status: "sent", message_id}`

### HTTP status code mapping
| Exception | Status | User-facing string |
|---|---|---|
| `TransientIOError` | 503 | retry-later message |
| `DuplicateEntryError` | 409 | duplicate-upload message |
| `RLSForbiddenError` | 403 | `messages.FORBIDDEN` |
| `FileHasNoValidColumns` | 422 | `messages.FILE_HAS_NO_VALID_COLUMNS` |
| `MappingAmbiguous` | 422 | `messages.MAPPING_FAILED` |
| `InvalidRunTransition` | 500 | generic "unexpected error" |
| `GuardrailError` | **not HTTP** | surfaced via `runs.status=guardrail_failed` |
| Unauthorized (no/bad JWT) | 401 | `messages.UNAUTHORIZED` |
| JWT valid, wrong company | 403 | `messages.FORBIDDEN` |
| Rate limit exceeded | 429 | `messages.RATE_LIMITED` + `Retry-After` header |

### Storage cleanup pattern (BackgroundTask)
```
On complete: schedule cleanup → log success/WARNING → never raise
On guardrail_failed: do NOT schedule cleanup
```

Reused by any future post-success side-effects (e.g. email indexing, audit log writes).

### Orchestration (full pipeline end-to-end)
```
POST /upload
  → write file to Storage → create run (pending) → schedule BG task → return {run_id}
BG task:
  Parser.run()       # parsing → mapping
  Comparison.run()   # mapping → comparing
  Interpreter.run()  # comparing → generating → complete OR guardrail_failed
  Storage cleanup (only on complete, as nested BackgroundTask)
```

---

## Cut Line

### Must ship today (non-negotiable)
- `narrative_prompt.txt` + `narrative_prompt_reinforced.txt`
- `tools/guardrail.py` with 2-attempt `run_with_guardrail`
- `agents/interpreter.py` wired Opus via `anthropic_llm.py`
- End-to-end pipeline: `Parser → Comparison → Interpreter → reports row`
- `GET /runs/{run_id}/status` (blocks Day 4 polling)
- `GET /report/{company_id}/{period}` (verified only)
- `GET /anomalies/{company_id}/{period}`
- HTTP status mapping for the full exception taxonomy
- Rate-limit decorators on every endpoint
- Storage cleanup BackgroundTask on `complete`
- `GET /runs/{run_id}/raw` for `guardrail_failed` runs
- CORS verified cross-origin

### Deferrable to Day 4
- Rate-limit smoke test script (can be Bruno collection on Day 4)
- Advanced guardrail failure cases (e.g. multiple mismatches in one response) — the core 2-attempt flow ships today

### Deferrable to Day 5
- `POST /mail/send` real wiring (scaffold today)
- Formal guardrail failure test with injected bad prompt (smoke test today, formal test Day 5)
- Formal RLS isolation test (smoke Day 3, formal Day 5)

### Defer to post-MVP
- TTL sweep for abandoned `guardrail_failed` runs (Storage leak mitigation) — logged as tech debt in `risks.md`
- Configurable guardrail tolerance per company (hard-coded 2% is fine for MVP)
- Guardrail attempt history persisted to a table for audit (logs are enough for MVP)
- Per-attempt prompt diff visualization (debugging aid, not demo-critical)

---

## Risks (this day)

| Risk | Impact | Mitigation |
|---|---|---|
| Guardrail too strict — fires on legitimate rounding | Demo pipeline fails live; judges see `guardrail_failed` instead of verified report | Hard rule: prompt forbids rounding in `numbers_used`. 2% tolerance gives headroom for float precision. Demo-day emergency lever: raise tolerance to 3% (documented as risk-mitigation only, not normal path) |
| Opus latency doubles on retry | Demo hits 20–30s wait on first failure + retry | Pre-warm with a cached run Day 6 for the live demo; also keep Loom backup |
| Semantic retry leaks into adapter | Adapter retries on content failures → infinite loop if network flaps during a guardrail fail | Clear separation: `anthropic_llm.py` retries ONLY on network/5xx, never on content. Document with a comment in the adapter. |
| `narrative_prompt.txt` or reinforced prompt drift causes chronic failures | Demo guardrail fires every time | Pin prompts end of Day 3; any edit requires re-running integration smoke test |
| Storage cleanup runs on `guardrail_failed` | Retry Analysis (Day 4) breaks — file gone | Hard rule in Interpreter: cleanup scheduled **only on `complete` transition**, not `guardrail_failed` |
| Storage cleanup failure raises uncaught | BG task crashes, logs swallowed, run stays `complete` but looks like orphaned infra | Top-level `try/except Exception` in BG cleanup; log at WARNING, swallow |
| Rate limit too aggressive | Frontend polling hits 429 during normal usage | 120/min for `/status` is generous (2/sec — more than enough for a 1-2sec poll interval) |
| CORS misconfigured, caught Day 3 not Day 1 | Wasted Day 1/2 time not noticing — but caught before Day 4 | Explicit preflight test in §8; test with both allowed and disallowed origin |
| `InvalidRunTransition` surfaces as 500 in user-visible error | Looks like a backend crash | `messages.py` key for `InvalidRunTransition` is generic "unexpected error — please retry". Log with full stack for debugging. |
| Guardrail verifies against flat list, loses context | Number in narrative matches an unrelated summary value by coincidence | 2% tolerance is small; chance of coincidence is low. Post-MVP: keyed verification (e.g. "Travel variance must match pandas Travel variance, not G&A") |
| `GET /report` exposes reports from other companies | Data leak | JWT→company_id resolution + URL `company_id` cross-check + RLS on `reports` table = three layers of defense |
| Exception handler order matters | Generic handler catches before specific one | Register most-specific exception handlers first in `main.py` |

Cross-day risks (tracked in `risks.md`): Opus quota exhaustion during demo, Storage leak mitigation post-MVP, MappingConfirmModal full pause/resume post-MVP.

---

## Reference Docs

Read these before starting Day 3 tasks.

- **`CLAUDE.md`** — Critical Files (`guardrail.py` — DO NOT CHANGE), Retry & Error Handling (adapter-owns-IO vs use-case-owns-semantic, storage cleanup), Model Strategy (Opus hard-coded)
- **`docs/scope.md`** — Numeric guardrail: 2 attempts (original + 1 retry with reinforced prompt), second failure → `guardrail_failed`, raw pandas summary downloadable, Retry Analysis starts fresh `run_id` reusing stored file
- **`docs/tech-stack.md`** — Numeric Guardrail section (code snippet), Orchestration (three agents, Supabase as message bus)
- **`docs/agent-flow.md`** — **Agent 3 Interpretation** (input/output/guardrail flow), **Numeric Guardrail** (flatten_summary + verify_guardrail + run_with_guardrail code), reinforced prompt exact wording, Error Handling table
- **`docs/db-schema.md`** — `reports` table fields, `runs.status` terminal states, `runs.raw_data_url` field
- **`docs/api.md`** — **every endpoint** (Authentication, `/upload`, `/runs/{id}/status`, `/report`, `/anomalies`, `/mail/send`, Error Codes Reference, CORS Configuration)
- **`docs/design.md`** — GuardrailWarning screen (3b) behavior (shapes the Day 4 UI; Day 3 backend must match), Verified badge / unverified raw download distinction
- **`docs/sprint.md`** — Day 3 section (reconciled v3)
