# IRONLEDGER HACKATHON MASTER BRIEF

## Context: What We're Building

**IronLedger** is an AI-powered month-end close tool for US SMBs. Target: companies with 5–40 employees, no FP&A budget, using QuickBooks + manual Excel files from departments. They spend 5–10 hours every month manually consolidating files and hunting discrepancies.

**Current state:** Single-file variance analyzer. Upload one file, detect anomalies vs. last month, Claude explains them.

**Target state (post-hackathon):** Multi-file consolidator with cross-source reconciliation. Upload N files from different departments/sources → one consolidated P&L → flagged discrepancies between sources → AI narrative → downloadable Excel audit workbook.

**Core architecture (DO NOT CHANGE):** pandas calculates, Claude interprets, guardrail verifies numbers. This is our hallucination moat.

---

## Three Real-World Scenarios We Must Handle

### Scenario 1: E-commerce (BlueLine Outdoor)
Sells camping gear on Shopify + Amazon. 1 person, no accountant, QuickBooks.

**Month-end files (5):**
1. `shopify_payout.csv` — ~150 rows: Date, Order ID, Gross Sales, Discounts, Refunds, Shipping, Shopify Fees, Net Payout. Net: $42,300
2. `amazon_settlement.csv` — ~40 rows: Settlement Date, Order Revenue, Refunds, FBA Fees, Advertising, Promo Rebates, Net Deposit. Net: $18,700
3. `gl_export.xlsx` — QuickBooks P&L export, ~60 rows. Net profit: $8,200
4. `ad_spend.csv` — Google Ads $5,100 + Meta $3,200 = $8,300 total
5. `bank_statement.csv` — Chase Business, ~200 transactions

**Key discrepancies to catch:**
- Shopify ($42,300) + Amazon ($18,700) = $61,000 total revenue, but QuickBooks shows $58,000 → $3,000 timing cutoff (March 28 Shopify payout landed April 1, not in GL)
- Ad spend $8,300 in CSV, but GL shows $8,500 → $200 FX timing difference on Meta invoice
- Bank deposits $57,500 vs total sales $61,000 → difference is Shopify/Amazon fees deducted before deposit

### Scenario 2: Security Systems Installation + Monitoring (Sentinel Secure)
Installs alarms, cameras, sensors for homes/businesses. 8 employees. Office manager does close.

**Month-end files (7):**
1. `gl_export.xlsx` — QuickBooks, ~90 rows
2. `payroll.xlsx` — Manual timesheet: Employee, Base, Overtime, Bonus, Total. 8 people. Total: $44,200
3. `supplier_invoices.xlsx` — 4 suppliers (AlarmTech $12,500, VisionPro $18,200, SafeGas $4,800, CableMax $2,300). Total: $37,800. Manually compiled from PDFs into Excel.
4. `service_contracts.xlsx` — 85 monitoring customers: Name, Plan, Monthly Fee, Active?. Expected revenue: $3,825
5. `vehicle_expenses.xlsx` — Fuel, maintenance, parking. ~25 rows. Total: $2,100
6. `ad_spend.csv` — Google Ads $1,800 + Angie's List $600 = $2,400
7. `bank_statement.csv` — ~300 transactions

**Key discrepancies:**
- Supplier invoices total $37,800, GL COGS $36,100 → $1,700 gap (CableMax invoice not yet entered in GL)
- Service contracts expect $3,825, GL shows $3,540 → $285 gap (3 cancelled customers still marked "active" in Excel)
- Payroll $44,200 manual vs GL $44,900 → $700 gap. A technician's on-call bonus was miscategorized to "Contractors" instead of "Payroll" in GL — categorical misclassification
- Installation revenue $8,000 in GL but only $4,000 in bank → $4,000 timing difference (50% deposits received, remainder due in April)

### Scenario 3: IT Consulting (Vantage Digital)
SAP/Salesforce/cloud consulting. 20 employees. Part-time accountant, CFO does close.

**Month-end files (8):**
1. `gl_export.xlsx` — QuickBooks, ~120 rows
2. `timesheets.xlsx` — Harvest export: Consultant, Client, Project, Hours, Rate, Amount. ~300 rows. Total billable: $187,000
3. `gusto_payroll.xlsx` — 20 employees. Base, Bonus, Benefits, Employer Taxes, 401k. Total: $162,000
4. `contractor_invoices.xlsx` — 6 subcontractors. Total: $28,400. Column: Paid? (Y/N)
5. `travel_expenses.xlsx` — 8 business trips. Flight, Hotel, Per Diem, Transport. Total: $12,600
6. `saas_subscriptions.xlsx` — 17 tools (AWS, Jira, Slack, Miro, Figma, HubSpot…). Total monthly: $8,100
7. `retainer_contracts.xlsx` — 12 retainer clients. Monthly Fee, Active, Last Billed. Expected: $31,200
8. `bank_statement.csv` — ~500 transactions

**Key discrepancies:**
- Timesheets $187,000 billable, GL consulting revenue $174,500 → $12,500 timing difference (3 projects worked in March, invoiced in April — accrued revenue, not an error)
- Gusto $162,000, GL salaries $158,500 → $3,500 gap. Severance payment miscategorized to Operating Expenses instead of Payroll
- Contractor invoices $28,400, GL contractors $24,900 → $3,500 gap. One invoice not yet approved/entered in GL
- Travel $12,600, GL travel $9,800 → $2,800 gap. Missing Uber receipts + one hotel invoice not yet processed
- SaaS list $8,100, GL software $6,700 → $1,400 gap. HubSpot annual invoice ($13,200) hit in March but wasn't amortized monthly. Correct monthly cost should be $1,100, GL shows lump sum causing discrepancy
- Retainer expected $31,200, GL retainer $28,600 → $2,600 gap. 1 client paused retainer (list not updated) + 1 client was billed at old rate before price increase took effect

---

## Current System Gaps (Honest Assessment)

Our product today delivers ~25% of the proposition. Here's what's missing:

| What we promise | What we actually do |
|---|---|
| "Five departments. Five different Excel files." | Uploads N files but routes each to independent pipeline. No consolidation. Five files = five separate reports. |
| "Reads across all of them, maps the chaos" | Maps ONE file's chaos well. Does not read across files. |
| "Catches discrepancies" | Catches variance vs. last month, NOT discrepancies between files for the same month. Two very different things. |
| "Reconciles inconsistencies" | No reconciliation logic in the codebase. None. |
| "Someone consolidates manually. Someone hunts missing rows." | We do not consolidate. We do not check for missing rows. |
| "Controller running three companies" | Auth model: one user = one company. Multi-entity impossible. |

**The core gap:** We built the interpretation engine (10% of the job). We skipped the consolidation + reconciliation engine (60% + 30% of the CFO's actual close-night pain).

---

## The 30-Hour Plan (Already Decided)

Goal: close the gap from 25% to ~80% delivered.

### Hours 0–2: Database Migration + Entity Changes
- Run migration `0002_multi_source_consolidation.sql`:
  - `ALTER TABLE monthly_entries ADD COLUMN source_breakdown JSONB` — shape: `[{"source_file": "payroll.xlsx", "source_column": "Gross", "amount": 47200.00, "row_count": 3}, ...]`
  - `ALTER TABLE reports ADD COLUMN reconciliations JSONB` — shape: `[{"account": "Marketing", "sources": [...], "delta": 2900.00, "severity": "medium", "narrative": "..."}, ...]`
  - `ALTER TABLE runs ADD COLUMN file_count INT DEFAULT 1`
- Update `MonthlyEntry` and `Report` dataclasses + repos to accept new fields.

### Hours 2–8: ConsolidatorAgent (Core New Code)
- New file: `agents/consolidator.py`
- Pure pandas. Input: `list[tuple[str, pd.DataFrame]]`. Output: `(consolidated_df, list[ReconciliationItem])`
- Three operations:
  1. **Union:** stack all entries into one DataFrame tagged with `source_file`
  2. **Match:** fuzzy-match account names across files using `rapidfuzz` at 90% threshold. "Payroll" + "Wages & Salaries" + "Employee Compensation" → collapse to one line. Ambiguous matches (<90%) go to existing low-confidence-mapping flow
  3. **Total:** produce one consolidated P&L with per-source breakdown. For each consolidated account, compute delta if any source differs by >$100 OR >5%
- Write unit tests with two hand-crafted DataFrames (one "GL", one "Payroll dept") before wiring up.

### Hours 8–12: Orchestrator + Route Rewrite
- `routes.py:/upload` — pass ALL storage keys to ONE background task, not N individual tasks
- `agents/orchestrator.py` — new function `run_multi_file_parser_until_preview(run_id, storage_keys, ...)`. Loops files through existing ParserAgent, collects validated DataFrames, calls ConsolidatorAgent.consolidate(), writes via `entries_repo.replace_period()`
- Smoke test: upload drone data + hand-crafted disagreeing file

### Hours 12–18: Frontend Consolidation UI
- Upload component: allow multiple files, show as chips with optional "source label" input
- ParsePreviewPanel: add "Sources" column showing which file contributed to each account line
- New component: `<ReconciliationPanel>` — shown above AnomalyCards. Lists every mismatch with per-source breakdown
- AnomalyCard: use stored provenance data. Hover shows "from payroll_mar.xlsx, column Gross Pay"

### Hours 18–22: Interpreter + Guardrail Extension
- Add reconciliations to Interpreter's prompt context
- Extend `narrative_prompt.txt` so output JSON has `reconciliation_narrative` field
- **Critical:** Add accrual/timing/cutoff difference awareness to prompt. If delta can be explained by period cutoff, Claude should say so, not flag as error.
- Verify existing guardrail catches mismatches in reconciliation narrative numbers (it should — `numbers_used` covers all output numbers)

### Hours 22–26: Excel Export Endpoint
- New route: `GET /report/{company_id}/{period}/export.xlsx`
- Build with `openpyxl`. Three sheets: Consolidated P&L, Reconciliations, Source Breakdown
- Add "Download Excel" button to report page

### Hours 26–28: Demo Data + Rehearsal
- Create 2–3 demo files per scenario
- Walk end-to-end: drop 3 messy files → one consolidated P&L → reconciliation flags with dollar deltas → narrative explains each
- Must be under 2 minutes

### Hours 28–30: Polish + Buffer

---

## Hackathon Feature Priority (What Wins)

| # | Feature | Why It Wins |
|---|---|---|
| 🥇 | **Multi-file consolidation + cross-source reconciliation** | Core promise. 3-8 files → 1 P&L → flagged deltas. The "wow" moment. |
| 🥈 | **Excel export (3-sheet workbook)** | Finance people trust Excel. PDF is a demo artifact; Excel is a work deliverable. |
| 🥉 | **Provenance (clickable source trace)** | Click any number → see which file, row, column produced it. Trust feature. Auditor asks "prove it" on every number. |
| 4 | **Revenue recognition / timing difference explanation** | Claude prompt update. Distinguishes real errors from period-cutoff timing differences. Shows domain expertise. |
| 5 | **Lightweight bank balance comparison** | Compare GL "Cash" account ending balance vs bank CSV final row. Single check, big confidence signal. Skip full bank reconciliation — too heavy for 30h. |
| 6 | **Row-level detail reconciliation** | Match individual customers/employees across sources. High value but hard to finish in 30h. If time permits, demo with 5 rows as proof of concept. |

---

## What We Explicitly Cut (For Now)
- PDF ingestion (2+ days)
- Full bank statement reconciliation (different data shape, needs new schema)
- Multi-company / multi-entity (requires auth rework)
- Scheduled runs / continuous monitoring
- Real-time dashboards
- Anything involving pgvector, embeddings, or semantic search (CLAUDE.md forbids)

---

## Instructions for AI

You are helping build IronLedger for a hackathon. The above is your complete context: product state, user scenarios, technical gaps, and the 30-hour plan.

When asked to implement something:
1. Follow the existing architecture: pandas calculates → Claude interprets → guardrail verifies
2. Do not touch: domain layer, ports, adapters, guardrail, PII sanitizer, Discovery agent, existing Interpreter core logic
3. All new code goes in: `agents/consolidator.py` (new), `agents/orchestrator.py` (extend), `routes.py` (modify upload route), frontend components (new ReconciliationPanel, extend ParsePreviewPanel and AnomalyCard)
4. Prefer minimal, surgical changes. No schema rewrites. No new dependencies without justification.
5. Every number in the UI must be traceable to its source file.
