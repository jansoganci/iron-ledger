---
name: financial-validator
description: Use this skill before finalizing any financial report, running the agent pipeline, or writing narrative output. Enforces the IronLedger architectural rules for data integrity and agent flow.
---

# IronLedger Financial Validator Skill

## When to use this skill
- Before writing any Claude narrative (Interpretation agent)
- Before saving anything to the `reports` table in Supabase
- When debugging why a report was rejected by the guardrail
- When adding a new file type or data source to the parser

## The Golden Rule
Claude never does arithmetic. All numbers come from Python/pandas.
Claude only writes prose that describes what pandas already calculated.

## Agent Pipeline — Always follow this order

1. **Parser agent** (`backend/agents/parser.py`)
   - Detects file format (xlsx, csv, xls, xlsm)
   - NetSuite edge case: `.xls` may be XML Spreadsheet 2003 — check first 2 bytes
   - Strips ERP metadata rows (first 0-10 rows)
   - Maps columns to US GAAP categories: REVENUE, COGS, OPEX, G&A, R&D, OTHER_INCOME
   - Validates with pandera schema
   - Writes to `monthly_entries` table

2. **Comparison agent** (`backend/agents/comparison.py`)
   - Python only — no Claude calls in this agent
   - Pulls history from Supabase via SQL join (no pgvector)
   - Calculates variance: `((current - avg) / abs(avg)) * 100`
   - Threshold: ±15% = medium, ±30% = high
   - Aggregates to account-level summary before any Claude call
   - Writes flagged items to `anomalies` table

3. **Interpretation agent** (`backend/agents/interpreter.py`)
   - Claude receives ONLY the aggregated pandas_summary dict — never raw rows
   - Claude must return JSON: `{"narrative": "...", "numbers_used": [...]}`
   - Numeric guardrail runs immediately after Claude responds
   - If guardrail fails: retry once with stronger prompt
   - If retry fails: raise GuardrailError, do not write to `reports`
   - **Anomaly classification is folded into this agent.** Severity (low/medium/high) is
     already set by Python in comparison.py using fixed thresholds. Claude writes only
     the one-sentence business reason per flagged item, inside the same narrative JSON.
     No separate anomaly classification call, no separate prompt file, no separate model.

## Guardrail Checklist
Before any report is written to Supabase, verify:
- [ ] Claude returned valid JSON with `narrative` and `numbers_used` fields
- [ ] Every number in `numbers_used` exists in `pandas_summary` within 2% tolerance
- [ ] No rounding or abbreviation in `numbers_used` array (e.g., 4730000 not 4.73)
- [ ] `company_id` is present and matches the uploaded file's company

## What Claude should NEVER do in this project
- Calculate variance, totals, averages, or percentages
- Write prompts inline in Python code
- Access raw DataFrame rows (only aggregated summary)
- Write to `reports` table before guardrail passes
- Use pgvector (Post-MVP — SQL joins only this week)

## Auth / data isolation
- Every protected endpoint validates the Supabase JWT before doing anything.
- `company_id` is NEVER accepted from the client — it is resolved server-side from
  `companies.owner_id = auth.uid()`.
- RLS is enabled on `companies`, `accounts`, `monthly_entries`, `anomalies`, `reports`,
  `runs`. `account_categories` is a public lookup table (no RLS).
- File uploads land in `financial-uploads/{auth.uid()}/{period}/{filename}` — never
  hardcode `company_id` as the folder key.
