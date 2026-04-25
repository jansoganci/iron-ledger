# Day 1 — Backend Foundation
*IronLedger 6-Day Sprint — Built with Opus 4.7 Hackathon, April 2026*

## Goal

FastAPI running with Clean Architecture scaffold, Supabase fully configured (schema + RLS + Auth + Storage), infrastructure in place (logger + trace_id, rate limiter, messages, settings), and DRONE Excel readable end-to-end from an authenticated `POST /upload` request.

## End-of-Day Acceptance Check

> Using Bruno with a valid demo-user JWT, POST `drone_mar_2026.xlsx` to `/upload` with `period=2026-03-01`. Verify:
> 1. A `runs` row is created with `status=pending` for the DRONE company
> 2. The file is stored under `financial-uploads/{auth.uid()}/2026-03-01/drone_mar_2026.xlsx` in Supabase Storage
> 3. A clean DataFrame is printed to the terminal (file read + PII-sanitized + pandera-validated)
> 4. `GET /health` returns 200
> 5. RLS test: a second user's JWT cannot see the DRONE run ✅

## Preconditions (from prior days)

None — Day 1 is the start of the sprint.

External pre-requisites (not tasks, but must exist before starting):
- Anthropic API key (`ANTHROPIC_API_KEY`)
- Supabase project created, URL + service key available
- Resend API key (needed at least by Day 5; fine to acquire now)
- Python 3.11+ and Node 20+ installed locally

---

## Tasks

### 1. Project Scaffold

- [ ] Create folder structure: `backend/{domain,adapters,agents,api,tools,prompts,db}/`, plus `frontend/` (empty for now) and `tests/`
  - **Why:** Clean Architecture layer boundaries are enforced by folder structure; agents depend on `domain.ports`, adapters implement them.
  - **Blocks:** Every other Day 1 task.
- [ ] `backend/main.py` — FastAPI app factory. Wires CORS, middleware, lifespan, router include. No business logic.
  - **Files:** `backend/main.py`
- [ ] `backend/settings.py` — Pydantic `BaseSettings` reading `.env`. Keys: `ANTHROPIC_API_KEY`, `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`, `RESEND_API_KEY`, `FRONTEND_URL` (optional for Day 1, required Day 6).
  - **Files:** `backend/settings.py`, `.env.example`, `.env` (never commit)
- [ ] `backend/messages.py` — single source of truth for every user-facing string. Include keys referenced across the docs: `FILE_HAS_NO_VALID_COLUMNS`, `RATE_LIMITED`, `UNSUPPORTED_FORMAT`, `PARSE_FAILED`, `MAPPING_FAILED`, `GUARDRAIL_FAILED`, `NOT_FOUND`, `MAIL_FAILED`, `UNAUTHORIZED`, `FORBIDDEN`, auth error strings.
  - **Why:** Exceptions never hold user copy. This file is the only place strings live.
  - **Files:** `backend/messages.py`
- [ ] `backend/logger.py` — JSON log formatter + `trace_id` contextvar. Every log line carries `trace_id`. Explicit rule: never log DataFrame cell values.
  - **Files:** `backend/logger.py`
- [ ] Install dependencies — pin what matters:
  ```
  fastapi, uvicorn[standard], python-multipart
  pandas, openpyxl, xlrd==1.2.0, pandera
  pydantic>=2.0, pydantic-settings>=2.0     # v2 ONLY — see rule below
  supabase
  anthropic
  resend
  slowapi==0.1.9
  python-jose[cryptography]                 # JWT validation
  jinja2                                    # email template rendering (Day 5)
  pytest, pytest-asyncio, httpx             # testing
  black, flake8
  ```
  - **Pydantic v2 rule (project-wide):** Pydantic **v2** everywhere. Use `model_dump()` (NOT `dict()`), `model_validate()` (NOT `parse_obj()`), `model_dump_json()` (NOT `json()`). v1 syntax is forbidden — it will silently work on a v1 install and break on v2.
  - **Files:** `requirements.txt`, `requirements-dev.txt`
- [ ] `backend/prompts/.gitkeep` — placeholder folder; prompt files land Days 2 and 3

### 2. Domain Layer (pure Python — zero I/O)

- [ ] `domain/entities.py` — dataclasses: `Company`, `Account`, `MonthlyEntry`, `Anomaly`, `Report`, `Run`
  - **Why:** Hot-path entities (`MonthlyEntry`, `Anomaly`, `Report`) are typed — prevents silent `KeyError`s in agent loops. `Company`, `Account`, `Run` stay as dicts in adapters (per CLAUDE.md repo layer policy).
  - **Blocks:** Agents, repo adapters.
- [ ] `domain/contracts.py` — Pydantic v2 models. **Freeze the shapes today** — every downstream day depends on these.
  - **`PandasSummary`** — Comparison agent's output, Day-3 Interpreter's input, guardrail's source of truth.
    - Nested dict keyed by account: `{accounts: dict[str, AccountSummary], period: date, company_id: UUID}`
  - **`AccountSummary`** — leaf entry inside PandasSummary. Fields:
    ```
    account: str
    category: str            # one of REVENUE, COGS, OPEX, G&A, R&D, OTHER_INCOME, OTHER
    current: float
    historical_avg: float    # 0.0 if no history (severity will be no_history)
    variance_pct: float      # 0.0 if no history
    severity: str            # low | medium | high | no_history
    ```
  - **`NarrativeJSON`** — Claude Opus output before guardrail.
    ```
    narrative: str
    numbers_used: list[float]
    ```
  - **`MappingOutput`** — single Haiku mapping result. Used inside `ParserOutput.low_confidence_columns`.
    ```
    column: str
    mapped_to: str           # category name OR "SKIP" (frontend-only sentinel)
    confidence: float        # 0.0–1.0
    ```
  - **`ParserOutput`** — Parser agent's return shape (in-memory; NOT persisted).
    ```
    status: str                              # "success" | "parsing_failed"
    file_format: str                         # "xlsx" | "csv" | "xls_binary" | "xml_spreadsheet"
    rows_parsed: int
    new_accounts_created: int
    warnings: list[str]
    low_confidence_columns: list[MappingOutput]   # ≥0 entries
    ```
  - **`SendResult`** — Resend adapter return shape (Day 5 wires; scaffolded today).
    ```
    status: str              # "sent" | "failed"
    message_id: str          # Resend message id; empty string if failed
    ```
  - **All five models use Pydantic v2 syntax** (`model_dump()`, `model_validate()`).
  - **Blocks:** Day 2 Comparison emission, Day 2 Parser return, Day 3 Interpreter input, Day 3 guardrail, Day 5 mail send.
- [ ] `domain/ports.py` — `Protocol` interfaces only. No implementations. **Method signatures below are authoritative — adapters must match exactly.**

  **Infrastructure ports:**
  ```
  class LLMClient(Protocol):
      def call(prompt: str, model: str, context: dict,
               schema: type[BaseModel]) -> BaseModel: ...
      # `prompt` is a filename relative to backend/prompts/
      # `model` is the exact model id (e.g. "claude-haiku-4-5-20251001")
      # `context` is the JSON-serializable input
      # `schema` is the Pydantic v2 model class for the expected output
      # Returns: validated instance of `schema`
      # Raises: TransientIOError after network retries exhausted

  class FileStorage(Protocol):
      def upload(user_id: str, company_id: str, period: str,
                 filename: str, data: bytes) -> str: ...
      # Returns the storage_key (full path: financial-uploads/{uid}/{period}/{filename})
      # Raises TransientIOError after 3 retries (0.5s/1.5s/4s + jitter)

      def download(storage_key: str) -> bytes: ...
      def delete(storage_key: str) -> None: ...

  class EmailSender(Protocol):
      def send(to: str, subject: str, html: str, text: str) -> SendResult: ...
  ```

  **Repository ports** (return-type policy per CLAUDE.md — dataclasses for hot-path entities, dicts for one-shot lookups):
  ```
  class EntriesRepo(Protocol):
      def list_history(company_id: str, period: date,
                       lookback_months: int = 6) -> list[MonthlyEntry]: ...
      def replace_period(company_id: str, period: date,
                         entries: list[MonthlyEntry]) -> None: ...
      # Atomic DELETE-then-INSERT in a single transaction.
      # Raises DuplicateEntryError on unique-constraint violation (never retried).

  class AnomaliesRepo(Protocol):
      def list_for_period(company_id: str, period: date) -> list[Anomaly]: ...
      def write_many(anomalies: list[Anomaly]) -> None: ...

  class ReportsRepo(Protocol):
      def get(company_id: str, period: date) -> Report | None: ...
      def write(report: Report) -> Report: ...
      def mark_mail_sent(report_id: str) -> None: ...

  class RunsRepo(Protocol):
      def get_by_id(run_id: str) -> dict: ...
      def create(company_id: str, period: date) -> dict: ...
      def update_status(run_id: str, status: RunStatus,
                        extra: dict | None = None) -> None: ...
      # `extra` may contain: step, step_label, progress_pct, error_message,
      # report_id, raw_data_url. Keys absent from `extra` are not modified.
      def set_low_confidence_columns(run_id: str,
                                      columns: list[MappingOutput]) -> None: ...

  class CompaniesRepo(Protocol):
      def get_by_owner(user_id: str) -> dict: ...
      # Returns the single company owned by this user (MVP: 1 company per user).
      # Raises RLSForbiddenError if no row matches.

  class AccountsRepo(Protocol):
      def list_for_company(company_id: str) -> dict[str, str]: ...
      # Returns {column_header: category_name} map for auto-mapping next upload.
      def upsert_mapping(company_id: str, column: str, category: str) -> None: ...
  ```

  - **Blocks:** Adapters (implement these signatures verbatim), agents (depend on these — never on concrete classes).
- [ ] `domain/errors.py` — exception taxonomy. Full list per CLAUDE.md:
  - `TransientIOError` — adapters, after retries exhausted on network/5xx
  - `DuplicateEntryError` — unique-constraint violation on `monthly_entries`
  - `RLSForbiddenError` — RLS denies a row
  - `GuardrailError` — interpreter, after 2 guardrail attempts
  - `InvalidRunTransition` — `RunStateMachine.transition()` on illegal move
  - `FileHasNoValidColumns` — PII sanitizer stripped everything
  - `MappingAmbiguous` — Haiku returns <80% confidence (Day 2 uses this)
  - **Why:** User-facing strings live in `messages.py`; this file holds types only.
- [ ] `domain/run_state_machine.py` — `RunStatus` enum + allowed-transitions table + `RunStateMachine.transition(run, new_status)` which raises `InvalidRunTransition` on illegal moves.
  - **Happy path:** `pending → parsing → mapping → comparing → generating → complete`
  - **Failure transitions** (all terminal — cannot be left):
    - `pending → upload_failed` (Storage upload exhausted retries)
    - `parsing → parsing_failed` (any pre-mapping failure: pandera error, FileHasNoValidColumns, Haiku unreachable)
    - `mapping → parsing_failed` (mid-mapping crash; same terminal as parsing-stage failures)
    - `comparing → parsing_failed` (Comparison crash — `comparing_failed` is post-MVP; see risks.md R-012)
    - `generating → guardrail_failed` (Interpreter exhausted 2 guardrail attempts)
  - **Terminal states are immutable** — `complete`, `upload_failed`, `parsing_failed`, `guardrail_failed` cannot transition to anything. Retry creates a **new** `run_id`.
  - **Why:** Every `runs.status` write goes through this class — enforces valid state machine without scattering checks across agents.
  - **Exception name:** `InvalidRunTransition` (canonical). Never `InvalidTransition`.
  - **Blocks:** Every agent that updates run status.

### 3. Database — Schema + RLS

- [ ] Create Supabase project (if not already); capture `SUPABASE_URL` + `SUPABASE_SERVICE_KEY` into `.env`
- [ ] `backend/db/schema.sql` — **7 tables** per `db-schema.md`:
  1. `companies` (with `owner_id → auth.users(id)`)
  2. `account_categories` (seeded: REVENUE, COGS, OPEX, G&A, R&D, OTHER_INCOME, **OTHER**)
  3. `accounts`
  4. `monthly_entries` (with `UNIQUE(company_id, account_id, period)` + `source_column TEXT`)
  5. `anomalies`
  6. `reports`
  7. `runs` (with `storage_key TEXT` populated by `POST /upload`)
  - Indexes: `idx_companies_owner`, `idx_monthly_entries_company_period`, `idx_anomalies_company_period`, `idx_runs_company_period`
  - **Why:** Unique constraint on `monthly_entries` enforces dup-upload detection (DELETE-then-INSERT on Day 2 keeps it compatible). `source_column` records the original file column header per row for provenance tooltips (Day 4). `storage_key` enables Retry Analysis (Day 4) without re-upload.
- [ ] Seed `account_categories` with the **7** values (REVENUE, COGS, OPEX, G&A, R&D, OTHER_INCOME, OTHER) via `ON CONFLICT DO NOTHING`. **OTHER is id=7 by insertion order** — used by Parser as the catch-all for low-confidence Haiku mappings. **SKIP is NOT seeded** — it is a frontend-only sentinel in MappingConfirmModal meaning "do not import this column".
- [ ] **Enable RLS** on every company-owning table: `companies`, `accounts`, `monthly_entries`, `anomalies`, `reports`, `runs`. `account_categories` has no RLS (public lookup).
- [ ] Write RLS policies:
  - `companies`: `USING (owner_id = auth.uid()) WITH CHECK (owner_id = auth.uid())`
  - All other tables: EXISTS-through-`companies` pattern (verify `c.id = {table}.company_id AND c.owner_id = auth.uid()`)
- [ ] Run the schema: `supabase db push` (or `psql $DATABASE_URL -f schema.sql`)

### 4. Authentication + Demo Data

- [ ] Enable Supabase Auth — email + password provider
- [ ] Create demo user `demo@dronedemo.com` (remember the user UUID — needed for the next step)
- [ ] Insert DRONE Inc. row into `companies` with `owner_id = <demo_user_uuid>`, `name = 'DRONE Inc.'`, `currency = 'USD'`
  - **Note:** Demo company is "DRONE Inc." (per project instructions). `company_id` is a UUID — never a string slug.

### 5. Supabase Storage

- [ ] Create Storage bucket `financial-uploads` (private, not public)
- [ ] Storage RLS policy: files scoped to user folder
  ```sql
  CREATE POLICY "user_owns_upload" ON storage.objects
  FOR ALL USING (
    bucket_id = 'financial-uploads'
    AND (storage.foldername(name))[1] = auth.uid()::text
  );
  ```
- [ ] Folder layout: `financial-uploads/{auth.uid()}/{period}/{filename}`
  - **Why (per `db-schema.md`):** folder keyed on `auth.uid()`, NOT `company_id` — simpler RLS, since each demo user owns exactly one company.

### 6. Adapters (I/O — the only layer that imports SDKs)

- [ ] `adapters/supabase_repos.py` — all 6 repo implementations share one Supabase client. Hybrid return-type policy (per CLAUDE.md):
  - Return dataclasses: `EntriesRepo`, `AnomaliesRepo`, `ReportsRepo`
  - Return dicts: `CompaniesRepo`, `AccountsRepo`, `RunsRepo`
  - **Why:** Hot-path entities benefit from strict typing; one-shot lookups don't.
- [ ] `adapters/supabase_storage.py` — `FileStorage` port backed by `storage.objects`. **Upload retry rule:**
  - 3 attempts total
  - Backoff 0.5s → 1.5s → 4s with ±20% jitter
  - Retry only on network-class errors: `httpx.ConnectError`, `ReadTimeout`, 5xx responses. NOT on 4xx.
  - After 3 failures: raise `TransientIOError`. Use case transitions run to `upload_failed`; user re-uploads (no checkpoint resume).
- [ ] `adapters/anthropic_llm.py` — `LLMClient` port. Loads prompts from `prompts/` by filename. Logs git SHA of the prompt file with each call.
  - Network retry only; no semantic retry here (semantic retry = guardrail's job in Day 3).
  - **Note:** Can ship as a stub today; Day 2 wires it to Haiku, Day 3 wires it to Opus.
- [ ] `adapters/resend_email.py` — `EmailSender` port scaffold. No wiring today; Day 5 fully integrates.

### 7. API Layer

- [ ] `api/middleware.py` — `trace_id` middleware. Generates a UUID per request (or reads inbound `X-Trace-Id`), stamps into the contextvar, includes in every response header.
- [ ] `api/auth.py` — JWT validation dependency. Reads `Authorization: Bearer <supabase_jwt>`, validates signature + expiry, resolves `user_id → company_id` via `companies.owner_id`. Never accept `company_id` from client.
  - Unauthorized → 401 with `messages.UNAUTHORIZED`
  - User does not own requested company → 403 with `messages.FORBIDDEN`
- [ ] `api/deps.py` — builds adapters once (module-level or lifespan), injects into agents via FastAPI `Depends`. This is the **only place** wire-up happens.
- [ ] `api/rate_limit.py` — slowapi `Limiter` instance + composite `key_func` (`user_id` if JWT present, else IP). In-memory backend (single Railway container). 429 returns `Retry-After` header + JSON body with `messages.RATE_LIMITED`. Frontend disables the action for `retry_after_seconds` and shows a countdown.
  - **Note:** Redis is post-MVP.
- [ ] CORS config in `main.py`: allow `http://localhost:5173` and `os.getenv("FRONTEND_URL", "")`
  - **Why (per `api.md`):** Forgetting this causes silent Day 4 failures. Test with a cross-origin request from Bruno on Day 3.
- [ ] `api/routes.py` — router skeleton with placeholder endpoints
- [ ] `GET /health` — `{"status": "ok"}`, uncapped (no rate limit, no auth)
- [ ] `POST /upload` — thin handler:
  - Multipart: `files: File[]`, `period: string` (ISO date)
  - Derives `company_id` from JWT (never accepts from client)
  - Writes file(s) to Supabase Storage via `FileStorage` adapter (uses retry)
  - Creates `runs` row with `status=pending` (via `RunStateMachine`)
  - **Persists `storage_key` on the `runs` row** (full path of the uploaded file). Required by
    `POST /runs/{run_id}/retry` (Day 4) to re-run the pipeline without forcing a re-upload.
    If multiple files are uploaded in one request, store the first file's storage_key (MVP —
    multi-file retry is post-MVP).
  - Returns `{run_id, status, files_received, message}`
  - Rate limit: 5/min per user, 20/hour per user; 10/min fallback per IP

### 8. Tools (Stateless Helpers)

- [ ] `tools/file_reader.py` — format detection + reader.
  - `.xlsx` / `.xlsm` → openpyxl
  - `.csv` → pandas
  - `.xls` → check first 2 bytes: `b"<?"` → XML Spreadsheet 2003 (NetSuite edge case, parse as XML); else → xlrd binary
  - **Why:** NetSuite's default Export button produces `.xls` files that are actually XML Spreadsheet 2003. openpyxl cannot open them.
  - **XML Spreadsheet 2003 parse path** (NetSuite branch):
    - Namespace: `xmlns="urn:schemas-microsoft-com:office:spreadsheet"`
    - Element path: `Workbook > Worksheet > Table > Row > Cell > Data`
    - Skip the first `Row` if `ss:Index` attribute is **absent on all cells** (metadata row heuristic — title banner / generation timestamp).
    - `Data` element with `ss:Type="Number"` → `float()`; `ss:Type="String"` → `str()`. Other types unchanged.
    - **Fall back to xlrd** if XML parse raises `ParseError` (some NetSuite exports are misnamed real `.xls` binaries).
- [ ] `tools/pii_sanitizer.py` — **critical, must ship Day 1.**
  - **Header blacklist** — case-insensitive substring match. **Authoritative list (must implement verbatim, copied from `agent-flow.md` §Agent 1 Step 4):**

    | Category | Trigger condition | Substrings (case-insensitive substring match) |
    |---|---|---|
    | SSN / Tax ID | always | `ssn`, `social_security`, `social security`, `taxpayer_id`, `tax_id`, `tin` |
    | Date of Birth | always | `dob`, `date_of_birth`, `date of birth`, `birth_date`, `birthdate`, `birthday` |
    | Personal Name | **only when an `employee_id` column exists in the same sheet** | `first_name`, `last_name`, `full_name`, `employee_name`, `personal_name` |
    | Home Address | always | `home_address`, `residence`, `street_address`, `zip_code`, `postal_code`, `mailing_address` |
    | Bank Account / Routing | always | `bank_account`, `account_number`, `routing_number`, `iban`, `swift_code`, `aba_routing` |
    | Personal Contact | always | `phone_number`, `mobile_phone`, `cell_phone`, `personal_email`, `home_phone`, `home_email` |

    **Conservative bias:** bare `name`, `address`, `phone`, `email`, `account` are intentionally **not in the blacklist** — they are common in legitimate finance files (`vendor_name`, `billing_address`, `account_number_balance`, etc.). False-negative risk is mitigated by the SSN value-level regex below.
  - Matched columns are **dropped entirely** — no hashing.
  - **Value-level fallback, SSN only:** regex `^\d{3}-?\d{2}-?\d{4}$`. If an unmapped column has ≥20% of non-null values matching, drop it.
  - Emits a structured log at INFO level: `event="pii_sanitization"` with `trace_id`, `run_id`, `columns_dropped` (header names), `rows_in_file`, `strategy`. **Cell values are never logged.**
  - If all columns are stripped: raise `FileHasNoValidColumns` → surfaces as `messages.FILE_HAS_NO_VALID_COLUMNS`.
  - **Why ship Day 1:** Day 2 Parser invokes it before pandera and before any Claude call. Forgetting it = PII leak to Anthropic = disqualifying.
- [ ] `tools/validator.py` — pandera schema. Columns: `amount: float`, `period: date`, `account: str`. Plain-English error on failure (surface via `messages.PARSE_FAILED`).

---

## Internal Sequencing

Strict order matters today — most tasks have dependency cascades.

1. **Project scaffold + infrastructure (1, 2)** — pure Python, no external dependencies. Domain layer, messages, logger, settings.
   - Do first: everything else depends on these.
2. **Domain contracts + state machine** — freeze `PandasSummary`, `NarrativeJSON`, `RunStatus`. Day 2 and 3 cannot start until these are frozen.
3. **Database (3) + Auth + Demo data (4)** — Supabase project must exist before adapters can connect. RLS policies must land before any insert.
4. **Storage bucket + policy (5)** — needed before `POST /upload` can write files.
5. **Adapters (6)** — depend on `domain.ports`. `supabase_repos.py` + `supabase_storage.py` are mandatory today; `anthropic_llm.py` can be a stub.
6. **API layer (7)** — depends on adapters via `deps.py`. Order inside the layer: `middleware.py` → `auth.py` → `rate_limit.py` → `deps.py` → `routes.py` → endpoints.
7. **Tools (8)** — `pii_sanitizer.py` before `validator.py` (pandera runs on sanitized data). Can be developed in parallel with API layer once scaffold is ready.
8. **Integration smoke test** — wire `POST /upload` → Storage → Runs repo → file_reader → pii_sanitizer → pandera. Print DataFrame.

Rule of thumb: **everything pure-Python before anything I/O.** A mistake in `domain/ports.py` cascades into every adapter, so lock `ports.py` early.

---

## Contracts Produced Today

These are frozen at end of Day 1. Day 2 and beyond cannot change them without a migration discussion.

### Pydantic contracts (`domain/contracts.py`)

All models are **Pydantic v2** (use `model_dump()`, `model_validate()`).

```python
class AccountSummary(BaseModel):
    account: str
    category: str            # REVENUE | COGS | OPEX | G&A | R&D | OTHER_INCOME | OTHER
    current: float
    historical_avg: float    # 0.0 when severity == "no_history"
    variance_pct: float      # 0.0 when severity == "no_history"
    severity: str            # low | medium | high | no_history

class PandasSummary(BaseModel):
    # Comparison agent emits this; Interpreter consumes; guardrail flattens.
    accounts: dict[str, AccountSummary]
    period: date
    company_id: UUID

class NarrativeJSON(BaseModel):
    # Opus output before guardrail. Every value in `numbers_used` must
    # match a leaf in PandasSummary within 2% (verified by tools/guardrail.py).
    narrative: str
    numbers_used: list[float]

class MappingOutput(BaseModel):
    # Single Haiku mapping result for one column.
    column: str
    mapped_to: str           # category name OR "SKIP" (frontend-only sentinel)
    confidence: float        # 0.0–1.0; <0.80 flags for MappingConfirmModal

class ParserOutput(BaseModel):
    # Parser agent's in-memory return shape. Not persisted.
    status: str                              # "success" | "parsing_failed"
    file_format: str                         # xlsx | csv | xls_binary | xml_spreadsheet
    rows_parsed: int
    new_accounts_created: int
    warnings: list[str]
    low_confidence_columns: list[MappingOutput]

class SendResult(BaseModel):
    # Resend adapter return shape. Day 5 wires; Day 1 scaffolds.
    status: str              # "sent" | "failed"
    message_id: str          # empty string when status == "failed"
```

### State machine (`domain/run_state_machine.py`)

```
RunStatus: pending, parsing, mapping, comparing, generating, complete,
           upload_failed, parsing_failed, guardrail_failed
```

### Exception taxonomy (`domain/errors.py`)

`TransientIOError`, `DuplicateEntryError`, `RLSForbiddenError`, `GuardrailError`, `InvalidRunTransition`, `FileHasNoValidColumns`, `MappingAmbiguous`

### API surface (Day 1 portion)

- `GET /health` → `{"status": "ok"}`
- `POST /upload` → `{run_id: UUID, status: "processing", files_received: int, message: str}`

### Storage layout

```
financial-uploads/{auth.uid()}/{period}/{filename}
```

`period` = ISO date string, first of month (e.g. `2026-03-01`)

### `messages.py` keys (minimum set)

`UNAUTHORIZED`, `FORBIDDEN`, `UNSUPPORTED_FORMAT`, `PARSE_FAILED`, `MAPPING_FAILED`, `GUARDRAIL_FAILED`, `NOT_FOUND`, `MAIL_FAILED`, `RATE_LIMITED`, `FILE_HAS_NO_VALID_COLUMNS`

---

## Cut Line

If time runs short, cut in this order — most critical items stay.

### Must ship today (non-negotiable)
- Folder structure + domain layer (entities, contracts, ports, errors, run_state_machine) — **blocks Day 2**
- Supabase schema + RLS + Auth + demo user + DRONE Inc. row
- Storage bucket + Storage RLS policy
- `messages.py`, `logger.py`, `settings.py`, `main.py` with CORS + middleware
- `api/auth.py` JWT validator
- `supabase_repos.py` (at minimum `RunsRepo` + `CompaniesRepo` + `EntriesRepo`)
- `supabase_storage.py` with retry
- `POST /upload` end-to-end
- `tools/pii_sanitizer.py` + `tools/file_reader.py` + `tools/validator.py`

### Deferrable to Day 2 morning (low-risk slip)
- `anthropic_llm.py` beyond a stub (Day 2 wires Haiku; Day 3 wires Opus — stub fine for tonight)
- `adapters/resend_email.py` scaffold (Day 5 anyway)
- `api/rate_limit.py` wiring on endpoints — Limiter instance mandatory, per-route decorators can slip to Day 3

### Defer to Day 3
- Any non-`/upload`, non-`/health` endpoint (they belong to Day 3)

### Post-MVP (per scope.md)
- Redis-backed rate limiting (in-memory is week-1)
- pgvector (SQL joins only for history)

---

## Risks (this day)

| Risk | Impact | Mitigation |
|---|---|---|
| Clean Architecture setup slips | Cascades into Days 2–6 | Ship minimal domain + one adapter per port today; refine shapes mid-sprint if needed |
| RLS policies wrong | Data leaks between users; demo liability | Write RLS test on Day 5 (second user cannot see DRONE data); test with two JWTs before end of Day 1 |
| Supabase Storage RLS misconfigured | Files accessible across users | Test with `auth.uid()::text` cast; test upload + download with two users before end of Day 1 |
| PII sanitizer forgotten | PII reaches Anthropic on Day 2 → disqualifying | Explicit task today; integration in Day 2 Parser; E2E test on Day 5 |
| JWT validation brittle | Every protected endpoint fails; Day 4 frontend can't log in | Test with a real `supabase.auth.signInWithPassword` token from a Supabase Studio session |
| `PandasSummary` / `NarrativeJSON` shapes wrong | Day 2 emission and Day 3 guardrail both break | Freeze shapes end of Day 1; Day 2/3 get contract-first scaffolding |
| CORS misconfigured | Silent Day 4 failure per `api.md` | Allowlist `http://localhost:5173` + `FRONTEND_URL`; test cross-origin from Bruno on Day 3 |
| Dependency version drift (xlrd 2.x breaks `.xls`) | NetSuite edge case silently fails | Pin `xlrd==1.2.0` in `requirements.txt` |
| Schema forgets `runs` table | Day 2/3 can't transition state or update progress | Explicit checklist item in §3 above |

Cross-day risks (tracked in `risks.md`): Railway cold-start, Resend verified-sender delay, frontend component sprawl on Day 4, `MappingConfirmModal` contract gap.

---

## Reference Docs

Read these sections before starting Day 1 tasks.

- **`CLAUDE.md`** (repo root) — Project Structure, Database Tables, Repo Layer (return-type policy), Retry & Error Handling, Storage cleanup
- **`docs/scope.md`** — MVP Scope (Storage, RLS, rate limiting, PII, run state machine, messages.py), Architectural Constraints
- **`docs/tech-stack.md`** — Architecture Layers (lightweight ports & adapters), Folder Structure
- **`docs/agent-flow.md`** — Parser Step 0 (format detection), Step 1-7 pipeline order, NetSuite edge case
- **`docs/db-schema.md`** — all 7 tables, indexes, Row Level Security, File Storage (bucket + RLS)
- **`docs/api.md`** — Authentication (JWT → company_id), `POST /upload`, CORS Configuration
- **`docs/design.md`** — Number Formatting Standards (used everywhere, Day 4 centralizes)
