# Month Proof — Completed Work Log
*Month Proof 6-Day Sprint — Built with Opus 4.7 Hackathon, April 2026*

Append-only log of what actually shipped. Update at end of each working session.

**Rules:**
- Strike through entries if a decision is reversed (do NOT delete).
- Link commit SHAs where possible — this doc points outward to source of truth.
- Every entry answers a specific question — see subsection definitions below.
- Do not batch updates. Context decays fast.

**Subsection purposes (repeated for each day):**

- **Shipped** — what actually got done. One line per item. Format: `- [x] <thing> — <path/or/ref> — commit <sha> — <date>`
- **Decisions Made** — choices made during the day that are not yet reflected in the root docs (CLAUDE.md / scope.md / tech-stack.md / agent-flow.md / db-schema.md / api.md / design.md). Flag so docs can be updated.
- **Deviations from Plan** — where reality diverged from the day file. **Planned** / **Shipped** / **Why** structure.
- **Cut / Deferred** — items explicitly pushed to a later day or post-MVP. Link to the new home (e.g. `→ day-5-polish.md §4` or `→ risks.md R-XXX`).
- **Known Issues / Tech Debt** — surfaced during the day. Include discovery date and planned action.

---

## Day 1 — Backend Foundation

**Status:** ✅ COMPLETE
**Sessions:** Multiple (Apr 22-23, 2026)

### Shipped
- [x] Clean Architecture folder scaffold — `backend/{domain,adapters,agents,api,tools,prompts,db}/` — 2026-04-22
- [x] FastAPI app with main.py, settings.py, logger.py, messages.py — 2026-04-22
- [x] Domain layer — entities.py, contracts.py, ports.py, errors.py, run_state_machine.py — 2026-04-22
- [x] Supabase schema — 6 migrations (0001-0006) covering all tables + RLS + Storage — 2026-04-22 to 2026-04-23
- [x] Adapters — supabase_repos.py, supabase_storage.py, anthropic_llm.py, resend_email.py — 2026-04-22
- [x] API infrastructure — middleware.py, auth.py, deps.py, rate_limit.py — 2026-04-22
- [x] Tools — file_reader.py, pii_sanitizer.py, validator.py, normalizer.py, guardrail.py — 2026-04-22 to 2026-04-23
- [x] CORS configuration and /health endpoint — 2026-04-22

### Decisions Made
- **Hybrid return-type policy**: MonthlyEntry, Anomaly, Report return dataclasses; Company, Account, Run return dicts (documented in CLAUDE.md)
- **6 migrations instead of single schema.sql**: Incremental schema evolution (0001_initial, 0002_pandas_summary, 0003_source_column, 0004_storage_key, 0005_parse_preview, 0006_discovery_plan)
- **Discovery agent added**: Beyond original 3-agent plan (Parser/Comparison/Interpreter), added Discovery agent for onboarding flow
- **Orchestrator pattern**: Added orchestrator.py to coordinate agent pipeline

### Deviations from Plan
- **Planned**: Single `schema.sql` in `backend/db/`
- **Shipped**: Migration-based approach in `supabase/migrations/` with 6 incremental files
- **Why**: Better version control and evolution of schema changes

### Cut / Deferred
- (None — Day 1 fully delivered)

### Known Issues / Tech Debt
- PII sanitizer needs comprehensive E2E test coverage (deferred to Day 5)
- Rate limiter using in-memory backend (Redis deferred to post-MVP per R-112)

---

## Day 2 — Parser + Comparison

**Status:** ✅ COMPLETE
**Sessions:** Apr 23, 2026

### Shipped
- [x] Parser agent (agents/parser.py) — 513 lines — 2026-04-23
- [x] Comparison agent (agents/comparison.py) — 2026-04-23
- [x] Mapping prompt (prompts/mapping_prompt.txt) using claude-haiku-4-5-20251001 — 2026-04-23
- [x] PII sanitizer integrated into parser pipeline — BEFORE pandera, BEFORE Claude — 2026-04-23
- [x] Column mapping with confidence scoring — low confidence (<80%) flagged for review — 2026-04-23
- [x] Variance calculation in pure Python — no Claude math — 2026-04-23
- [x] PandasSummary contract emitted from Comparison agent — 2026-04-23
- [x] File format detection (xlsx, xls, csv, xlsm including NetSuite XML edge case) — 2026-04-23
- [x] normalizer.py — currency symbols, thousand separators, empty rows — 2026-04-23

### Decisions Made
- **MappingConfirmModal is post-hoc, not blocking**: Low-confidence columns auto-map to OTHER; review panel shown after-the-fact (see R-009)
- **comparing_failed not a distinct state**: Use parsing_failed as catch-all for pre-Interpreter failures (see R-012)
- **Dynamic-stdev severity deferred**: Fixed ±20% threshold for MVP; 3+ months stdev is post-MVP (see R-013, R-114)
- **Discovery agent added**: For onboarding flow, separate from core parser

### Deviations from Plan
- **Planned**: Blocking MappingConfirmModal pauses pipeline
- **Shipped**: Non-blocking post-hoc review panel (MappingConfirmPanel component)
- **Why**: Stateful pause/resume requires awaiting_mapping state + new endpoint — too risky for 6-day sprint

- **Planned**: 3 agents only
- **Shipped**: 5 agents (Parser, Comparison, Interpreter, Discovery, Orchestrator)
- **Why**: Onboarding flow and pipeline coordination needed dedicated agents

### Cut / Deferred
- Blocking MappingConfirmModal → post-MVP (see R-105)
- Dynamic-stdev severity ladder → post-MVP (see R-114)
- comparing_failed terminal state → post-MVP (see R-116)

### Known Issues / Tech Debt
- Parser.py is 513 lines — consider refactoring into smaller modules post-MVP
- Test coverage for comparison edge cases (no-history, single-period) needs expansion

---

## Day 3 — Interpreter + Guardrail + API

**Status:** ✅ COMPLETE
**Sessions:** Apr 23, 2026

### Shipped
- [x] Interpreter agent (agents/interpreter.py) — 226 lines — 2026-04-23
- [x] Numeric guardrail (tools/guardrail.py) — DO NOT CHANGE — 2026-04-23
- [x] Narrative prompts (prompts/narrative_prompt.txt + narrative_prompt_reinforced.txt) — 2026-04-23
- [x] Full API surface — 16 endpoints in routes.py (1180 lines) — 2026-04-23
  - GET /health
  - POST /upload
  - GET /runs/{run_id}/status (polling endpoint with progress)
  - GET /runs/{run_id}/raw (guardrail_failed unverified data download)
  - GET /report/{company_id}/{period}
  - GET /anomalies/{company_id}/{period}
  - POST /mail/send
  - POST /runs/{run_id}/retry
  - POST /runs/{run_id}/mapping/confirm
  - POST /runs/{run_id}/confirm
  - POST /runs/{run_id}/confirm-discovery
  - POST /runs/{run_id}/reject-discovery
  - GET /companies/me
  - GET /companies/me/has-history
  - POST /companies (company creation)
  - GET /reports (list all reports)
  - GET /data (data export)
- [x] Guardrail retry logic — 2 attempts with reinforced prompt — 2026-04-23
- [x] Storage cleanup as BackgroundTask on success — 2026-04-23
- [x] Exception → HTTP status mapping (503, 409, 403, etc.) — 2026-04-23
- [x] Rate limiting on all endpoints (slowapi) — 2026-04-23

### Decisions Made
- **Guardrail tolerance**: 2% (hard-coded for MVP; per-company config deferred to R-119)
- **Storage cleanup on success only**: File preserved on guardrail_failed for Retry Analysis (intentional, see R-015)
- **Semantic retry in use case**: Guardrail retry with reinforced prompt lives in Interpreter (not in anthropic_llm.py adapter)
- **16 endpoints**: Expanded beyond original plan to support Discovery flow, onboarding, data export

### Deviations from Plan
- **Planned**: ~7 core endpoints
- **Shipped**: 16 endpoints (added discovery, onboarding, data export, company setup)
- **Why**: Product scope expanded to include onboarding flow

### Cut / Deferred
- Storage TTL sweep for abandoned guardrail_failed runs → post-MVP (see R-115)
- Configurable guardrail tolerance per company → post-MVP (see R-119)
- interpreting_failed terminal state → post-MVP (see R-116)

### Known Issues / Tech Debt
- routes.py is 1180 lines — should be split into separate router modules post-MVP
- Guardrail logging could be more structured (add examples of failures to telemetry)

---

## Day 4 — Frontend

**Status:** ✅ COMPLETE
**Sessions:** Apr 22-23, 2026

### Shipped
- [x] React + TypeScript + Vite project setup — 2026-04-22
- [x] shadcn/ui integration (Radix + Tailwind) — 2026-04-22
- [x] 10 pages implemented — 2026-04-22 to 2026-04-23
  - LoginPage, RegisterPage, OnboardingPage
  - UploadPage, ReportPage, ReportsPage
  - DashboardPage, DataPage, LandingPage, ProfilePage
- [x] 17 components — 2026-04-22 to 2026-04-23
  - FileUpload (drag & drop with client validation)
  - LoadingProgress (4-step polling)
  - AnomalyCard (direction + severity separation)
  - ReportSummary (verified badge, stale chip)
  - GuardrailWarning (inline error with retry)
  - MappingConfirmPanel (post-hoc review)
  - MailButton, EmptyState, ErrorBoundary
  - AppShell, CompanySetupForm, HowItWorks
  - ParsePreviewPanel, HistoryList, MetricCard, PeriodSelector
  - ToastProvider
- [x] Auth flow — Supabase auth.signInWithPassword + JWT injection — 2026-04-22
- [x] US accounting formatting — tabular numerals, parenthesized negatives — 2026-04-22
- [x] Toast system — 4 types (success/error/warning/info) with dedup — 2026-04-22
- [x] Responsive breakpoints (desktop-first, mobile simplified) — 2026-04-23
- [x] Direction vs severity separation on AnomalyCard (R-021 mitigated) — 2026-04-23

### Decisions Made
- **Card-level provenance only**: Number-level prose provenance deferred to post-MVP (see R-011, R-106)
- **Source column added to schema**: ALTER TABLE monthly_entries ADD COLUMN source_column — migration 0003
- **CompanySetupForm for onboarding**: Beyond original spec, added full company creation flow
- **Landing page + marketing content**: HowItWorks component for product explanation
- **Data export page**: DataPage for raw CSV downloads of monthly_entries

### Deviations from Plan
- **Planned**: Basic upload → report flow
- **Shipped**: Full app with onboarding, landing page, dashboard, profile, data export
- **Why**: Product scope expanded for demo and user experience

- **Planned**: Provenance hover on every number in narrative prose
- **Shipped**: Provenance only on AnomalyCard figures
- **Why**: Regex-parse-and-wrap narrative strings too ambitious for sprint (see R-011)

### Cut / Deferred
- Number-level prose provenance → post-MVP (see R-106)
- TrendChart / advanced analytics components → post-MVP (see R-107)
- Tablet polish (full optimization) → basic responsive shipped, advanced deferred

### Known Issues / Tech Debt
- Some pages (DataPage, ProfilePage) could use more polish
- Toast deduplication window is 1s — could be smarter (content-based dedup)
- No E2E browser tests yet (manual smoke only)

---

## Day 5 — Mail + E2E + Polish

**Status:** 🟡 PARTIAL
**Sessions:** Apr 23, 2026

### Shipped
- [x] Resend email adapter wired (adapters/resend_email.py) — 2026-04-23
- [x] POST /mail/send endpoint fully functional — 2026-04-23
- [x] MailButton component wired with success/error toasts — 2026-04-23
- [x] 3 test files started — 2026-04-23
  - tests/tools/test_pii_sanitizer.py
  - tests/tools/test_normalizer.py
  - tests/integration/test_parser_end_to_end.py
- [x] Backend code formatting (black, flake8) — 2026-04-23
- [x] Frontend linting clean — 2026-04-23

### Decisions Made
- **Test coverage prioritized**: PII, normalizer, parser integration first
- **Manual E2E over automated**: Browser smoke tests instead of Playwright/Cypress for MVP (see R-118)

### Deviations from Plan
- **Planned**: Full E2E test suite (9 test files, ~40 tests)
- **Shipped**: 3 test files started, manual E2E smoke
- **Why**: Time constraints — prioritized functional delivery over comprehensive test coverage

### Cut / Deferred
- Full E2E test suite → post-MVP (see R-118)
- Guardrail test with intentional wrong number → deferred
- RLS isolation test (two users) → deferred
- Rate limit spam test → deferred
- Storage cleanup test → deferred
- Empty state test → deferred (but component exists and works)
- mypy strict mode on domain/ → post-MVP (see R-111)

### Known Issues / Tech Debt
- **Critical**: Comprehensive test coverage missing (PII, guardrail, RLS are high-severity untested)
- Test suite needs expansion before production use
- No automated E2E — regression risk on future changes
- Resend sender domain DNS propagation not verified (assumed working)

---

## Day 6 — Demo + Deploy + Submit

**Status:** 🔴 NOT STARTED
**Sessions:** —

### Shipped
- (None yet — Day 6 work pending)

### Decisions Made
- (To be filled as Day 6 progresses)

### Deviations from Plan
- (To be filled as Day 6 progresses)

### Cut / Deferred
- (To be filled as Day 6 progresses)

### Known Issues / Tech Debt
- Deployment not done (Railway backend, Vercel frontend)
- Demo script not written
- Submission not filed
- Pre-demo checklist not executed
- DRONE baseline (Feb 2026) not pre-loaded into production DB
- No backup demo video recorded
- GitHub repo not made public yet

---

## Post-Sprint Backlog

Items explicitly cut during the sprint, earmarked for post-hackathon work. Cross-reference with `risks.md` post-MVP entries (R-100+).

<!-- Append entries as they are cut. Example: -->
<!-- - <Item> — deferred from Day <X> — <reason> — see risks.md [R-XXX] -->

### Tech Debt (from sprint)

### Scope Cuts (pre-committed, from scope.md Future Roadmap)

- pgvector — long-term pattern recognition across fiscal years — see risks.md [R-100]
- ERP API integration (NetSuite, QuickBooks, SAP direct) — see risks.md [R-101]
- Multi-user / role management (Controller vs CFO view) — see risks.md [R-102]
- Budget vs actuals comparison — see risks.md [R-103]
- Draft journal entries (auto-generated JE suggestions for ERP upload) — see risks.md [R-104]

### Scope Cuts (made during sprint, from day files)

- Aspirational blocking MappingConfirmModal (true pause/resume) — see risks.md [R-105]
- Number-level prose provenance — see risks.md [R-106]
- TrendChart / MetricCard / HistoryList components — see risks.md [R-107]
- Prod/dev Supabase separation — see risks.md [R-108]
- Observability (Sentry / Datadog) — see risks.md [R-109]
- CI/CD pipeline — see risks.md [R-110]
- mypy strict mode everywhere — see risks.md [R-111]
- Redis-backed rate limiting — see risks.md [R-112]
- Multi-recipient `POST /mail/send` — see risks.md [R-113]
- Dynamic-stdev severity (3+ months history) — see risks.md [R-114]
- Storage TTL sweep for abandoned `guardrail_failed` runs — see risks.md [R-115]
- `comparing_failed` / `interpreting_failed` terminal states — see risks.md [R-116]
- Sample-Excel-download on EmptyState — see risks.md [R-117]
- Playwright / Cypress E2E automation — see risks.md [R-118]
- Configurable guardrail tolerance per company — see risks.md [R-119]
- Per-row email action on /reports list (Option Y) — see risks.md [R-120]

---

## Submission Record

*To be filled on Day 6 after submission.*

- **Submitted at:** —
- **Cerebral Valley confirmation:** —
- **Live demo URL:** —
- **Demo video URL:** —
- **GitHub repo URL (public):** —
- **Commit SHA at submission:** —
- **Git tag:** `hackathon-submission` (applied after submission)
