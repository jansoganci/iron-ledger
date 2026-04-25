# IronLedger — 30-Hour Execution Plan & Product Audit

> Drafted 2026-04-24. Hackathon deadline in ~30 hours.
> Purpose: close the gap between the proposition and the shipped product.

---

## 1. Proposition vs. Product — brutally honest

The proposition is **strong**. It names a real, underserved problem for SMB finance teams (5–200 employees, no FP&A tool budget). Every sentence points to a specific workflow that wastes hours.

**But the current product delivers ~25% of it, not 80%.**

| Promise | What the code does today |
|---|---|
| "Five departments. Five different Excel files." | Uploads N files but routes each to an **independent** pipeline (`backend/api/routes.py:255-262`). Five files → five separate reports. No consolidation. |
| "Five different formats." | Handles `.xlsx`, `.xlsm`, `.csv`, `.xls` (incl. NetSuite XML). **No PDF.** |
| "Reads across all of them, maps the chaos." | Maps a single file's chaos well (Discovery agent + Haiku). Does not read **across** files. |
| "Catches discrepancies." | Catches **variance vs. last month**, not **discrepancies between files** for the same month. Different thing. |
| "Reconciles inconsistencies." | **No reconciliation logic in the codebase.** None. |
| "Someone consolidates manually. Someone hunts missing rows." | No consolidation. No missing-row checks. |
| "Controller running three companies on one spreadsheet." | Auth model is one user = one company (`companies.owner_id` → `auth.uid()`, RLS-enforced). Multi-entity impossible today. |

**Verdict:** the copy sells a **multi-file consolidator with cross-source reconciliation**. The product is a **single-file variance analyzer**. These are different products.

---

## 2. Does the concept match the promise?

- **Concept (pandas calculates, Claude interprets, guardrail verifies):** excellent. Do not change.
- **Scope:** the interpretation engine was built; the consolidation engine was skipped.
- A CFO's close-night pain is roughly **60% consolidation + 30% reconciliation + 10% interpretation.** Only the 10% is shipped.

---

## 3. The real SMB close workflow — concrete, not abstract

What lands in a 40-person SaaS company controller's inbox between the 1st and 5th of the month:

1. `Bank_Statement_March.csv` — bank portal export. ~200 rows. Columns: `Date, Description, Debit, Credit, Balance`.
2. `Payroll_March.xlsx` — Gusto/Rippling/ADP export. Gross wages, employer taxes, benefits, 401k.
3. `AWS_Invoice_March.csv` or a Stripe/Shopify payouts file. Raw vendor export.
4. `Marketing_Spend_March.xlsx` — hand-built by the marketing manager. Ad platforms + agency fees + events. Often has typos ("Gogle Ads") or merged-cell campaign groupings.
5. `GL_Export_March.xlsx` — from QuickBooks / Xero / NetSuite. The "official" P&L. ~80 rows.

**What the controller does for ~6 hours:**

- Copies all five into one master workbook.
- Matches department-submitted marketing spend ($47,200) against the GL marketing line ($50,100). $2,900 delta. 45 minutes to track it down to a reclass.
- Sums payroll line items vs. GL wages+benefits. Finds $1,800 of bonuses booked to G&A instead of Payroll.
- Spots bank deposits ($412K) don't match GL revenue ($473K). Reconciles to a $60K wire that arrived April 2 (timing cut-off, not an error).
- Notices AWS up 42% vs. February. Writes three sentences for the CEO.
- Re-keys everything into the board deck.

**This is the job.** The copy promises to automate this. The current product automates the last 20 minutes.

---

## 4. Minimum feature set to deliver 80% of the promise

Rank-ordered by value-per-hour-of-build. If it's not on this list, cut it.

### (A) True multi-file consolidation ← the core gap
One upload, N files. Each file passes through the existing Parser (it already works). A **new `ConsolidatorAgent`** then:

1. **Unions** all entries into one DataFrame tagged with `source_file`.
2. **Fuzzy-matches** account names across files so "Payroll" / "Wages & Salaries" / "Employee Compensation" collapse to one line. Use `rapidfuzz` at 90% threshold; ambiguous matches fall into the existing low-confidence mapping flow.
3. **Totals** into one consolidated P&L, written to `monthly_entries` as today. Per-file provenance preserved in a new JSONB column.

### (B) Cross-source reconciliation ← the headline feature
For every consolidated account line, compare across sources:

- **Hard mismatch**: same account in two files with different amounts (Marketing dept $47,200 vs GL $50,100). Flag with delta.
- **Missing coverage**: account in one file but not the "master" source. Flag as orphan.

These become first-class findings alongside anomalies. Claude narrates them with the existing guardrail.

### (C) Provenance in the UI
Every number on the report clickable → which file + which row produced it. `monthly_entries.source_file` and `source_column` are already stored (`backend/api/routes.py:420-428`) but the UI does not surface them. Plumb it through. Highest-ROI trust feature — auditors ask "prove it" on every number.

### (D) Structured Excel output
`GET /report/{company_id}/{period}/export.xlsx` — real `.xlsx` with three sheets: `Consolidated P&L`, `Reconciliations`, `Source Breakdown`. Finance people trust Excel. A PDF/HTML report is a demo artifact; an Excel file is a work deliverable.

### Cut from the 80% path
- PDF ingestion
- Bank-statement reconciliation (different data shape; breaks the schema)
- Multi-company / multi-entity (requires auth rework)
- Continuous monitoring / scheduled runs
- Email sending (already scaffolded; leave it)
- pgvector anything (CLAUDE.md already forbids)

---

## 5. Database changes — minimal, additive, one migration

Do **not** redesign the DB. Three additive columns.

```sql
-- 0002_multi_source_consolidation.sql
ALTER TABLE monthly_entries
    ADD COLUMN source_breakdown JSONB;
-- Shape: [{"source_file": "payroll_mar.xlsx", "source_column": "Gross",
--         "amount": 47200.00, "row_count": 3}, ...]

ALTER TABLE reports
    ADD COLUMN reconciliations JSONB;
-- Shape: [{"account": "Marketing", "sources": [...], "delta": 2900.00,
--         "severity": "medium", "narrative": "..."}, ...]

ALTER TABLE runs
    ADD COLUMN file_count INT DEFAULT 1;
```

That's it. Existing `monthly_entries` row = consolidated total; `source_breakdown` = audit trail of origin.

---

## 6. Backend / AI architecture changes

**Keep unchanged:** domain layer, ports, adapters, guardrail, PII sanitizer, Discovery agent, Interpreter.

**Change (surgical):**

1. `backend/api/routes.py:255-262` — stop looping `background_tasks.add_task` per file. **One** `add_task` per run, passing the full list of storage keys.
2. `backend/agents/orchestrator.py` — new `run_multi_file_parser_until_preview(run_id, storage_keys, ...)`. Loops files through existing ParserAgent, collects N validated DataFrames into a list.
3. **New file** `backend/agents/consolidator.py` — pure pandas. Input: `list[tuple[str, pd.DataFrame]]`. Output: one consolidated DataFrame + `list[ReconciliationItem]` Pydantic models. Zero Claude calls. ~120–150 lines.
4. `backend/agents/interpreter.py` — extend prompt context to include `reconciliations` alongside `anomalies`. Guardrail handles numeric verification unchanged.
5. `backend/prompts/narrative_prompt.txt` — add a "Reconciliations" section to the required output JSON. Existing guardrail catches every number in `numbers_used` → reconciliation deltas inherit the safety net automatically.

Entire architectural delta. Everything else stays.

---

## 7. What SMB finance users actually pay for first

| Feature | Would SMB controllers pay? | Why |
|---|---|---|
| Auto-consolidate N department files into one P&L | **Yes, immediately** | Saves 3–4 hours every month. Nobody under $500/mo does this. |
| Flag discrepancies between dept and GL totals | **Yes** | Manual error-hunting they already do. |
| English narrative explaining variance | Maybe | Nice, but they can write it themselves in 10 min. |
| Excel export with audit trail | **Yes** | What they send to the auditor. |
| Anomaly detection vs. history | Lukewarm | They already know what's unusual — they need to explain it, not detect it. |
| PDF parsing | Yes but expensive to build | Skip for 30h. |
| Multi-entity consolidation | Yes, premium tier | Skip for 30h. Real differentiator post-hackathon. |

Ship: **consolidation + reconciliation + Excel export.** Narrative is garnish — already built.

---

## 8. Market reality check

- **Vena / Anaplan / Planful / Workday Adaptive** — enterprise. $50K–$500K/yr. Require a consultant. Assume clean data.
- **Mosaic / Cube / Pry (pre-Brex)** — mid-market FP&A. $1K–$5K/mo. Connect to NetSuite/QuickBooks via API. Do NOT accept raw department Excel files. Require clean GL in.
- **Puzzle.io / Digits** — AI bookkeeping for SMBs. Replaces QuickBooks, not close workflow. Different problem.
- **Ramp / Brex / Bill.com** — spend management. Not close.
- **QuickBooks / Xero / NetSuite** — the GL itself. Produces the export we consume.

**The gap:** nobody ingests raw, messy, per-department Excel and produces a consolidated close package. That territory is served today by a human analyst and a shared Google Sheet. This is the wedge. The proposition names it correctly — the product just hasn't built it yet.

---

## 9. What to ignore for the next 30 hours

- Any new auth flow, onboarding change, Stripe/billing
- PDF support (2+ days even with a good library)
- Bank statement reconciliation (different data shape; breaks schema)
- New LLM models, prompt A/B tests, caching optimizations
- UI redesign beyond the specific components called out below
- Tests for new code beyond smoke tests on `consolidator.py`
- Multi-tenancy / multi-company
- pgvector, embeddings, semantic search

---

## 10. Hour-by-hour plan

Assumes one person working with Claude Code. Front-loaded so that if the clock runs out at hour 24, the product is still demoable.

### Hours 0–2: Decision + scaffolding
- Commit: multi-file consolidation is the headline. Everything else is support.
- Write and apply migration `0002_multi_source_consolidation.sql`.
- Update `MonthlyEntry` dataclass + repo for `source_breakdown`. Update `Report` dataclass + repo for `reconciliations`.

### Hours 2–8: ConsolidatorAgent (the only net-new logic)
- `backend/agents/consolidator.py`: takes `list[tuple[str, pd.DataFrame]]`, returns `(consolidated_df, list[ReconciliationItem])`.
- `rapidfuzz` account-name matching at 90% threshold; lower-confidence matches go into the existing low-confidence flow.
- Per consolidated account: total, per-source breakdown, deltas > $100 OR > 5%.
- Unit-test against two hand-crafted DataFrames (one "GL", one "Payroll dept") before wiring anything up.

### Hours 8–12: Orchestrator + route rewrite
- `routes.py:/upload` — pass ALL storage keys to ONE background task.
- `orchestrator.py` — `run_multi_file_parser_until_preview` loops files through the existing ParserAgent, calls `ConsolidatorAgent.consolidate()`, writes consolidated entries via `entries_repo.replace_period()`.
- Smoke test: upload `drone_mar_2026.xlsx` + a hand-crafted `drone_mar_payroll.xlsx` that disagrees on one account. Verify the reconciliation appears.

### Hours 12–18: Frontend consolidation UI
- Upload: multi-file with file chips + optional per-file "source label" (defaults to filename).
- ParsePreviewPanel: add "Sources" column showing which file contributed to each account line.
- **New** `<ReconciliationPanel>` — above AnomalyCards. Lists every mismatch with source breakdown.
- AnomalyCard: surface existing provenance — hover shows "from `payroll_mar.xlsx`, column `Gross Pay`."

### Hours 18–22: Interpreter + guardrail
- Add `reconciliations` to Interpreter's prompt context.
- Extend `narrative_prompt.txt` so output JSON has a `reconciliation_narrative` field.
- Verify the guardrail catches mismatches in reconciliation narrative numbers (it should — `numbers_used` covers all output numbers).

### Hours 22–26: Excel export endpoint
- `GET /report/{company_id}/{period}/export.xlsx`.
- Build with `openpyxl` (already a dependency). Three sheets: Consolidated P&L, Reconciliations, Source Breakdown.
- "Download Excel" button on report page.

### Hours 26–28: Demo data + rehearsal
- Second demo file: "marketing department submission" where Marketing line is $3K lower than the GL (simulates a reclass).
- Third demo file: "payroll export" where bonuses book differently than the GL.
- End-to-end walkthrough. Wow moment = drop three messy files → one consolidated P&L → three reconciliation flags with dollar deltas → one narrative explaining each.
- Time it. Must be under 2 minutes.

### Hours 28–30: Polish + buffer
- Fix the one thing that broke in rehearsal. There will be one.
- Record a 60-second backup video in case live demo fails.
- Sleep 2 hours if possible. A tired demo kills a good product.

---

## One-line summary

The proposition is correct. The product is only the interpretation layer of what that proposition promises. In 30 hours we can ship the consolidation layer and reconciliation layer using existing infrastructure with **one migration, one new agent file (~150 LOC), one orchestrator change, and targeted UI additions**. That closes the gap from 25% to ~80% delivered.

## Recommended starting point

**Build the `ConsolidatorAgent` first.** It is the only net-new logic, fully unit-testable in isolation, and nothing else unlocks until it exists.
