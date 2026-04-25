# IronLedger
### AI-Powered Month-End Close Agent
*Built with Claude Opus 4.7 — Anthropic Hackathon April 2026*

---

## What it does

Drop your messy financial Excel files. IronLedger's agent reads them, compares to history, finds anomalies, writes a plain-language report, and emails it — in under 2 minutes.

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
claude "explain how the numeric guardrail works in tools/guardrail.py"
claude "add support for .xlsm files in tools/file_reader.py"
claude "write a test for the variance calculation in agents/comparison.py"
```

---

## Quick Start

### Prerequisites
- Python 3.11+
- Node.js 18+
- Supabase account
- Anthropic API key
- Resend API key (for email)

### 1. Clone and install
```bash
git clone https://github.com/YOUR_USERNAME/ironledger
cd ironledger
cp .env.example .env   # fill in your keys
pip install -r requirements.txt
cd frontend && npm install
```

### 2. Set up database + auth
```bash
# Apply migrations to your Supabase project (6 migration files)
# In Supabase Dashboard → SQL Editor, run each migration in order:
#   - supabase/migrations/0001_initial_schema.sql
#   - supabase/migrations/0002_add_pandas_summary.sql
#   - supabase/migrations/0003_add_source_column.sql
#   - supabase/migrations/0004_add_storage_key.sql
#   - supabase/migrations/0005_add_parse_preview.sql
#   - supabase/migrations/0006_add_discovery_plan.sql
# Or use Supabase CLI: supabase db push

# In Supabase Dashboard → Authentication → Users, create a demo user:
#   email:    demo@ironledger.com
#   password: (your choice)
# The app will guide you through company setup on first login
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
#     -d '{"email":"demo@dronedemo.com","password":"..."}'
# Use the returned access_token:

curl -X POST http://localhost:8000/upload \
  -H "Authorization: Bearer $JWT" \
  -F "file=@drone_mar_2026.xlsx" \
  -F "period=2026-03-01"
```

---

## Architecture

```
File Upload → Parser Agent → Comparison Agent → Interpretation Agent
                                                        ↓
                                             Numeric Guardrail
                                                        ↓
                                        Dashboard + Email Report
```

**Key principle:** Numbers come from pandas. Prose comes from Claude. A numeric guardrail verifies that Claude's narrative matches the pandas output before any report is saved.

---

## Demo

Live demo: *(Deployment pending — Day 6)*

### Demo datasets (included in the repo)

The `docs/demo_data/` folder ships with curated multi-file scenarios designed to exercise the full pipeline end-to-end:

| Scenario | Folder / Files | What it demonstrates |
|---|---|---|
| **DRONE Inc. — single-file variance** | `docs/demo_data/Drone Inc - {Jan,Feb,Mar} 26.xlsx` | Month-over-month variance analysis on a clean GL export. Highlights: G&A down 34%, Travel up 61%. |
| **Sentinel Secure — multi-file reconciliation** | `docs/demo_data/sentinel/sentinel_*.xlsx` (5 files: GL, supplier invoices, payroll, contracts, installation payments) | Multi-source consolidation + cross-source reconciliation. Produces 30+ reconciliation items across `missing_je` and `categorical_misclassification` classifications. |

Drop these into the upload form (or use the `/upload` endpoint) to see the system run without preparing your own data.

### Demo walkthrough
1. Sign in or create account
2. Set up company profile (first-time onboarding)
3. Choose a demo dataset above (single-file for variance, Sentinel multi-file for reconciliation)
4. Upload the files, select the period (`2026-03-01`), click Analyze
5. Review the parsed preview, confirm
6. Plain-language report generated and verified by the numeric guardrail
7. Download raw data, export Excel, or send email report

---

## Known Limitations (MVP scope)

This is a hackathon MVP. It is intentionally narrow. Things you should know before testing with your own data:

- **Tested input formats.** The pipeline has been smoke-tested against the curated datasets in `docs/demo_data/`. Real-world exports from QuickBooks, NetSuite, Xero, Shopify, Stripe, and similar platforms may require manual adjustment of the column mappings the Discovery agent produces. The frontend exposes a confirmation step for low-confidence mappings, but unusual file shapes can still produce surprising results.
- **Account-name normalization is not yet automatic.** The pipeline expects each input file to contain a column whose values are recognizable account names (or names that fuzzy-match across files at ≥90% WRatio). Files that use vendor names, employee names, or SKU codes as the primary identifier will produce a flood of `missing_je` reconciliations because the consolidator can't link those values to GL accounts. An AI-assisted account mapping layer is on the v1.1 roadmap (see `docs/02-planning/account_mapper_sprint_plan.md`).
- **Single user, single company per account.** RLS enforces `companies.owner_id = auth.uid()`. Multi-entity / multi-user is post-MVP.
- **Single-period analysis.** The variance engine compares one period to history; it does not yet support custom comparison ranges or YoY views.
- **No PDF, no API integrations.** Excel/CSV only. Direct ERP integrations are post-MVP.
- **Email is scaffolded but disabled by default.** Set `RESEND_API_KEY` and toggle the send flag in the report panel to enable.
- **In-memory rate limiting.** A single backend container is assumed. Redis-backed rate limiting is post-MVP.

If you want to evaluate the system, **start with `docs/demo_data/`** — every file there has been verified to flow through the pipeline cleanly.

---

## Environment Variables

```bash
# .env.example
ANTHROPIC_API_KEY=your_key_here
SUPABASE_URL=your_supabase_url
SUPABASE_SERVICE_KEY=your_service_key
RESEND_API_KEY=your_resend_key
```

---

## Future Roadmap

See `docs/sprint/risks.md` section "Post-MVP Backlog" for full list. Highlights:

- **pgvector** for long-term pattern recognition across fiscal years
- **ERP API integrations** (NetSuite, QuickBooks, SAP direct)
- **PDF invoice ingestion** (pdfplumber)
- **Multi-user / role management** (Controller vs CFO views)
- **Budget vs actuals comparison**
- **Draft journal entry generation** (auto-generated JE for ERP upload)
- **Comprehensive test coverage** (E2E, RLS, guardrail, PII sanitization)
- **CI/CD pipeline** with automated testing
- **Observability** (Sentry / Datadog integration)
