# Month Proof — Claude Code Context

AI-powered month-end close agent for US finance teams. Drop messy Excel files → agent finds anomalies, compares to history, writes a verified plain-language report, and exports an Excel close package. The frontend can open a prefilled `mailto:` draft; backend email delivery is still stubbed.

Built with Claude Opus 4.7 — Anthropic Hackathon April 2026.

---

## THE GOLDEN RULE

**Numbers come from pandas. Prose comes from Claude. A numeric guardrail verifies both match.**

- Claude NEVER does arithmetic. All calculations (variance, totals, anomaly thresholds) are Python/pandas.
- Claude ONLY interprets the pandas output in plain English.
- No report is saved to Supabase until the numeric guardrail passes.
- The monthly interpreter uses strict, unit-aware guardrail checks: money uses cent/float-noise tolerance and percentages use 0.05 percentage points. Legacy quarterly and Opus-upgrade callers still use the documented legacy tolerance in `backend/tools/guardrail.py`.

---

## Core Commands

```bash
# Backend
pip install -r requirements.txt
uvicorn backend.main:app --reload        # API at localhost:8000

# Frontend
cd frontend && npm install
npm run dev                              # UI at localhost:5173

# Database
supabase db push                         # Apply supabase/migrations/ against Supabase
psql $DATABASE_URL -f supabase/seed.sql  # Load demo data (run once after auth user created)

# Tests
pytest                                   # Run all tests
pytest tests/tools/test_guardrail.py    # Guardrail tests only

# Code quality
black --check backend tests
flake8 backend tests
```

---

## Project Structure

```
monthproof/
├── backend/
│   ├── main.py                       # App factory — middleware, lifespan, router include
│   ├── messages.py                   # ALL user-facing error strings (single source)
│   ├── logger.py                     # JSON log formatter + trace_id contextvar
│   ├── settings.py                   # Pydantic BaseSettings — env vars in one place
│   │
│   ├── domain/                       # PURE Python. No pandas/anthropic/supabase imports.
│   │   ├── entities.py               # Company, Account, MonthlyEntry, Anomaly, Report, Run
│   │   ├── contracts.py              # PandasSummary + NarrativeJSON Pydantic models
│   │   ├── run_state_machine.py      # RunStatus enum + allowed transitions
│   │   ├── ports.py                  # Protocol interfaces — repos, LLM, storage, email
│   │   └── errors.py                 # Domain exceptions (incl. GuardrailError)
│   │
│   ├── adapters/                     # I/O implementations of domain.ports
│   │   ├── supabase_repos.py         # All repo impls share one client
│   │   ├── supabase_storage.py       # FileStorage → storage.objects
│   │   ├── anthropic_llm.py          # LLMClient — loads prompts from prompts/
│   │   └── resend_email.py           # Stub EmailSender adapter
│   │
│   ├── agents/                       # Use cases — depend on ports, injected at wire-up
│   │   ├── discovery.py              # Structure/header discovery
│   │   ├── account_mapper.py         # Source values → canonical GL accounts
│   │   ├── parser.py                 # Read, sanitize, normalize, and preview
│   │   ├── consolidator.py           # Multi-source consolidation/reconciliation
│   │   ├── comparison.py             # Python-only variance calculation
│   │   ├── interpreter.py            # Claude narrative + guardrail
│   │   ├── quarterly.py              # Persisted quarterly reports
│   │   ├── opus_upgrade.py           # Optional narrative upgrade
│   │   └── orchestrator.py           # Background workflow coordination
│   │
│   ├── tools/                        # Stateless helpers — no DB, no LLM
│   │   ├── file_reader.py            # pandas + openpyxl + xlrd (NetSuite edge case)
│   │   ├── pii_sanitizer.py          # Header blacklist + SSN regex — drops PII columns pre-pandera
│   │   ├── validator.py              # pandera schema validation
│   │   ├── normalizer.py             # Discovery-plan normalization
│   │   ├── hint_computer.py          # Deterministic reconciliation hints
│   │   ├── batch_matcher.py          # Deterministic transaction matching
│   │   ├── excel_export.py           # Verified close-package export
│   │   └── guardrail.py              # Numeric guardrail — DO NOT CHANGE
│   │
│   ├── api/                          # FastAPI layer — thin, no business logic
│   │   ├── deps.py                   # Build adapters once, inject into agents
│   │   ├── middleware.py             # trace_id per request
│   │   ├── auth.py                   # JWT → user_id → company_id
│   │   ├── rate_limit.py             # slowapi Limiter + composite key_func (user_id | IP)
│   │   └── routes.py                 # Existing endpoints only
│   │
│   ├── prompts/                      # ALL Claude prompts live here — never inline
│   │   ├── narrative_prompt.txt      # Monthly report writer
│   │   ├── discovery_prompt.txt      # File-structure discovery
│   │   ├── account_mapping_prompt.txt # Source-value mapping
│   │   └── quarterly_report_prompt.txt # Quarterly narrative
│   │
├── frontend/
│   └── src/                          # React pages, components, auth, API client
├── supabase/
│   ├── migrations/
│   │   ├── 0001_initial_schema.sql   # 7 tables + RLS + category seed
│   │   └── 0010_add_company_monthly_scale.sql
│   └── seed.sql                      # Demo company row (Redhawk Alarm & Security LLC)
├── docs/                             # All architecture docs
├── .env                              # Never commit this
└── CLAUDE.md                         # This file
```

**Deleted:** `backend/tools/mailer.py`. The replacement `backend/adapters/resend_email.py` is behind the `EmailSender` port but remains a stub; the current frontend uses `mailto:`.

---

## Model Strategy

| Task | Model | Notes |
|---|---|---|
| Structure discovery | claude-haiku-4-5-20251001 | `discovery.py` |
| Column/category mapping | claude-haiku-4-5-20251001 | `parser.py` |
| Source-value account mapping | claude-haiku-4-5-20251001 | `account_mapper.py` |
| Monthly narrative + reconciliation classification | claude-opus-4-7 | `interpreter.py` |
| Quarterly narrative | claude-opus-4-7 | `quarterly.py` |
| Optional narrative upgrade | claude-opus-4-7 | `opus_upgrade.py` |

No user-selectable model toggle in MVP.
Model identifiers are module-level constants in the relevant agent files.

---

## Agent Architecture

The active workflow is coordinated by `agents/orchestrator.py`. It performs structure discovery, optional user review, account mapping, parsing/normalization, multi-source consolidation and reconciliation, preview confirmation, historical comparison, interpretation, and guardrail validation. Quarterly generation is a separate persisted workflow. Agents depend on domain ports; orchestration passes validated data directly and persists run/report state through repositories.

---

## Critical Files

**`backend/tools/guardrail.py`** — Do not break this.
`verify_guardrail()` accepts the narrative contract, pandas summary, optional reconciliation reference values, and a `strict` mode. The monthly interpreter uses strict unit-separated money/percentage pools; quarterly and Opus-upgrade paths currently use the legacy pool. Narrative-vs-`numbers_used` consistency is measured and logged, with enforcement controlled by the named rollout flag in this module.

**`backend/tools/file_reader.py`** — Handles NetSuite edge case.
NetSuite exports `.xls` files that are actually XML Spreadsheet 2003. openpyxl cannot open them. Detect by reading first 2 bytes: if `b"<?"` → parse as XML, not binary xls.

**`backend/prompts/narrative_prompt.txt`** — Claude's persona.
Claude writes as a CFO assistant. Plain English. No jargon. Exact numbers come from the deterministic pandas summary and reconciliation context. It returns `NarrativeJSON`: `narrative`, `numbers_used`, and optional `reconciliation_classifications`.

**`backend/tools/pii_sanitizer.py`** — PII stripping, called by Parser BEFORE pandera and BEFORE any Claude call.

Pipeline order inside the Parser agent:
```
read/sanitize sample → discover structure → read/sanitize full data → normalize/validate → map accounts → preview → confirmed write
```

Why this order:
- STRIP PII before pandera — pandera validates the P&L schema; PII columns (SSN, name, DOB) would either fail dtype checks or pass stale noise through. Strip first.
- STRIP PII before column map — the Haiku call includes column headers and 2-3 sample rows. Claude must never see an SSN, a name, a home address, or a bank account number.

Strategy:
- **Header blacklist, case-insensitive substring match.** Drop column entirely on match (no hashing).
  Categories: SSN/tax ID, DOB, personal names (only when `employee_id` is present in the same sheet), home address, bank account/routing, personal contact.
- **Value-level fallback, SSN only:** regex `^\d{3}-?\d{2}-?\d{4}$`. If an unmapped column has ≥20% of non-null values matching, drop it.
- Emits a structured log at INFO level (`event="pii_sanitization"`) with `trace_id`, `run_id`, `columns_dropped` (header names), `rows_in_file`, `strategy`. **Values are never logged.**
- If all columns are stripped: raise `FileHasNoValidColumns` → surfaces as `messages.FILE_HAS_NO_VALID_COLUMNS`.

**`backend/api/rate_limit.py`** — slowapi `Limiter` instance + composite `key_func` (user_id if JWT present, else IP). In-memory backend (single Railway container). Redis post-MVP.

Limits:
| Endpoint | Limit (keyed by authenticated user, otherwise client IP) |
|---|---|
| `POST /upload` | 5/min, 20/hour |
| `POST /mail/send` | 10/hour |
| `GET /runs/{id}/status` | 120/min |
| `GET /report/*`, `GET /anomalies/*` | 60/min |
| `GET /health` | none |

On 429: `Retry-After` header + JSON body with `messages.RATE_LIMITED`. Frontend disables the action for `retry_after_seconds` and shows a countdown.

**`backend/domain/errors.py`** — Exception taxonomy. The full list:

| Exception | Raised by | Retry? | HTTP surface |
|---|---|---|---|
| `TransientIOError` | Adapters, after exhausting retries on a network/5xx failure | No (already retried in adapter) | 503 |
| `DuplicateEntryError` | `EntriesRepo` on unique-constraint violation | Never | 409 |
| `RLSForbiddenError` | Any repo when RLS denies the row | Never | 403 |
| `GuardrailError` | Interpreter use case, after semantic retry | Never | surfaces as `guardrail_failed` run status, not a 5xx |
| `InvalidRunTransition` | `RunStateMachine.transition()` | Never — programmer error | 500 |
| `FileHasNoValidColumns` | Parser after PII sanitization | Never | 422 |
| `MappingAmbiguous` | Parser/category mapping | User confirmation | 422 when it reaches the API handler |
| `DiscoveryFailed` | Discovery after semantic retry | Fresh run | terminal parsing failure |
| `DiscoveryLowConfidence` | Discovery confidence gate | User confirmation | pauses at `awaiting_discovery_confirmation` |

User-facing strings for each of these live in `messages.py`, not in the exception itself.

---

## Database Tables

Seven tables are created by migration `0001`; migrations `0002` through `0010` add current workflow, reconciliation, quarterly-reporting, and revenue-scale fields. Company-owned data is isolated by `company_id`.

| Table | Purpose |
|---|---|
| `companies` | Company profile, currency, sector |
| `account_categories` | Fixed: REVENUE, COGS, OPEX, G&A, R&D, OTHER_INCOME, OTHER |
| `accounts` | Company-specific chart of accounts (agent-generated) |
| `monthly_entries` | All financial data, period by period |
| `anomalies` | Flagged items with severity and description |
| `reports` | Final verified reports |
| `runs` | Pipeline state, previews, summaries, and audit metadata |

Never break `company_id` isolation. Each company sees only its own data.

**Auth:** Supabase Auth (email + password). `companies.owner_id` references `auth.users(id)`.
RLS policies on every company-owning table enforce `owner_id = auth.uid()`. Backend receives
`Authorization: Bearer <supabase_jwt>`, validates it, resolves `user_id → company_id` via
the `companies` table, and never accepts `company_id` from the client.

---

## Repo Layer

Repositories live in `adapters/supabase_repos.py` and implement `Protocol` interfaces defined in `domain/ports.py`. We use a hybrid return-type policy — strict where it matters, loose where it doesn't:

| Entity | Repo returns/accepts | Why |
|---|---|---|
| `MonthlyEntry` | `domain.entities.MonthlyEntry` (dataclass) | Hot path. Comparison agent reads thousands of rows — type-safe field access prevents silent KeyErrors. |
| `Anomaly` | `domain.entities.Anomaly` (dataclass) | Hot path. Written by Comparison, read by Interpreter — both sides benefit from a strict contract. |
| `Report` | `domain.entities.Report` (dataclass) | Single row per run but it IS the product — guardrail-verified output deserves a typed contract. |
| `Company` | plain `dict` | Read once per request during auth lookup. Typing it adds ceremony for no payoff. |
| `Account` | plain `dict` | Only written at parser time, only read as `{name → category}` map. |
| `Run` | plain `dict` | State transitions are enforced by `RunStateMachine`, not by the dict shape. |

**Rule:** if an agent reads or writes an entity in its main loop, it gets a dataclass. If it's a one-shot lookup or config read, a dict is fine. Do not introduce a dataclass for the remaining three later "for consistency" — that's over-engineering.

Agents import entities from `domain.entities`, never from adapters. Adapters are the only layer that knows the Supabase row shape.

---

## Retry & Error Handling

### Storage uploads (Supabase Storage)
- **3 attempts total** (1 initial + 2 retries)
- Backoff before retries: **0.5s → 1.5s** with ±20% jitter (`4.0` is present in the tuple but is not slept after the final failed attempt)
- Retry **only** on `httpx.ConnectError` and `ReadTimeout`; other exceptions surface immediately
- Do NOT retry on 4xx (auth, quota, malformed) — they are deterministic
- After the 3rd failure: adapter raises `TransientIOError`, use case transitions run to `upload_failed`, user re-uploads

### Database writes (Supabase PostgREST)
- **Fail-fast with at most one retry**, and only on connection-class errors (dropped TCP, 5xx from PostgREST)
- Zero retries for constraint violations, RLS denials, or validation errors
- Unique-constraint violation on `monthly_entries(company_id, account_id, period)` → `DuplicateEntryError` surfaces **immediately**. This is a dup-upload signal, not a transient failure.

### Where retry logic lives
- **Adapters own all I/O retry.** Only the adapter can distinguish transient from permanent errors. Use cases receive either a success or a typed domain exception — never a raw HTTP error, never retry metadata.
- **One exception:** the guardrail's "retry Claude once with a stronger prompt" is a **semantic** retry, not an I/O retry. It lives in the **Interpreter use case**, not in `anthropic_llm.py`. The adapter retries network failures; the use case retries bad content.

### Mid-run recovery
- **No checkpoint resume.** On any failure the run transitions to a terminal `*_failed` status with an `error_message`; the frontend shows a plain-English retry button; the user re-uploads to start a fresh run.
- **On a new upload for the same `(company_id, period)`:** the Parser use case issues `DELETE FROM monthly_entries WHERE company_id=? AND period=?` **before** inserting. Do NOT use `UPSERT` / `ON CONFLICT DO UPDATE` — an explicit delete-then-insert leaves no stale rows from the prior failed run.
- The unique constraint remains in place. Within a single run it prevents double-insert; across re-uploads the delete-first rule keeps it compatible.

### Storage cleanup
- Triggered by the orchestrator only after the interpreter writes the `reports` row and transitions the run to `complete`
- Runs in a **FastAPI BackgroundTask** — the user response is sent first, cleanup happens after
- On guardrail failure (attempt 2 also failed): **file stays in storage** so the user's "Retry Analysis" button works without re-upload. Storage-leak mitigation (TTL sweep of abandoned guardrail_failed runs) is post-MVP.
- If cleanup itself fails: **log at WARNING with `trace_id`, `run_id`, `storage_key`, and the adapter's error. Do not raise.** The run is already complete from the user's perspective — a leaked object is an ops problem, not a product failure. Wrap the background task in a top-level `try/except Exception`.

---

## Coding Standards

**Error messages:** Plain English, no technical terms for user-facing errors.
- Bad: "pandera SchemaError: column 'amount' failed dtype check"
- Good: "We couldn't read the 'Amount' column. Please check for non-numeric values."

**Prompts:** Never write Claude prompts inline in code. All prompts in `backend/prompts/`. Log git SHA with each prompt call.

**Math:** If you're about to write a Claude prompt that asks it to calculate something — stop. Write a Python function instead.

**Agents:** Use explicit dataclasses/Pydantic contracts at workflow boundaries; do not pass unvalidated free-form LLM output.

**Security:** Even when not asked, fix OWASP Top 10 risks you notice in the files you are already working on.

---

## Environment Variables

```bash
# .env (copy from .env.example)
ANTHROPIC_API_KEY=
SUPABASE_URL=
SUPABASE_SERVICE_KEY=
SUPABASE_ANON_KEY=
SUPABASE_JWT_SECRET=
RESEND_API_KEY=
RESEND_FROM_EMAIL=
FRONTEND_URL=http://localhost:5173
APP_ENV=development
```

---

## Demo Data

Seven demo companies live in `docs/demo_data/`: `clearview`, `corebuilt`,
`harvest`, `helix`, `redhawk`, `sentinel`, `vandelay`.

**`redhawk/` is the seed company** — a small owner-operated alarm dealer that
matches the ICP (field service, 5 employees, ~$38,090/month revenue →
`under_100k` band). Four files, period `2026-03-01`:
- `redhawk_gl_mar_2026.xlsx` — Service Revenue 3,540.00
- `redhawk_contracts_mar_2026.xlsx` — 85 active accounts
- `redhawk_payroll_mar_2026.xlsx`
- `redhawk_vendor_invoices_mar_2026.xlsx`

Expected demo output:
- Service Revenue: `stale_reference`, 285.00 gap (GL 3,540.00 vs roster 3,825.00)
- Roster counts: `n_active` 85, `n_billed_in_period` 82, `count_delta` 3
- Coverage cards for GL lines with no supporting file (Rent, Licensing)

The earlier DRONE single-file workbooks **no longer exist** in the tree. One
legacy integration fixture still points to `docs/demo_data/Drone Inc - Mar
26.xlsx`; the four tests that consume it skip accordingly. That is expected,
not a demo-data failure.

---

## Migration Naming Convention

Migration files must be named: `{4-digit-sequence}_{snake_case_description}.sql`

Examples: `0001_initial_schema.sql`, `0002_add_pandas_summary.sql`

- Never use timestamps in migration filenames.
- Always increment the sequence number.
- All migrations live in `supabase/migrations/`.
- `supabase/seed.sql` holds demo data only — never schema changes.

---

## What NOT to do

- Do not use LangChain. Anthropic SDK tool-use loop only.
- Do not use Great Expectations. pandera only.
- Do not use Celery. FastAPI background tasks only.
- Do not let Claude do math. Ever.
- Do not write prompts inline. prompts/ folder only.
- Do not skip the guardrail. Even in tests.
- Do not add pgvector this week. SQL joins only for history comparison.
- **Do not log cell values from a DataFrame. Ever.** Only column names and counts. Any `logger.info(df.head())`, `print(df)`, or similar that can leak SSN/name/address values is a rejection in code review. PII blacklist applies to logs too.
