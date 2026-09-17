# Month Proof — Current Status

*Living page. Last updated: 16 September 2026.*
*If this file disagrees with code, tests, or `supabase/migrations/`, the code wins.*

This is the one-page picture of the product as it actually runs. April 2026 sprint
trackers (`YAPILACAKLAR.md`, Day 1–6 notes) describe the hackathon, not today.

---

## What the product is

Month Proof is an AI-assisted month-end close app for US finance teams.

Drop messy Excel/CSV files → Python finds structure, maps accounts, consolidates
sources, flags variances → Claude writes a plain-language report → a numeric
guardrail checks the numbers before anything is saved as verified.

**Golden rule:** numbers come from pandas. Prose comes from Claude. The guardrail
must pass before a report is persisted.

---

## What works today

| Area | In the product |
|---|---|
| Upload | `.xlsx`, `.xls`, `.xlsm`, `.csv`, including NetSuite XML Spreadsheet 2003 |
| Pipeline | Discovery → optional user confirm → account mapping → parse/normalize → multi-source consolidation + recon → preview confirm → history comparison → narrative + guardrail |
| Mapping (this slice) | Vendor and expense names can be remembered per company. Payroll lines skip review and go straight into the close. Conflicts with Haiku ask the user. Saved names are edited on Data, not in the sidebar. |
| Auth / tenancy | Supabase Auth JWT. `company_id` is resolved server-side. RLS on company-owned tables. |
| Frontend | Login, register, onboarding, Dashboard, Upload, Data (entries + saved names), Reports, monthly/quarterly report views |
| Demo fixtures | `docs/demo_data/` — Redhawk is the seed company; Riverbend is the cash/three-way demo |
| Email | Frontend can open a `mailto:` draft. Backend Resend adapter is still a stub |

Migrations currently go through `0011_add_source_account_mappings.sql`.

---

## Locked product decisions (mapping)

These are not open questions:

- Remember **vendors and general expense items** (electricity, phones, vehicle
  rentals, and other AP-style names).
- Do **not** remember payroll people. A payroll file enters the close as its
  total and/or its sub-lines (meals, office rent, salary, bonus) without a
  mapping review.
- If a saved mapping **disagrees with Haiku**, stop and ask the user.
- **No Mapping item in the sidebar.** Review happens on Upload; revise happens
  on Data → Saved names.

Spec: `docs/sprint/pre-analysis-source-mappings.md`.

---

## Real gaps (do not treat the April TODO as the backlog)

Still unbuilt or parked — details in `docs/06-reports/pending-decisions-audit.md`:

| Item | Status |
|---|---|
| Close-flow checklist / tie-out / sign-off | Decided in `close-flow-contract.md`, not coded |
| Guardrail narrative↔`numbers_used` consistency | Measured, still warn-only (`ENFORCE_NARRATIVE_CONSISTENCY = False`) |
| Quarterly + Opus-upgrade guardrail | Still on the legacy tolerance, by current design |
| Backend email send | Stubbed |
| GL + department double-count in consolidator `_roll_up` | Known, out of this slice |
| Kova Items 2 / 3 / 6 | Parked until a real dealer file or product decision arrives |
| 4-layer mapping, financial canvas, sidebar Mapping page | Explicitly out of scope |

---

## How to verify

```bash
pip install -r requirements.txt -r requirements-dev.txt
npm --prefix frontend install
pytest
black --check backend tests
flake8 backend tests
npm --prefix frontend run typecheck
```

Do not call paid LLM APIs, seed a remote database, or send email unless those
services are intentionally in this environment.
