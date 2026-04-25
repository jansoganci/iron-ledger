---
name: code-auditor
description: Use this skill to audit newly written code for architectural consistency, security issues, and adherence to IronLedger coding standards. Run after completing any agent, tool, or endpoint.
---

# IronLedger Code Auditor Skill

## When to use this skill
- After writing or editing any file in `backend/agents/`
- After writing or editing any file in `backend/tools/`
- When something feels inconsistent with the architecture
- Before submitting the hackathon project

## Audit Checklist — Run through every item

### 1. Golden Rule Compliance
- [ ] Does this file contain any arithmetic operations that should be in pandas?
- [ ] Does any Claude prompt ask it to calculate, sum, average, or compare numbers?
- [ ] Are all Claude prompts loaded from `backend/prompts/` — not written inline?

### 2. Agent Boundaries
- [ ] Does `comparison.py` contain any `client.messages.create()` calls? (It should NOT)
- [ ] Does `interpreter.py` receive raw DataFrame rows? (It should NOT — only aggregated summary)
- [ ] Does `parser.py` call Claude for anything other than column mapping? (It should NOT)

### 3. Guardrail Integrity
- [ ] Is `verify_guardrail()` called before every `supabase.table('reports').insert()`?
- [ ] Does the guardrail use 2% tolerance (`tolerance=0.02`)?
- [ ] Is retry logic present — max 2 attempts before GuardrailError?
- [ ] On GuardrailError, is the raw pandas data offered as download (not discarded)?

### 4. Data Isolation + Auth
- [ ] Every protected endpoint has a JWT-validation dependency (`Authorization: Bearer`)
- [ ] `company_id` is NEVER read from request body/query — always resolved from `companies.owner_id = auth.uid()`
- [ ] Every Supabase query includes `.eq('company_id', company_id)` filter (defense in depth over RLS)
- [ ] RLS is enabled on: companies, accounts, monthly_entries, anomalies, reports, runs
- [ ] `account_categories` is the only table WITHOUT RLS (it is a public lookup)
- [ ] No payroll or PII data is logged to console or stored beyond the session

### 5. File Format Handling
- [ ] Does `file_reader.py` handle these formats: `.xlsx`, `.csv`, `.xls`, `.xlsm`?
- [ ] Is the NetSuite edge case handled? (`.xls` that is actually XML — check first 2 bytes)
- [ ] Is `data_only=True` used when opening `.xlsm` files with openpyxl?

### 6. Error Messages
- [ ] Are all user-facing error messages in plain English — no technical terms?
- [ ] Example check: search for "SchemaError", "KeyError", "TypeError" in user-facing strings

### 7. Pre-Submit Final Audit
- [ ] Demo company name is "DRONE Inc." everywhere — no "DRONE Inc." references in code or comments
- [ ] No `.env` values hardcoded anywhere
- [ ] All `prompts/*.txt` files committed to repo
- [ ] `schema.sql` is up to date with all 6 tables
- [ ] GitHub repo is public
- [ ] Demo video is max 3 minutes
