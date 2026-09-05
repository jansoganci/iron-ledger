# Month Proof
### AI-Powered Month-End Close Agent
*Built with Claude Opus 4.7 — Anthropic Hackathon April 2026*

---

## What it does

Drop your messy financial Excel files. Month Proof reads them, compares them with history, finds anomalies, writes a plain-language report, verifies its numbers, and exports a close package.

Built for US finance teams spending 10-15 hours/month on manual close work.

---

## How it was built with Claude Code

This project was developed entirely using Claude Code as the primary development engine.

Claude Code was used to:
- Architect the agent orchestration loop (tool-use pattern)
- Write and debug all pandas parsing logic
- Design the numeric guardrail system
- Generate and iterate on narrative prompts
- Fix edge cases in NetSuite XML format detection
- Write FastAPI endpoints and Supabase integration

To see Claude Code in action on this codebase, run:
```bash
claude "explain how the numeric guardrail works in backend/tools/guardrail.py"
claude "add support for .xlsm files in backend/tools/file_reader.py"
claude "write a test for the variance calculation in backend/agents/comparison.py"
```

---

## Quick Start

### Prerequisites
- Python 3.11+
- Node.js 18+
- Supabase account
- Anthropic API key

### 1. Clone and install
```bash
git clone https://github.com/jansoganci/iron-ledger.git
cd iron-ledger
cp .env.example .env   # fill in your keys
pip install -r requirements.txt
cd frontend && npm install
```

### 2. Set up database + auth
```bash
# Apply all 10 migrations in supabase/migrations/ in numeric order.
# Recommended: use the Supabase CLI so no migration is skipped:
supabase db push

# In Supabase Dashboard → Authentication → Users, create a demo user:
#   email:    demo@redhawkdemo.com
#   password: (your choice)
# Then run supabase/seed.sql to create Redhawk Alarm & Security LLC for that user.
```

### 3. Run the backend
```bash
# From repo root:
uvicorn backend.main:app --reload
# API running at http://localhost:8000
```

### 4. Run the frontend
```bash
cd frontend
npm run dev
# UI running at http://localhost:5173
```

### 5. Upload a file and run the agent
Open `http://localhost:5173`, upload an Excel file, select the period, click Analyze.

Or via API directly (JWT required — `company_id` is derived from the token):
```bash
# Get a JWT by logging in through the frontend, or use the Supabase REST auth endpoint:
#   curl -X POST "$SUPABASE_URL/auth/v1/token?grant_type=password" \
#     -H "apikey: $SUPABASE_ANON_KEY" \
#     -H "Content-Type: application/json" \
#     -d '{"email":"demo@redhawkdemo.com","password":"..."}'
# Use the returned access_token:

curl -X POST http://localhost:8000/upload \
  -H "Authorization: Bearer $JWT" \
  -F "files=@docs/demo_data/redhawk/redhawk_gl_mar_2026.xlsx" \
  -F "period=2026-03-01"
```

---

## Architecture

```
File Upload → Discovery → Account Mapping → Parse/Normalize
                                                    ↓
                         Multi-source Consolidation + Reconciliation
                                                    ↓
                         Comparison → Interpretation → Numeric Guardrail
                                                    ↓
                                 Verified Monthly/Quarterly Reports + Excel Export
```

**Key principle:** Numbers come from pandas. Prose comes from Claude. A numeric guardrail verifies that Claude's narrative matches the pandas output before any report is saved.

---

## Demo

Live demo: no public deployment URL is currently documented.

### Demo datasets (included in the repo)

The `docs/demo_data/` folder ships with curated multi-file scenarios designed to exercise the full pipeline end-to-end:

| Scenario | Folder / Files | What it demonstrates |
|---|---|---|
| **Redhawk Alarm & Security LLC — seeded demo** | `docs/demo_data/redhawk/` (GL, contracts, payroll, and vendor invoices) | Primary four-file reconciliation scenario for `demo@redhawkdemo.com`, including the deterministic $285 service-revenue roster gap. |
| **Additional sector scenarios** | `docs/demo_data/{clearview,corebuilt,harvest,helix,vandelay}/` | Multi-source fixtures for healthcare, construction, food service, professional services, and e-commerce workflows. |
| **Sentinel Secure — multi-period GL** | `docs/demo_data/sentinel/` (February and March GL files) | The only checked-in two-period company fixture. The former payroll, supplier, contracts, and installation files are no longer in the repository. |

Drop these into the upload form (or use the `/upload` endpoint) to see the system run without preparing your own data.

### Demo walkthrough
1. Sign in or create account
2. Set up company profile (first-time onboarding)
3. Choose a demo dataset above (Redhawk is the seeded end-to-end scenario)
4. Upload the files, select the period (`2026-03-01`), click Analyze
5. Review the parsed preview, confirm
6. Plain-language report generated and verified by the numeric guardrail
7. Download raw data, export the verified Excel close package, or open a prefilled draft in the local email client

---

## Known Limitations (MVP scope)

This is a hackathon MVP. It is intentionally narrow. Things you should know before testing with your own data:

- **Supported input formats.** The reader accepts `.xlsx`, `.xls`, `.xlsm`, and `.csv`, including the NetSuite XML Spreadsheet 2003 edge case. `docs/demo_data/` contains curated sector fixtures, but not every checked-in workbook is exercised by an automated end-to-end test. Real-world exports can still require discovery or mapping review.
- **Account mapping still needs review for ambiguous values.** The implemented account-mapping layer uses Claude Haiku to map non-GL source values into the canonical GL account pool and validates its output. Uncertain mappings pause for user confirmation; unusual vendor, employee, or SKU identifiers can still require manual reassignment.
- **Single user, single company per account.** RLS enforces `companies.owner_id = auth.uid()`. Multi-entity / multi-user is post-MVP.
- **Fixed monthly and quarterly views.** Monthly runs compare one period with history. Persisted quarterly reports aggregate calendar quarters and can include prior-year deltas when enough data exists, but arbitrary date ranges are not supported.
- **No PDF, no API integrations.** Excel/CSV only. Direct ERP integrations are post-MVP.
- **No server-side email delivery.** `MailButton` opens a prefilled `mailto:` draft in the user's local email client. The `/mail/send` route and `ResendEmailSender` remain stubs; setting `RESEND_API_KEY` does not enable backend delivery.
- **In-memory rate limiting.** A single backend container is assumed. Redis-backed rate limiting is post-MVP.

If you want to evaluate the system, **start with the seeded Redhawk scenario in `docs/demo_data/redhawk/`**. The other folders are additional sector fixtures and may expose mapping decisions that need review.

---

## Environment Variables

```bash
# .env.example
ANTHROPIC_API_KEY=your_key_here
SUPABASE_URL=your_supabase_url
SUPABASE_SERVICE_KEY=your_service_key
SUPABASE_ANON_KEY=your_anon_key
SUPABASE_JWT_SECRET=your_jwt_secret
RESEND_API_KEY=your_resend_key
RESEND_FROM_EMAIL=reports@yourdomain.com
FRONTEND_URL=http://localhost:5173
APP_ENV=development
```

---

## Future Roadmap

See `docs/03-sprint/risks.md` section "Post-MVP Backlog" for the original backlog. Highlights:

- **pgvector** for long-term pattern recognition across fiscal years
- **ERP API integrations** (NetSuite, QuickBooks, SAP direct)
- **PDF invoice ingestion** (pdfplumber)
- **Multi-user / role management** (Controller vs CFO views)
- **Budget vs actuals comparison**
- **Draft journal entry generation** (auto-generated JE for ERP upload)
- **Comprehensive test coverage** (E2E, RLS, guardrail, PII sanitization)
- **CI/CD pipeline** with automated testing
- **Observability** (Sentry / Datadog integration)
