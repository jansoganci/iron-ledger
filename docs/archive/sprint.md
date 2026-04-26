# Month Proof — 6-Day Sprint
*Built with Opus 4.7 Hackathon — April 2026*
*v3 — reconciled with CLAUDE.md, scope.md, tech-stack.md, agent-flow.md, db-schema.md, api.md, design.md*

---

## Overall Strategy

- **Day 1:** Backend foundation — Clean Architecture scaffold, Supabase + Auth + Storage, infrastructure (logger, rate limiter, messages), file reading
- **Day 2:** Parser agent (PII + Haiku mapping) + Comparison agent (pure Python)
- **Day 3:** Interpreter agent + Numeric guardrail + full API surface
- **Day 4:** Frontend — Login, upload UI, report view, all component states
- **Day 5:** Mail + E2E tests + polish
- **Day 6:** Demo prep + deploy + submit

**Rule:** At the end of each day, something working must be delivered. Incomplete work should not spill into the next day.

**Rule:** Claude must never do math. All calculations are in Python.

**Rule:** Prompts are never inline. They live in `backend/prompts/` and the git SHA is logged per call.

**Rule:** PII never reaches Anthropic. `tools/pii_sanitizer.py` runs before pandera and before any Claude call.

---

## Day 1 — Backend Foundation

**Goal:** FastAPI running with Clean Architecture, Supabase connected (schema + RLS + Auth + Storage), infrastructure in place (logger, rate limiter, messages), DRONE Excel readable.

### Clean Architecture Scaffold
- [x] Create folder structure: `backend/{domain,adapters,agents,api,tools,prompts,db}/`
- [x] `backend/main.py` — app factory, CORS, middleware, lifespan, router include
- [x] `backend/settings.py` — Pydantic `BaseSettings` reading `.env`
- [x] `backend/messages.py` — single source of truth for every user-facing error string (reference `scope.md` / `agent-flow.md` for required keys, incl. `FILE_HAS_NO_VALID_COLUMNS`, `RATE_LIMITED`)
- [x] `backend/logger.py` — JSON log formatter + `trace_id` contextvar
- [x] Install dependencies: `fastapi`, `uvicorn`, `pandas`, `openpyxl`, `xlrd`, `pandera`, `pydantic`, `supabase`, `anthropic`, `resend`, `slowapi==0.1.9`, `python-multipart`

### Domain Layer (pure Python, no I/O)
- [x] `domain/entities.py` — dataclasses: `Company`, `Account`, `MonthlyEntry`, `Anomaly`, `Report`, `Run`
- [x] `domain/contracts.py` — Pydantic models `PandasSummary` and `NarrativeJSON` (cross-agent contracts)
- [x] `domain/ports.py` — Protocols: `EntriesRepo`, `AnomaliesRepo`, `ReportsRepo`, `RunsRepo`, `CompaniesRepo`, `AccountsRepo`, `FileStorage`, `LLMClient`, `EmailSender`
- [x] `domain/errors.py` — `TransientIOError`, `DuplicateEntryError`, `RLSForbiddenError`, `GuardrailError`, `InvalidRunTransition`, `FileHasNoValidColumns`, `MappingAmbiguous`
- [x] `domain/run_state_machine.py` — `RunStatus` enum + allowed transitions + `RunStateMachine.transition()` that raises `InvalidRunTransition`
  - Happy path: `pending → parsing → mapping → comparing → generating → complete`
  - Terminal failure: `upload_failed`, `parsing_failed`, `guardrail_failed`

### Supabase — Schema + Auth + Storage
- [ ] Create Supabase project, configure `.env` (`SUPABASE_URL`, `SUPABASE_SERVICE_KEY`)
- [ ] `backend/db/schema.sql` — **7 tables**: `companies`, `account_categories`, `accounts`, `monthly_entries`, `anomalies`, `reports`, `runs`
  - Seed `account_categories` (REVENUE, COGS, OPEX, G&A, R&D, OTHER_INCOME)
  - Unique constraint on `monthly_entries(company_id, account_id, period)`
  - Indexes on `(company_id, period)` for entries, anomalies, runs
- [ ] **RLS policies** on every company-owning table via EXISTS-through-`companies` (`owner_id = auth.uid()`). `account_categories` is public, no RLS.
- [ ] Enable Supabase Auth (email + password). Create demo user `demo@dronedemo.com`
- [ ] Insert DRONE Inc. row with `owner_id = demo_user_id`
- [ ] Create Supabase Storage bucket `financial-uploads`
- [ ] Storage RLS policy: `(storage.foldername(name))[1] = auth.uid()::text`
- [ ] Folder layout: `financial-uploads/{auth.uid()}/{period}/{filename}`

### Adapters (I/O implementations of ports)
- [ ] `adapters/supabase_repos.py` — all 6 repo implementations share one Supabase client. Hybrid return-type policy: `MonthlyEntry`, `Anomaly`, `Report` return dataclasses; `Company`, `Account`, `Run` return dicts.
- [ ] `adapters/supabase_storage.py` — `FileStorage` port. Upload retry: 3 attempts, backoff 0.5s → 1.5s → 4s with ±20% jitter, retry only on network-class errors. After 3 failures raise `TransientIOError`.
- [ ] `adapters/anthropic_llm.py` — `LLMClient` port. Loads prompts by filename from `prompts/`, logs git SHA per call. Network retry only; no semantic retry here.
- [ ] `adapters/resend_email.py` — `EmailSender` port (scaffold; wired up Day 5)

### API Layer
- [ ] `api/middleware.py` — generates/reads `trace_id`, stamps into contextvar, adds to every response header
- [ ] `api/auth.py` — JWT validation dependency. `Authorization: Bearer <supabase_jwt>` → `user_id` → `company_id` via `companies.owner_id`. Never accept `company_id` from client.
- [ ] `api/deps.py` — builds adapters once, injects into agents via FastAPI `Depends`
- [ ] `api/rate_limit.py` — slowapi `Limiter` + composite `key_func` (`user_id` if JWT present, else IP). In-memory backend. 429 returns `Retry-After` + `messages.RATE_LIMITED`.
- [ ] `api/routes.py` — router skeleton
- [ ] CORS config: `http://localhost:5173` + `FRONTEND_URL` env var *(forgetting this causes silent failures on Day 4)*
- [ ] `GET /health` — returns `{"status":"ok"}`, uncapped
- [ ] `POST /upload` endpoint — multipart: `files[]` + `period`. Writes file to Supabase Storage under `{auth.uid()}/{period}/{filename}`. Creates `runs` row with `status=pending`. Returns `{run_id, status, files_received}`. Rate limit: 5/min per user, 20/hour; 10/min per IP fallback.

### Tools
- [ ] `tools/file_reader.py` — pandas + openpyxl + xlrd. NetSuite edge case: detect by reading first 2 bytes (`b"<?"` → XML Spreadsheet 2003, else binary xls).
- [ ] Format detection: `.xlsx`, `.csv`, `.xls` (both flavors), `.xlsm`
- [ ] `tools/pii_sanitizer.py` — header blacklist (case-insensitive substring match: SSN, tax ID, DOB, personal name, home address, bank account/routing, personal contact). SSN value-level regex `^\d{3}-?\d{2}-?\d{4}$`, drop column if ≥20% match. Emits `event="pii_sanitization"` log with column names and counts — **never cell values**. Raises `FileHasNoValidColumns` if nothing survives.
- [ ] `tools/validator.py` — pandera schema: `amount: float`, `period: date`, `account: str`

### End-of-day check
> When DRONE Excel is uploaded via Bruno (with a valid JWT), is a `runs` row created in `pending`, the file stored under `financial-uploads/{uid}/{period}/`, and a clean DataFrame printed to the terminal? ✅

---

## Day 2 — Parser Agent + Comparison Agent

**Goal:** Parser reads DRONE files, maps columns to US GAAP with Haiku, writes to `monthly_entries`. Comparison calculates variances in pure Python and writes to `anomalies`. `PandasSummary` is emitted as the handoff to Day 3.

### Parser Agent (`agents/parser.py`)
- [ ] Anthropic SDK tool-use loop (~50 lines, no LangChain)
- [ ] Use `claude-haiku-4-5-20251001` for column mapping (hard-coded, no toggle)
- [ ] Pipeline order (strict): `read → skip metadata → detect header → STRIP PII → pandera validate → column map (Haiku) → normalize → write`
- [ ] `detect_format` tool
- [ ] `read_file` tool — skip 0–10 ERP metadata rows, detect header row
- [ ] **Invoke `pii_sanitizer.py`** — drops columns entirely (no hashing) before any downstream step
- [ ] pandera validate on the sanitized DataFrame — plain-English error surfaced to user on failure
- [ ] `map_to_accounts` tool (Haiku)
  - Input to Claude: sanitized column headers + 2–3 sample rows (no PII) + aggregated account totals (`df.groupby('account')['amount'].sum().to_dict()`)
  - Mapping confidence ≥80% → accepted silently
  - Mapping confidence <80% → surface via run state / status endpoint for `MappingConfirmModal` (max 3 flagged columns shown at once)
  - Persist confirmed mappings to `accounts` so same column header auto-maps next month
- [ ] `normalize_data` tool — currency symbols, thousand separators, empty rows
- [ ] **Re-upload policy:** before writing, `DELETE FROM monthly_entries WHERE company_id=? AND period=?`. Do NOT use UPSERT / ON CONFLICT.
- [ ] `write_entries` — writes to `monthly_entries` via `EntriesRepo`. `DuplicateEntryError` surfaces immediately (never retry).
- [ ] Transition run status via `RunStateMachine`: `pending → parsing → mapping`
- [ ] On `FileHasNoValidColumns` → transition to `parsing_failed`, surface `messages.FILE_HAS_NO_VALID_COLUMNS`

### Comparison Agent (`agents/comparison.py`) — pure Python, no Claude
- [ ] `get_history` — fetch prior periods via `EntriesRepo` (standard SQL joins, **not pgvector**)
- [ ] `calculate_variance` in Python:
  ```python
  variance_pct = ((current - historical_avg) / abs(historical_avg)) * 100
  ```
- [ ] Severity thresholds: `low` <15%, `medium` ≥15%, `high` ≥30%. First 3 months use ±20% fixed; 3+ months use company's own stdev.
- [ ] Handle no-history case: `flag="no_history"`, skip comparison cleanly
- [ ] `write_anomaly` via `AnomaliesRepo`
- [ ] **Emit `PandasSummary`** (Pydantic model from `domain/contracts.py`) as the handoff to the Interpreter. This is the strict contract.
- [ ] Transition run status: `mapping → comparing`
- [ ] DRONE Mar 2026 vs Feb 2026 smoke test: G&A −34% and Travel +61% should appear in `anomalies`

### End-of-day check
> After uploading DRONE Mar/Feb Excel, are G&A and Travel entries in `anomalies` with correct severity, and does the Comparison agent return a valid `PandasSummary`? ✅

---

## Day 3 — Interpretation Agent + Numeric Guardrail + Full API

**Goal:** Plain-language English report generated with Claude Opus 4.7, numeric guardrail verifies it (2 attempts), full API surface live.

### Interpreter Agent (`agents/interpreter.py`)
- [ ] Use `claude-opus-4-7` for narrative + anomaly reasons (hard-coded, no toggle)
- [ ] `prompts/narrative_prompt.txt` — CFO-persona report writer. Must return JSON matching `NarrativeJSON`: `{narrative, numbers_used[]}`
- [ ] Input: `PandasSummary` + `Anomaly[]` (from Comparison)
- [ ] Claude never receives raw DataFrame rows — only the aggregated summary
- [ ] Anomaly severity (low/medium/high) already set by Comparison — Claude does NOT classify severity, only writes the one-sentence business reason
- [ ] Transition run status: `comparing → generating`

### Numeric Guardrail (`tools/guardrail.py` — DO NOT CHANGE after Day 3)
- [ ] `flatten_summary(d)` — recursive extract of all numeric leaves from nested dict
- [ ] `verify_guardrail(claude_json, pandas_summary, tolerance=0.02)` — returns `(bool, message)`
- [ ] `run_with_guardrail(pandas_summary, max_retries=2)`:
  - Attempt 1: call Claude, verify
  - On failure: retry with **reinforced prompt suffix** ("Your previous response contained a number that did not match the source data. Use ONLY the exact values from the pandas_summary provided. Do not round or abbreviate numbers in the numbers_used array.")
  - Attempt 2 also fails → raise `GuardrailError`
- [ ] On `GuardrailError`: transition run to `guardrail_failed`. **File stays in Supabase Storage** (not cleaned up). Do NOT write to `reports`.
- [ ] On success: write verified report via `ReportsRepo`, transition run to `complete`, schedule storage cleanup as `BackgroundTask`.
- [ ] Storage cleanup failures: log at WARNING with `trace_id`, `run_id`, `storage_key`, swallow. Run stays `complete`.

### API Endpoints (`api/routes.py`)
- [ ] `GET /runs/{run_id}/status` — polling endpoint for progress bar. Returns `{run_id, status, step, total_steps, step_label, progress_pct, report_id?, error_message?, raw_data_url?, low_confidence_columns?}`. Rate limit: 120/min per user.
- [ ] `GET /runs/{run_id}/raw` — raw pandas summary download, **guardrail_failed runs only**. Output labeled unverified (file header starts with `raw_`).
- [ ] `GET /report/{company_id}/{period}` — verified report only. 404 if none. Rate limit: 60/min.
- [ ] `GET /anomalies/{company_id}/{period}` — anomaly list. Rate limit: 60/min.
- [ ] `POST /mail/send` — scaffold endpoint (fully wired Day 5). Rate limit: 10/hour.
- [ ] HTTP status mapping for exception taxonomy:
  - `TransientIOError` → 503
  - `DuplicateEntryError` → 409
  - `RLSForbiddenError` → 403
  - `GuardrailError` → surfaced via `status=guardrail_failed` on the run (not a 5xx)
  - `InvalidRunTransition` → 500 (programmer error)
  - Unauthorized → 401, Forbidden (wrong company) → 403
- [ ] Every response carries the `trace_id` from middleware

### End-of-day check
> DRONE Mar 2026 full pipeline runs end-to-end from `POST /upload`: report row exists in `reports`, guardrail passed, run status = `complete`, `GET /runs/{run_id}/status` returns progress, `GET /report/.../...` returns the verified narrative. Storage file has been cleaned up. ✅

---

## Day 4 — Frontend

**Goal:** Browser flow works end-to-end. Login → upload → progress → verified report (with Verified badge + provenance) → email. All specified component states implemented.

### Project Setup
- [ ] React + TypeScript + Vite
- [ ] shadcn/ui (Radix + Tailwind) — set palette + typography tokens in `tailwind.config`; do NOT heavily theme shadcn
- [ ] `@tanstack/react-table` for financial tables (do not hand-roll)
- [ ] `@supabase/supabase-js` client
- [ ] US accounting formatter helper: `Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', currencySign: 'accounting' })` — parenthesized negatives, tabular numerals (`font-feature-settings: "tnum"`)
- [ ] Inter font family globally

### Auth & Routing
- [ ] `LoginPage` (`/login`) — email + password via `supabase.auth.signInWithPassword`. Spec: 400px centered card, teal `#0D9488` Sign in button, inline error on `#FEE2E2`/`#C53030` (no toast for auth errors). No social login, no forgot-password, no sign-up in MVP.
- [ ] Auth guard — unauthenticated routes redirect to `/login`. Attach `Authorization: Bearer <access_token>` to every backend fetch. Honor `?next=` if same-origin.
- [ ] `ErrorBoundary` — route-level wrapper with plain-English fallback ("Something went wrong. Please refresh — your data is safe."). Logs with current `trace_id`.

### Upload Flow
- [ ] `FileUpload` component — drag & drop, multiple files. **Client-side validation before upload**: accepted extensions `.xlsx`/`.csv`/`.xls`/`.xlsm`, max 10 MB per file. Rejected files never hit `POST /upload`.
- [ ] States: idle, dragging, uploading (inline progress), wrong-type (inline red error), too-large (inline red error), server failure (error toast with retry)
- [ ] `PeriodSelector` — month/year dropdown (`MMM YYYY` labels)
- [ ] `CompanySelector` — for MVP, single-company dropdown
- [ ] `LoadingProgress` — 4-step bar. Polls `GET /runs/{run_id}/status`. Completed ✓ in `#166534`, active ● in teal `#0D9488`, pending ○ in `#6B6B6B`.

### Report View
- [ ] `ReportSummary` — plain-language narrative. States: generating (skeleton + spinner), verified (full with "Verified · Guardrail Passed" badge), stale ("Out of date" amber chip when source re-uploaded), guardrail-failed (not rendered — GuardrailWarning takes over)
- [ ] **Verified badge** — checkmark + teal accent, only on guardrail-passed reports. Never on raw downloads.
- [ ] **Provenance popovers** — every number in the narrative and every figure in AnomalyCards is hoverable. Reveals source filename + original column name (e.g. `drone_mar_2026.xlsx — column 'Amount'`). Tabular numerals + subtle underline on hover.
- [ ] `AnomalyCard` — API: `{ value, direction: favorable|unfavorable|neutral, severity: high|medium|normal, ... }`. Direction drives color (favorable = green chip `#ECFDF5/#166534`); severity drives label. Do NOT color by sign of value. Skeleton state + empty-category summary row.
- [ ] US accounting formatting everywhere: `$1,234`, `($1,234)` for negatives, `$4.73M` in narrative
- [ ] `MailButton` — opens compose, sends via `POST /mail/send`

### Edge-Path Screens
- [ ] `GuardrailWarning` (screen 3b) — shown when `status=guardrail_failed`. Inline error pattern (NOT a toast). Offers `Retry Analysis` (creates fresh `run_id`, reuses stored file) + `Download Raw Data` (unverified, `raw_` prefix).
- [ ] `MappingConfirmModal` — shown when `low_confidence_columns` returned on run status. Max 3 rows. Column name verbatim + agent's guess + confidence % + dropdown (REVENUE/COGS/OPEX/G&A/R&D/OTHER_INCOME/OTHER/SKIP) + "Skip this column" link. Teal `Confirm Mapping` primary CTA. Cancel = cancel run (file stays in storage). Esc = Cancel. Focus trap.
- [ ] **Empty state** (screen 6) — for users with zero `monthly_entries`. "Let's set up your baseline." Neutral palette only (no red/amber). Defaults period to previous calendar month. Dashboard/history links disabled with tooltip.

### Cross-Cutting
- [ ] **Toast system** — 4 types (success 4s, error manual, warning 6s, info 4s). Top-right, max 3 visible, `role="status"`/`role="alert"`, dedup within 1s. Use for: mail sent, rate-limited (429), network error, client-side file reject. NEVER for guardrail or auth errors.
- [ ] **Responsive breakpoints** — desktop-first. Mobile (<768px): upload + report only (Dashboard/TrendChart/MetricCard/HistoryList hidden). Tablet (768–1023px): single-column stacked. Tables horizontal-scroll below 1024px. Tap targets ≥44×44 on touch.
- [ ] Error state copy — no technical jargon anywhere; all strings sourced from backend `messages.py` mirror

### End-of-day check
> In a browser: sign in → drop DRONE Mar 2026 Excel → see 4-step progress → land on verified report with badge + AnomalyCards + provenance hover. Force a guardrail failure and see `GuardrailWarning`. Force a <80% mapping and see `MappingConfirmModal`. ✅

---

## Day 5 — Mail + E2E Tests + Polish

**Goal:** Full E2E works from file drop to inbox. All critical paths have tests. Demo quality.

### Mail
- [ ] Wire `adapters/resend_email.py` — Resend API client, HTML template (simple, readable), subject `[Month Proof] {Month YYYY} — {Company}`
- [ ] `POST /mail/send` — accepts `{report_id, to_email}`, returns `{status, message_id}`. Marks `reports.mail_sent = true`, `mail_sent_at = now()`.
- [ ] `MailButton` wired end-to-end with success toast ("Report emailed to ...") and error toast on failure
- [ ] Mail body: narrative summary + anomaly list + link to dashboard. No technical jargon.

### E2E Tests
- [ ] DRONE Feb 2026 → Mar 2026 full flow (baseline + analysis period)
- [ ] CSV format test — same pipeline with `.csv`
- [ ] NetSuite edge case — `.xls` XML Spreadsheet 2003 file reads correctly
- [ ] Guardrail test — narrative with intentional wrong number → `guardrail_failed`, file remains in storage, Retry Analysis path works
- [ ] **PII sanitizer test** — file with SSN column header and SSN regex values → columns dropped, log emits counts (never values), Claude never sees PII
- [ ] **Mapping confidence test** — ambiguous column → `MappingConfirmModal` surfaces, confirmed mapping persisted to `accounts`
- [ ] **Rate limit test** — spam `POST /upload` → 429 with `Retry-After` header + `messages.RATE_LIMITED`
- [ ] **Storage cleanup test** — file deleted on success, **preserved** on guardrail_failed
- [ ] **Stale report test** — re-upload same `(company_id, period)` after verified report → badge swaps to "Out of date" chip + regenerate CTA
- [ ] **Invalid run transition test** — illegal status move raises `InvalidRunTransition`
- [ ] **Empty state test** — user with zero entries sees the baseline-setup screen, not an error
- [ ] RLS test — two users cannot see each other's data

### Polish
- [ ] Loading skeletons on every data-fetching component
- [ ] All error strings routed through backend `messages.py` / mirrored on frontend
- [ ] Tablet view sanity check (768–1023px)
- [ ] `black .` + `flake8` on backend; frontend lint clean
- [ ] Verify every prompt is a file in `prompts/`, none inline

### End-of-day check
> Upload DRONE Mar 2026 in the browser → 4-step progress → verified report → send email → email arrives. All tests green. ✅

---

## Day 6 — Demo + Deploy + Submit

**Goal:** Live URL working, demo rehearsed, submission filed.

### Deploy
- [ ] Railway backend — env variables: `ANTHROPIC_API_KEY`, `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`, `RESEND_API_KEY`, `FRONTEND_URL` (Vercel production URL)
- [ ] Vercel frontend — `VITE_SUPABASE_URL`, `VITE_SUPABASE_ANON_KEY`, `VITE_API_URL` (Railway URL)
- [ ] **CORS** — Railway backend allowlist includes Vercel URL (via `FRONTEND_URL` env)
- [ ] Pre-load DRONE **Feb 2026 baseline** into Supabase so Comparison has history for Mar 2026
- [ ] Smoke test on live URL: login → upload → report → email
- [ ] Measure cold-start time (Railway free tier ~10s). Plan for pre-demo ping.

### Demo Prep
- [ ] Write 3-minute demo script (per `docs/runbook.md`)
- [ ] Pre-warm browser session on demo laptop: sign in as `demo@dronedemo.com` so `/login` is skipped on stage
- [ ] Demo files on desktop: `drone_feb_2026.xlsx`, `drone_mar_2026.xlsx`
- [ ] Resend verified sender + test email to jury-visible inbox
- [ ] Browser zoom 125%, close other tabs/notifications
- [ ] Record backup demo video (Loom/QuickTime, night of Day 5)
- [ ] Rehearse demo end-to-end at least twice

### Pre-Demo Checklist (30 min before)
- [ ] `GET /health` returns 200
- [ ] Frontend opens with no console errors
- [ ] Ping backend to beat Railway cold start: `curl $RAILWAY_URL/health`
- [ ] Email sender still verified
- [ ] Fallback ready: localhost + ngrok if Railway fails

### Submit
- [ ] README: setup, demo link, architecture summary, the Golden Rule
- [ ] Commit `schema.sql`, all `prompts/*.txt`, `.env.example` (no secrets)
- [ ] Demo video uploaded (Loom or YouTube, ≤3 min)
- [ ] GitHub repo public
- [ ] Submit via Cerebral Valley platform before April 26, 8:00 PM EST

### Final Check Before Submit
- [ ] Live demo link works end-to-end
- [ ] DRONE Excel uploads, variance calculated in Python, guardrail active, report is plain English, email sends
- [ ] Every prompt is a file in `prompts/` with a logged git SHA
- [ ] GitHub repo public
- [ ] No `.env` or secrets committed

---

## Cross-Cutting Rules (apply every day)

- **Domain layer has zero I/O imports.** No `pandas`, `anthropic`, `supabase`, `resend` inside `backend/domain/`.
- **Agents depend on ports, never on concrete adapters.** Wire-up happens in `api/deps.py`.
- **Every `runs.status` write goes through `RunStateMachine.transition()`.**
- **Every third-party SDK call lives in `adapters/`.** Changing vendors = rewrite one adapter.
- **Every log line carries `trace_id`.** Never log cell values from a DataFrame — column names and counts only.
- **PII sanitizer runs before pandera and before any Claude call.** No exceptions.
- **All user-facing strings in `backend/messages.py`.** Exceptions never hold user copy.
- **Claude never does math.** If you're writing a prompt that asks for a calculation — stop, write Python.

---

## Risk Plan

| Risk | Mitigation |
|---|---|
| Day 1 scaffold slips — cascades into every later day | Cut rate-limit scaffold to Day 3; keep domain/adapters/auth/storage on Day 1 |
| PII sanitizer forgotten on Day 2 | Explicit task on Day 1; E2E test on Day 5 |
| Guardrail tolerance too strict during demo | Raise 2% → 3% as a last resort; document in `messages.py` |
| Frontend Day 4 underestimates — too many components | Cut line: Empty state, Stale state, Dashboard — defer to post-MVP |
| CORS misconfigured — silent Day 4 failure | Day 1 explicit task; test cross-origin with Bruno on Day 3 |
| Railway cold start during demo | Pre-demo `/health` ping + localhost+ngrok fallback |
| `MappingConfirmModal` contract (low-confidence columns) missing from API | Frozen on Day 3 as a field in `/runs/{run_id}/status` response |
| Agent slow during live demo | Keep pre-recorded Loom backup; pre-warm with a cached run |
| Resend delivery delay | Show sent confirmation in UI; email arrival is a "nice-to-have" for demo |
| pgvector temptation | Out of scope — SQL joins only for week 1 |
| Guardrail fails repeatedly on demo data | Rehearse demo data end-to-end Day 5; narrative prompt explicitly says "Use exact numbers from the data provided" |
