# AGENTS.md

This file guides coding agents working in this repository. It applies to the
entire tree unless a more specific `AGENTS.md` exists in a subdirectory.

## Product and priorities

Month Proof is an AI-assisted month-end close application. It ingests Excel or
CSV finance data, normalizes and reconciles it, compares it with historical
periods, and produces a plain-language report.

The central trust rule is:

> Numbers come from deterministic Python/pandas code. The LLM writes prose. The
> numeric guardrail verifies the prose before a report is persisted.

Protect financial correctness, tenant isolation, PII safety, and auditability
before optimizing convenience or UI polish.

## Source of truth

Use this order when repository documentation disagrees:

1. Current code, tests, and Supabase migrations
2. `AGENTS.md`
3. `docs/01-architecture/` and `docs/04-status/`
4. `CLAUDE.md` and `README.md`

Some docs describe an older three-agent/six-migration version of the product.
The current implementation also includes discovery, account mapping,
multi-source consolidation, reconciliation, and quarterly reporting. Verify
claims against the code before relying on them.

## Repository map

- `backend/domain/`: pure business types, contracts, errors, ports, and run
  state transitions. Do not import vendor SDKs here.
- `backend/agents/`: application workflows and financial use cases.
- `backend/adapters/`: Supabase, Anthropic, storage, and email implementations.
- `backend/api/`: FastAPI routes, authentication, dependencies, middleware, and
  rate limiting. Keep routes thin.
- `backend/tools/`: deterministic, stateless parsing, validation, sanitizing,
  calculation, guardrail, and export helpers.
- `backend/prompts/`: all LLM prompts. Do not embed substantial prompts in code.
- `frontend/src/`: React/Vite/TypeScript client.
- `supabase/migrations/`: ordered database history. Add a new migration; do not
  rewrite an applied migration.
- `tests/`: mirrors backend areas with domain, tool, agent, API, adapter, and
  integration tests.
- `docs/demo_data/`: checked-in finance fixtures for manual and integration
  testing. Do not casually modify these binary fixtures.
- `video/`: separate Remotion demo-video project; it is not part of the app
  runtime.

## Non-negotiable invariants

### Financial integrity

- The LLM must never calculate totals, variances, severities, reconciliations,
  thresholds, or other financial facts. Compute these in Python/pandas.
- Give the LLM only deterministic, structured context and validate its response
  with Pydantic contracts.
- A report may be saved or shown as verified only after
  `backend/tools/guardrail.py` passes.
- Do not weaken guardrail tolerances or omit reference values merely to make a
  failing narrative pass. Fix the deterministic data or prompt/output contract.
- Preserve Decimal/date semantics at boundaries where rounding or serialization
  could change financial meaning.

### Security and privacy

- Never accept or trust `company_id` from the browser. Resolve it from the
  authenticated user on the server.
- Every company-owned query and write must preserve `company_id` isolation and
  Supabase RLS assumptions.
- PII sanitization must happen before sample extraction, derived-row
  persistence, or any LLM request. Raw uploads may remain in the existing
  user-scoped storage workflow, but must never be logged or sent to an LLM.
  Never log raw cell values, tokens, secrets, or PII.
- Keep secrets in environment variables. Do not commit `.env`, service-role
  keys, JWT secrets, API keys, or real customer data.
- Keep user-facing backend messages centralized in `backend/messages.py`.
- Proactively fix OWASP Top 10 risks whenever you encounter them in files you
  are already working on, even if the user did not explicitly ask for security
  remediation. Keep the fixes scoped and add or update relevant security tests.

### Architecture and workflow

- Agents depend on protocols from `backend/domain/ports.py`; third-party SDK
  imports belong in adapters and dependency wiring.
- Business logic belongs in agents/domain/tools, not FastAPI route handlers or
  React components.
- Change run statuses only through `RunStateMachine.transition()` and update the
  transition table and tests together when adding a state or path.
- Treat terminal run states as immutable audit records. Retries create a fresh
  run unless the existing workflow explicitly defines otherwise.
- Keep prompts in `backend/prompts/` and parse LLM output through an explicit
  Pydantic schema.
- Use Pydantic v2 APIs (`model_validate`, `model_dump`, `model_dump_json`).

## Backend conventions

- Target Python 3.11. Add `from __future__ import annotations` to new backend
  modules and use modern type hints.
- Prefer small pure functions for financial transformations and unit-test edge
  cases such as zero history, negative values, missing values, rounding, and
  duplicate inputs.
- Keep repository row-shape conversion inside adapters. Main-loop financial
  entities use the dataclasses in `backend/domain/entities.py`.
- Translate infrastructure failures into the domain exceptions in
  `backend/domain/errors.py`; do not expose raw vendor errors to users.
- Preserve supported inputs: `.xlsx`, `.xls`, `.xlsm`, and `.csv`, including the
  NetSuite XML Spreadsheet 2003 edge case handled by the file reader.
- Avoid broad exception swallowing. If a workflow fails, log structured context
  without sensitive values and move the run through a valid failure transition.

## Frontend conventions

- Use TypeScript and functional React components. Do not introduce `any` when a
  request/response or component type can be expressed directly.
- Route API calls through `frontend/src/lib/api.ts` so JWT attachment, trace IDs,
  and 401/403/429/5xx handling remain consistent.
- Route auth behavior through the existing auth context/helpers and Supabase
  client; do not store service credentials in the frontend.
- Reuse the tokens and semantic classes in `frontend/src/index.css`. Severity,
  favorable direction, and agent activity are distinct visual meanings.
- Financial numbers should use the shared formatters and tabular numerals. Do
  not duplicate currency/percent formatting in components.
- Preserve accessible labels, keyboard behavior, focus states, loading states,
  empty states, and text in addition to color for status.

## Database changes

- Create the next numbered SQL file in `supabase/migrations/` for schema changes.
- Enable and verify RLS for new company-owned tables. Policies must derive
  access through the authenticated owner relationship.
- Add indexes and constraints that support the access pattern and financial
  uniqueness rules; do not rely only on application checks.
- Update adapters, domain contracts/entities, API types, tests, and relevant docs
  when a schema shape changes.

## Commands

Run from the repository root unless noted otherwise.

```bash
# Install
pip install -r requirements.txt -r requirements-dev.txt
npm install
npm --prefix frontend install

# Develop
npm run dev
npm run dev:backend
npm run dev:frontend

# Backend verification
pytest
pytest tests/tools/test_guardrail.py
black --check backend tests
flake8 backend tests

# Frontend verification
npm --prefix frontend run typecheck
npm --prefix frontend run build

# Database migrations (requires a configured Supabase project)
supabase db push
```

Do not run external-service integration tests, apply remote migrations, seed a
database, send email, or call paid LLM APIs unless the task requires it and the
needed environment is explicitly available.

## Testing expectations

- Add or update tests for every behavior change. Prefer the narrowest relevant
  test while iterating, then run the broader affected suite.
- Financial calculation or narrative changes require deterministic calculation
  tests and guardrail tests, including an intentional mismatch.
- Parser changes require tests proving PII is removed before any LLM boundary
  and covering the affected file-format edge case.
- Auth/repository/database changes require tenant-isolation and authorization
  coverage.
- Run-state changes require allowed and forbidden transition tests.
- API changes require status code, response body, auth, and error-path tests.
- Frontend changes should at minimum pass typecheck and production build; manually
  exercise the changed flow when no UI test covers it.
- If a check cannot run because credentials or services are unavailable, report
  that clearly instead of claiming it passed.

## Working practices

- Inspect nearby code and tests before editing; follow established patterns.
- Preserve unrelated user changes in a dirty worktree.
- Keep changes scoped. Avoid opportunistic refactors in financial or auth paths.
- Do not edit generated artifacts such as `*.tsbuildinfo`, caches, rendered
  videos, or package lockfiles unless the dependency graph actually changes.
- Update documentation when behavior, commands, architecture, environment
  variables, migrations, or user-visible flows change.
- In the handoff, summarize changed files, verification performed, and any
  remaining risks or skipped checks.
