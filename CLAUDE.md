# Month Proof — Claude Code Context

AI-powered month-end close agent for US finance teams. Drop messy Excel files → agent finds anomalies, compares to history, writes a verified plain-language report, sends email.

Built with Claude Opus 4.7 — Anthropic Hackathon April 2026.

---

## THE GOLDEN RULE

**Numbers come from pandas. Prose comes from Claude. A numeric guardrail verifies both match.**

- Claude NEVER does arithmetic. All calculations (variance, totals, anomaly thresholds) are Python/pandas.
- Claude ONLY interprets the pandas output in plain English.
- No report is saved to Supabase until the numeric guardrail passes.
- Guardrail tolerance: 2%. If Claude writes "$4.8M" but pandas says $4,730,000 → GuardrailError.

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
pytest backend/tools/test_guardrail.py  # Guardrail tests only

# Code quality
black .
flake8
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
│   │   └── resend_email.py           # EmailSender (replaces tools/mailer.py)
│   │
│   ├── agents/                       # Use cases — depend on ports, injected at wire-up
│   │   ├── parser.py                 # Agent 1: reads files, maps to accounts
│   │   ├── comparison.py             # Agent 2: Python-only variance calculation
│   │   └── interpreter.py            # Agent 3: Claude narrative + guardrail
│   │
│   ├── tools/                        # Stateless helpers — no DB, no LLM
│   │   ├── file_reader.py            # pandas + openpyxl + xlrd (NetSuite edge case)
│   │   ├── pii_sanitizer.py          # Header blacklist + SSN regex — drops PII columns pre-pandera
│   │   ├── validator.py              # pandera schema validation
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
│   │   ├── narrative_prompt.txt      # CFO-persona report writer (includes anomaly reasons)
│   │   └── mapping_prompt.txt        # Column → US GAAP category mapper
│   │
│   └── db/                           # (empty — schema moved to supabase/migrations/)
├── frontend/
│   └── src/
│       └── components/
│           ├── ErrorBoundary.tsx     # Route-level error wrapper
│           ├── FileUpload.tsx        # Drag/drop + client-side validation
│           ├── AnomalyCard.tsx
│           ├── ReportSummary.tsx
│           ├── GuardrailWarning.tsx
│           └── MappingConfirmModal.tsx
├── supabase/
│   ├── migrations/
│   │   └── 0001_initial_schema.sql   # 7 tables + RLS + category seed
│   └── seed.sql                      # Demo data (DRONE Inc. row)
├── docs/                             # All architecture docs
├── .env                              # Never commit this
└── CLAUDE.md                         # This file
```

**Deleted:** `backend/tools/mailer.py`. All Resend logic lives in `backend/adapters/resend_email.py` behind the `EmailSender` port.

---

## Model Strategy

| Task | Model | Notes |
|---|---|---|
| Column mapping | claude-haiku-4-5-20251001 | Hard-coded in parser.py. No toggle. |
| Narrative + anomaly reasons | claude-opus-4-7 | Hard-coded in interpreter.py. No toggle. |

No user-selectable model toggle in MVP.
Post-hackathon: expose MODEL constants at top of each agent file for easy refactor.

---

## Agent Architecture

Three sequential agents, each with a single responsibility:

1. **Parser** (`agents/parser.py`) — reads files, detects format, maps columns to US GAAP categories, writes to `monthly_entries`
2. **Comparison** (`agents/comparison.py`) — Python only, no Claude. Calculates variance vs history, writes flagged items to `anomalies`
3. **Interpreter** (`agents/interpreter.py`) — Claude writes narrative, guardrail validates, writes to `reports`

Agents communicate via Supabase — not direct function calls.

---

## Critical Files

**`backend/tools/guardrail.py`** — Do not break this.
```python
def verify_guardrail(claude_json: dict, pandas_summary: dict, tolerance=0.02) -> tuple:
    for num in claude_json["numbers_used"]:
        exists = any(
            abs(num - p_val) / abs(p_val) < tolerance
            for p_val in pandas_summary.values()
            if p_val != 0
        )
        if not exists:
            return False, f"Mismatch: {num} not found in pandas output"
    return True, "Success"
```

**`backend/tools/file_reader.py`** — Handles NetSuite edge case.
NetSuite exports `.xls` files that are actually XML Spreadsheet 2003. openpyxl cannot open them. Detect by reading first 2 bytes: if `b"<?"` → parse as XML, not binary xls.

**`backend/prompts/narrative_prompt.txt`** — Claude's persona.
Claude writes as a CFO assistant. Plain English. No jargon. Exact numbers from pandas_summary only. Must return JSON with `narrative` and `numbers_used` array.

**`backend/tools/pii_sanitizer.py`** — PII stripping, called by Parser BEFORE pandera and BEFORE any Claude call.

Pipeline order inside the Parser agent:
```
read → skip metadata → detect header → STRIP PII → pandera validate → column map (Claude Haiku) → normalize → write
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
| Endpoint | Per user_id | Per IP (fallback) |
|---|---|---|
| `POST /upload` | 5/min, 20/hour | 10/min, 30/hour |
| `POST /mail/send` | 10/hour | — |
| `GET /runs/{id}/status` | 120/min | — |
| `GET /report/*`, `GET /anomalies/*` | 60/min | — |
| `GET /health` | none | none |

On 429: `Retry-After` header + JSON body with `messages.RATE_LIMITED`. Frontend disables the action for `retry_after_seconds` and shows a countdown.

**`backend/domain/errors.py`** — Exception taxonomy. The full list:

| Exception | Raised by | Retry? | HTTP surface |
|---|---|---|---|
| `TransientIOError` | Adapters, after exhausting retries on a network/5xx failure | No (already retried in adapter) | 503 |
| `DuplicateEntryError` | `EntriesRepo` on unique-constraint violation | Never | 409 |
| `RLSForbiddenError` | Any repo when RLS denies the row | Never | 403 |
| `GuardrailError` | Interpreter use case, after semantic retry | Never | surfaces as `guardrail_failed` run status, not a 5xx |
| `InvalidRunTransition` | `RunStateMachine.transition()` | Never — programmer error | 500 |

User-facing strings for each of these live in `messages.py`, not in the exception itself.

---

## Database Tables

Five tables in Supabase. All data isolated by `company_id`.

| Table | Purpose |
|---|---|
| `companies` | Company profile, currency, sector |
| `account_categories` | Fixed: REVENUE, COGS, OPEX, G&A, R&D, OTHER_INCOME |
| `accounts` | Company-specific chart of accounts (agent-generated) |
| `monthly_entries` | All financial data, period by period |
| `anomalies` | Flagged items with severity and description |
| `reports` | Final verified reports |

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
- Exponential backoff: **0.5s → 1.5s → 4s** with ±20% jitter
- Retry **only** on network-class errors: `httpx.ConnectError`, `ReadTimeout`, 5xx responses
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
- Triggered by the **Interpreter use case** only after `reports` row is written AND the run transitions to `complete`
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

**Agents:** Each agent returns a typed dict. No loose string passing between agents.

---

## Environment Variables

```bash
# .env (copy from .env.example)
ANTHROPIC_API_KEY=
SUPABASE_URL=
SUPABASE_SERVICE_KEY=
RESEND_API_KEY=
```

---

## Demo Data

DRONE monthly financials are in `docs/demo_data/`.
- `drone_feb_2026.xlsx` — baseline period (period: 2026-02-01)
- `drone_mar_2026.xlsx` — analysis period (period: 2026-03-01)

Expected demo output:
- G&A: -34% variance (favorable) ✅
- Travel: +61% variance (flagged) ⚠️
- Gross margin: 39.4% — 7-quarter high

---

## Migration Naming Convention

Migration files must be named: `{4-digit-sequence}_{snake_case_description}.sql`

Examples: `0001_initial_schema.sql`, `0002_add_low_confidence_columns.sql`

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