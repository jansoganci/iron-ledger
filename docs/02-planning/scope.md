# Month Proof — Scope Document
*Built with Opus 4.7 Hackathon — April 2026*
*v2 — US market focus, market data, and input list updated*

---

## One-Line Definition

Drop your messy financial files → agent finds errors, compares to history, writes the report, sends the mail.

---

## Problem

US finance teams spend 10-15 hours every month-end close on tasks that should take minutes:

- Pulling ERP exports (NetSuite, QuickBooks, SAP) into Excel manually
- Copy-pasting across 5-10 fragmented files from different departments
- Building VLOOKUP formulas to reconcile GL to sub-ledgers
- Writing variance commentary by hand
- Errors surface at the end — after hours of work

**The person doing this is either the company owner, a part-time controller, or a small finance team with no dedicated FP&A staff.**

### Market Data (Use for Demo)

- 87% of CFOs say "AI will be extremely important to finance in 2026" — but only 14% have integrated AI agents into finance (Deloitte CFO Signals, Q4 2025)
- 33% of SAP finance teams see month-end close as the biggest pain point — but only 15% use automated solutions (SAPinsider)
- 36% of C-suite leaders identify "manual error detection during close" as the biggest issue (BlackLine global survey)
- Manual reconciliation workload drops by 60-70% with automation (AICPA Continuous Finance Survey)

**Gap:** Enterprise tools (FloQast, BlackLine) require months of setup, are expensive, and are not SMB-friendly. Month Proof: drop files, get report.

---

## Target User

**Primary:** US-based finance analyst or controller (small/mid-sized company)
- Spends 10-15 hours/month on month-end close
- Works in NetSuite, QuickBooks, SAP, or Excel-native workflows
- Understands finance terms but has no access to FP&A tools

**Secondary:** CFO or business owner (reads report, makes decisions)

**Target Market:** 70% US, 30% Canada / UK / Australia

---

## Accepted Input Files

Standard files used by US finance teams during monthly close:

| File Type | Format | Source |
|---|---|---|
| P&L / Income Statement | .xlsx, .csv | NetSuite, QuickBooks, SAP |
| Budget vs Actuals | .xlsx | Manual FP&A template |
| Trial Balance | .xlsx, .csv | Any ERP |
| Payroll Register | .xlsx, .csv | ADP, Gusto, Paychex |
| Expense Report | .xlsx, .csv | Concur, Expensify |
| Prior period file | .xlsx | Prior period comparison |

Multiple files can be uploaded at once. Revenue and expenses may come separately. The agent merges them.

---

## Core User Flow

### First Use (Baseline Setup)
1. User uploads prior 1-3 months of files
2. Agent reads files, maps to US GAAP categories, writes to Supabase
3. Reference baseline is created

### Monthly Use
1. User uploads this month's files (can be multiple files)
2. Agent merges and normalizes files
3. Python: calculates variance against historical data
4. Python: detects anomalies and errors
5. Claude: writes plain-language report
6. Numeric guardrail: verifies mathematical accuracy of report
7. Visualizes in dashboard
8. Sends email

---

## MVP Scope

### INCLUDED ✅
- Multi-file upload (.xlsx, .csv, .xls, .xlsm)
- Format flexibility — agent reads whatever arrives
- US GAAP category mapping: REVENUE, COGS, OPEX, G&A, R&D, OTHER_INCOME, OTHER. SKIP is frontend-only — used in the MappingConfirmModal dropdown to mean "do not import this column"; never written to the database.
- Historical data reference (Supabase)
- Variance calculation (Python — not Claude)
- Anomaly and error detection (Python — not Claude)
- Numeric guardrail: 2 attempts (original + 1 retry with reinforced prompt). Second failure → `guardrail_failed` run state, GuardrailWarning screen, raw pandas summary downloadable. Retry Analysis starts a fresh `run_id`, reuses the already-stored file.
- Two-model pipeline: `claude-haiku-4-5-20251001` for column mapping (Parser), `claude-opus-4-7` for narrative + anomaly reasoning (Interpreter). No user toggle.
- Dashboard (visual report)
- Email sending (Resend)
- Supabase Auth (email + password). RLS isolates data by `companies.owner_id = auth.uid()`.
- Frontend error boundary: React `ErrorBoundary` wrapper covering all routes, rendering a plain-English fallback instead of a white screen.
- Client-side file validation before upload: extension must be `.xlsx` / `.csv` / `.xls` / `.xlsm`, size ≤ 10 MB. Rejected files never hit the backend; user sees a clear error message (e.g. "`report.pdf` is not a supported format — upload an Excel or CSV file.").
- PII sanitization before any Claude call: header blacklist (SSN, tax ID, DOB, personal name, home address, bank account/routing, personal contact) + SSN value-level regex (`^\d{3}-?\d{2}-?\d{4}$`). Matching columns are dropped entirely (no hashing). Runs before pandera validation and before column mapping, so Claude never sees PII values or PII-column samples. All-stripped files surface `messages.FILE_HAS_NO_VALID_COLUMNS`.
- Rate limiting via `slowapi` (in-memory, single Railway container) with a **composite key**: authenticated requests are keyed on `user_id`; unauthenticated requests fall back to client IP. Single bucket per request — not two parallel buckets. Caps: `POST /upload` 5/min; `GET /runs/{run_id}/status` 120/min; `GET /report/*`, `GET /anomalies/*` 60/min; `POST /mail/send` 10/hour; `GET /health` uncapped. 429 responses carry `Retry-After` and a plain-English message.
- Clean Architecture (ports & adapters): `domain/`, `adapters/`, `agents/`, `api/` layers. Dependencies point inward only.
- `RunStateMachine` enforcing explicit transitions: `pending → parsing → mapping → comparing → generating → complete`. Terminal states: `upload_failed`, `guardrail_failed`.
- `PandasSummary` and `NarrativeJSON` Pydantic contracts between agents.
- Supabase Storage as file persistence layer (Railway containers are ephemeral). Folder: `financial-uploads/{auth.uid()}/{company_id}/{period}/{filename}`.
- Storage upload retry: 3 attempts, backoff 0.5s → 1.5s → 4s, then `TransientIOError` → `upload_failed`.
- Post-success storage cleanup as background task. Failures logged at WARNING with `trace_id` / `run_id` / `storage_key` and swallowed.
- RLS on every company-owning table via EXISTS-through-`companies`. Storage RLS keyed on `(storage.foldername(name))[1] = auth.uid()::text`.
- `trace_id` middleware + JSON structured logging end-to-end including frontend `ErrorBoundary`.
- `messages.md` as single source of truth for all user-facing strings.
- `GET /runs/{run_id}/raw` — raw pandas summary download for `guardrail_failed` runs only. Output labeled unverified.
- PII sanitization before any Claude call: header blacklist + SSN value pattern. Pipeline order: `read → strip PII → pandera → map → normalize → write`.
- Frontend stack: React + TypeScript + Vite + shadcn/ui (Radix + Tailwind) + `@tanstack/react-table`.
- Toast notifications (4 types) for transient events. Inline errors for blocking states (guardrail, auth, low-confidence mapping).
- Visual trust signal: "Verified · Guardrail Passed" badge on every guardrail-passed report.
- Provenance on every number: hover reveals source filename + original column name.
- US accounting number formatting: tabular numerals (`font-feature-settings: "tnum"`), comma thousands, parenthesized negatives (`$1,234`), `MMM YYYY` headers, ISO-8601 metadata.
- Responsive breakpoints: desktop-first. Mobile (≤375px): upload + report only. Tables horizontal-scroll below 1024px.
- Login screen as step 0 of Core User Flow.
- Empty state for first-time users with no history yet.

### EXCLUDED ❌
- Onboarding wizard (mock/real data for demo)
- Multi-user / role management (single user per company)
- budget/plan comparison
- ERP API integration (NetSuite, QuickBooks)
- PDF export
- mobile app

---

## Demo Scenario

**Primary demo — DRONE Inc.:**
Fictional demo company. Quarterly financial data derived from SEC 10-Q/10-K. Income Statement, Balance Sheet, and Cash Flow included.

> "I uploaded DRONE's March 2026 and February 2026 financial Excel files. The agent detected G&A dropped from $7.2M to $4.7M in March — a 34% improvement. Gross margin rose to 39%, the highest in 7 months. Travel variance +61% was flagged. A plain-language report was generated and emailed."

**Secondary demo — different format test:**
The same agent can also read a file in a different format.

---

## Architectural Constraints

- **Claude must never do math.** All variance, anomaly, and percentage calculations are done in Python/pandas.
- **Numeric guardrail is mandatory.** Numbers in Claude's report are verified against pandas output with 2% tolerance.
- **Prompts are never written inline.** They are versioned in the `prompts/` folder.

---

## Success Criteria (Hackathon)

- [ ] Real DRONE Excel can be uploaded
- [ ] Agent can read file and map to US GAAP categories
- [ ] Variance is calculated in Python
- [ ] At least 2 anomalies are detected
- [ ] Numeric guardrail works
- [ ] Plain-language English report is generated
- [ ] Dashboard visualization works
- [ ] Email can be sent

---

## Future Roadmap (Post-MVP)
These are intentionally excluded from the hackathon build.
Including them in the submission framing shows vision with MVP discipline.

- pgvector: Long-term pattern recognition across fiscal years
- pdfplumber: PDF invoice and statement ingestion
- ERP API integration: Direct NetSuite, QuickBooks, SAP connections
- Multi-user / role management: Controller vs CFO view
- Budget vs actuals: Plan file comparison layer
- Draft journal entries: Auto-generated JE suggestions for ERP upload
