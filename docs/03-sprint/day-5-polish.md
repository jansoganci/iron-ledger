# Day 5 — Mail + E2E Tests + Polish
*IronLedger 6-Day Sprint — Built with Opus 4.7 Hackathon, April 2026*

## Goal

End-to-end pipeline is demo-ready: Resend is fully wired, a real HTML email arrives with the verified report + anomaly list. The full E2E test suite covers every critical path (PII in all blacklist categories, NetSuite XML edge case, rate limit, storage cleanup preservation-on-fail, stale report, invalid state transitions, RLS isolation between two users, empty state). Day-4 deferrals land (MappingConfirmPanel, EmptyState, Stale state, rate-limit cooldown). Code is lint-clean (`black`, `flake8`, frontend lint). No inline prompts anywhere. Every user-facing string routes through `messages.py` and its frontend mirror.

## End-of-Day Acceptance Check

> From a clean browser session:
> 1. Sign in as `demo@dronedemo.com`. Upload `drone_mar_2026.xlsx` (Feb 2026 baseline already loaded). Report renders with Verified badge.
> 2. Click **Send Email**. Enter a real inbox address (e.g. the developer's). Confirm a success toast fires. Open the inbox — email arrives within 30s with subject `[IronLedger] Mar 2026 — DRONE Inc.`, HTML body containing the narrative + anomaly list with US accounting numbers + link to the dashboard.
> 3. `SELECT mail_sent, mail_sent_at FROM reports WHERE ...` → `true` + timestamp.
> 4. Run `pytest` — **all tests green**, including all §7 tests.
> 5. Run `black --check .` + `flake8` on backend → clean.
> 6. Run `npm run lint` on frontend → clean.
> 7. Inline-prompt audit: `grep -rn "client.messages.create" backend/ | grep -v anthropic_llm.py` returns **zero results**. Every Claude call goes through the adapter.
> 8. Resize browser to 900px (tablet): every screen renders without overlap, horizontal scroll, or hidden CTAs. Resize to 400px (mobile): Dashboard/TrendChart hidden with friendly redirect, upload + report still usable.
> 9. Sign out. Sign in as a fresh 2nd demo user (no `monthly_entries`). Verify `EmptyState` renders with neutral palette.
> 10. **RLS isolation**: while signed in as user 2, issue `GET /report/<drone_company_id>/2026-03-01` via browser devtools → 403. Cannot see DRONE's data.
> 11. Re-upload `drone_mar_2026.xlsx` under demo user after report already exists. Verify ReportSummary shows **"Out of date"** amber chip with Regenerate CTA.
> 12. Force-load a run where mapping confidence was <80% (test fixture). Verify MappingConfirmPanel renders post-hoc; confirm a mapping; verify persistence in `accounts`. ✅

## Preconditions (from Day 1–4)

From Day 4:
- [x] Full browser flow: login → upload → progress → verified report
- [x] `GuardrailWarning` screen + `POST /runs/{id}/retry` endpoint
- [x] Toast system + ErrorBoundary live
- [x] `adapters/resend_email.py` scaffolded (port exists; actual Resend call stubbed)
- [x] `POST /mail/send` scaffold accepts the shape (Day 3) and UI wires to it (Day 4)
- [x] Provenance schema extension (`monthly_entries.source_column`) + response shape extended
- [x] `POST /mapping/confirm` + `GET /companies/me/has-history` endpoints live

From Day 3:
- [x] `GET /runs/{id}/status` + `/raw` + rate limits + HTTP status mapping + CORS verified
- [x] Storage cleanup on `complete` + file-stays-on-guardrail_failed rule

From Day 2:
- [x] DRONE Feb + Mar full pipeline producing `PandasSummary` → Interpreter → `reports` row
- [x] DELETE-then-INSERT on re-upload
- [x] Parser pipeline order: read → skip metadata → detect header → STRIP PII → pandera → map (Haiku) → normalize → write

From Day 1:
- [x] Clean Architecture layers intact
- [x] `RunStateMachine` enforced at every state write
- [x] `messages.py` single source of truth for user strings

External pre-requisites:
- `RESEND_API_KEY` valid
- **Resend sender domain verified** — this takes time to propagate; verify Day-4 evening so Day 5 doesn't block on DNS
- Test inbox reachable (e.g. developer's Gmail) to visually confirm email arrival
- 2nd test user in Supabase Auth (e.g. `demo2@dronedemo.com`) — created today for RLS + EmptyState tests

---

## Tasks

### 1. Resend Adapter — Full Wiring

- [ ] `adapters/resend_email.py` — implement the `EmailSender` port using the Resend Python SDK:
  ```python
  class ResendEmailSender:
      def send(self, to: str, subject: str, html: str, text: str) -> SendResult:
          response = resend.Emails.send({"from": "IronLedger <reports@...>",
                                         "to": to, "subject": subject,
                                         "html": html, "text": text})
          return SendResult(message_id=response["id"])
  ```
- [ ] Network retry: 3 attempts, 0.5s → 1.5s → 4s backoff (same pattern as Storage adapter), retry only on network/5xx. On exhaustion → raise `TransientIOError`. **The `POST /mail/send` handler maps `TransientIOError` to HTTP 500 + `messages.MAIL_FAILED`** (per `api.md` Error Codes Reference — `mail_failed → 500`).
- [ ] Do NOT retry 4xx (e.g. invalid sender, invalid recipient) — deterministic; surface immediately.
- [ ] **From address** uses `IronLedger Reports <reports@ironledger.ai>`. `# TODO: replace with verified Resend sender domain before launch` — `ironledger.ai` is a placeholder; the production sender must be a domain verified in Resend with SPF + DKIM propagated (start DNS Day-4 evening per risks.md R-003).

### 2. Email Template

- [ ] `backend/templates/report_email.html` — simple readable HTML (inline styles only — no external CSS for email client compatibility):
  - Header: "`{Month} {Year}` — `{Company Name}`"
  - "Verified · Guardrail Passed" badge (inline SVG check + teal `#0D9488` text) — mirrors the dashboard badge
  - Narrative text block (from `reports.summary`)
  - Anomaly list — each row: account name, severity chip (high/medium color), variance %, one-line description
  - Numbers formatted US-accounting: `$1,234`, `($1,234)` for negatives, `$4.73M` for narrative figures
  - CTA: "View full report in IronLedger →" linking to `${FRONTEND_URL}/report/${period}`
  - Footer: "Sent by IronLedger — month-end close, verified."
- [ ] `backend/templates/report_email.txt` — plain-text fallback (Gmail/Outlook plain-text mode clients)
- [ ] Use Jinja2 for templating (add `jinja2` to `requirements.txt`)
- [ ] **Rule:** every number in the HTML template uses the same `format_currency` helper as the backend API layer — single source of US accounting formatting
- [ ] Preview locally: render template with DRONE Mar 2026 fixture + open in a browser; verify tabular numerals, parenthesized negatives, badge rendering

### 3. `POST /mail/send` — Full Implementation

- [ ] Handler replaces the Day-3 scaffold:
  - Input: `{report_id: UUID, to_email: str}`
  - Fetch `reports` row via `ReportsRepo`; verify ownership via RLS (second layer on top of JWT)
  - Validate `to_email` as a basic email format
  - Render template with report + anomalies data
  - Call `EmailSender.send(...)` via injected port. **Returns `SendResult` Pydantic v2 model** (`domain/contracts.py`) — use `.model_dump()` to serialize.
  - On success: `UPDATE reports SET mail_sent=true, mail_sent_at=NOW() WHERE id=...`. Return `{status: "sent", message_id}`.
  - **On `TransientIOError`: return HTTP 500 with `messages.MAIL_FAILED`** — matches `api.md` Error Codes Reference (`mail_failed → 500`). Frontend surfaces error toast with manual retry.
- [ ] Rate limit: **10/hour per user** (already set Day 3)
- [ ] Audit log: `event="mail_sent"` with `trace_id`, `run_id`, `report_id`, `to_email_domain` (**log the domain, not the full address** — minor PII hygiene)

### 4. Day-4 Deferrals Land

#### MappingConfirmPanel
- [ ] Render below `ReportSummary` when `runs.low_confidence_columns` is non-empty
- [ ] Max 3 rows shown at once (lowest confidence first); remainder handled post-MVP
- [ ] Per-row: column name verbatim + agent's guess + confidence % + dropdown (REVENUE/COGS/OPEX/G&A/R&D/OTHER_INCOME/OTHER/SKIP)
- [ ] **Confirm Mappings** CTA (teal) — POSTs to `/mapping/confirm`; persists to `accounts`; dismisses the panel on success
- [ ] Note: this is the **non-blocking post-hoc** version (MVP decision from Day 2). Aspirational blocking modal remains post-MVP.

#### EmptyState (screen 6)
- [ ] Route: on `/upload`, call `GET /companies/me/has-history` before rendering. If `has_history=false`, render `EmptyState`.
- [ ] "Let's set up your baseline" headline, neutral palette only, muted folder glyph
- [ ] Period defaults to previous calendar month
- [ ] Primary CTA: "Upload baseline" (teal, disabled until file + period chosen)
- [ ] On baseline upload success: redirect to confirmation screen ("Baseline saved. Come back at month-end to run your first close."), NOT to a report page
- [ ] Nav items (Dashboard, History, Reports) dimmed with tooltip: "Available after your first upload."
- [ ] **Smoke test** with 2nd demo user (`demo2@dronedemo.com`) — verify EmptyState renders, successful upload transitions to baseline-saved screen.

#### Stale state on ReportSummary
- [ ] Logic: fetch `reports.created_at` + latest `monthly_entries.created_at` for the same `(company_id, period)`. If entries are newer than the report → stale.
- [ ] Render "Out of date" chip (amber `#FEF3C7`/`#B45309`) replacing the Verified badge
- [ ] Copy above body: "This report was generated before you re-uploaded the source file. [Regenerate report]."
- [ ] "Regenerate report" button → calls `POST /runs/{run_id}/retry`-pattern endpoint but for a fresh run on latest `monthly_entries` (since the file is already parsed, skip parser and re-run Comparison + Interpreter). **MVP shortcut**: treat Regenerate as a full re-upload trigger — user re-uploads the file, fresh run starts. Simpler, no new endpoint.
- [ ] MailButton disabled in Stale state.

#### Rate-limit cooldown countdown
- [ ] When fetch client catches 429, read `retry_after_seconds` from response header
- [ ] Warning toast fires (6s auto-dismiss)
- [ ] Button that triggered the request shows countdown badge ("Retry in 48s...") and is disabled until countdown ends
- [ ] Works on Analyze button, MailButton, Retry Analysis button

#### Tablet/mobile polish pass
- [ ] Screen-by-screen audit at 900px (tablet) and 400px (mobile):
  - Login, Upload, LoadingProgress, ReportSummary, AnomalyCard grid, GuardrailWarning, MappingConfirmPanel, EmptyState
- [ ] Fix any overflow, alignment, or illegible text issues
- [ ] Verify: severity chips + Verified badge never hidden at any breakpoint
- [ ] Verify: tables horizontal-scroll <1024px (if any tables are introduced)

### 5. E2E Test Suite — Backend (pytest)

Goal: every critical path has a test. Each test is green before Day 6.

- [ ] **`tests/test_parser_pipeline.py`**:
  - `test_drone_feb_baseline_load` — upload Feb, verify `monthly_entries` populated, no anomalies (no history)
  - `test_drone_mar_variance` — upload Mar after Feb, verify G&A −34% and Travel +61% in `anomalies` with correct severity
  - `test_csv_format` — upload DRONE data as CSV, same flow, same anomalies
  - `test_netsuite_xml_edge_case` — synthetic `.xls` with `<?xml` header, verify xlrd/XML parse path picks it up correctly
  - `test_delete_then_insert_on_reupload` — upload Mar twice, verify row count unchanged (no duplicates)
  - `test_pandera_error_surface` — upload file with non-numeric amount column, verify `messages.PARSE_FAILED` returned (no stack trace)
- [ ] **`tests/test_pii_sanitizer.py`**:
  - `test_ssn_header_stripped` — column named "SSN" dropped entirely; log emits column name, never value
  - `test_ssn_value_regex` — unmapped column with ≥20% SSN-pattern values dropped
  - `test_name_with_employee_id` — column "Name" stripped when sheet also contains `employee_id`; NOT stripped otherwise (legit account name)
  - `test_dob_stripped`, `test_home_address_stripped`, `test_bank_account_stripped`, `test_bank_routing_stripped`, `test_personal_contact_stripped` — each category of the header blacklist
  - `test_file_has_no_valid_columns` — all columns stripped → `FileHasNoValidColumns` raised → `messages.FILE_HAS_NO_VALID_COLUMNS` surfaced + run transitions to `parsing_failed`
  - **`test_pii_never_in_claude_context`** — mock `anthropic_llm.py`, assert the context payload never contains any PII value or header substring
  - `test_pii_sanitization_log_no_values` — capture log output, assert `event="pii_sanitization"` line contains column names + counts but no cell values
- [ ] **`tests/test_guardrail.py`**:
  - `test_guardrail_pass_on_clean_numbers` — narrative with numbers in `pandas_summary` → success
  - `test_guardrail_fail_on_mismatch` — narrative with "$200,000,000" not in summary → `GuardrailError` raised after 2 attempts
  - `test_guardrail_reinforced_prompt_on_retry` — attempt 1 uses `narrative_prompt.txt`, attempt 2 uses `narrative_prompt_reinforced.txt` (check logs for prompt path)
  - `test_guardrail_within_2pct_tolerance` — narrative says `$4.8M`, summary has `$4,730,000` → pass (within 2%)
  - `test_guardrail_fail_writes_no_report` — on `GuardrailError`, verify `reports` table has no new row
  - `test_guardrail_fail_preserves_storage_file` — on `GuardrailError`, verify file still exists in Supabase Storage
- [ ] **`tests/test_rate_limit.py`**:
  - `test_upload_429_after_5_per_min` — fire 6×/min, 6th returns 429 with `Retry-After` header and `messages.RATE_LIMITED` body
  - `test_status_poll_120_per_min` — verify polling under the cap doesn't trip 429
  - `test_composite_key_user_vs_ip` — authenticated user key, unauthenticated falls back to IP
- [ ] **`tests/test_storage.py`**:
  - `test_cleanup_on_complete` — after successful run, verify file no longer in Storage
  - `test_cleanup_skipped_on_guardrail_failed` — after guardrail_failed, verify file still in Storage
  - `test_cleanup_failure_logged_not_raised` — mock Storage delete to fail, verify WARNING log + run stays `complete`
  - `test_upload_retry_on_network_error` — mock first 2 attempts fail with network error, 3rd succeeds; verify `TransientIOError` NOT raised
  - `test_upload_transient_after_3_failures` — all 3 attempts fail; verify `TransientIOError` + run `upload_failed`
- [ ] **`tests/test_run_state_machine.py`**:
  - `test_valid_happy_path_transitions` — pending → parsing → mapping → comparing → generating → complete
  - `test_invalid_transition_raises` — e.g. `complete → parsing` raises `InvalidRunTransition`
  - `test_terminal_state_no_resume` — `guardrail_failed` cannot transition to anything; only a new `run_id` works
- [ ] **`tests/test_rls.py`** — the #1 security test:
  - Two users, two companies. User 1 uploads DRONE data. User 2's JWT:
    - `GET /report/<drone_company_id>/2026-03-01` → 403
    - `GET /anomalies/<drone_company_id>/2026-03-01` → 403
    - `GET /runs/<user1_run_id>/status` → 403
    - Raw SQL via user 2's PostgREST session → zero rows from DRONE's `monthly_entries`
    - Storage: user 2 cannot download user 1's stored file
- [ ] **`tests/test_empty_state.py`**:
  - `test_has_history_false_for_fresh_user` — new user, no entries → `GET /companies/me/has-history` returns `{has_history: false}`
  - `test_has_history_true_after_baseline_upload` — after first entry write, endpoint returns `true`
- [ ] **`tests/test_stale_report.py`**:
  - Generate report. Re-upload file (new `monthly_entries.created_at` > `reports.created_at`). Verify frontend stale-state trigger condition (backend query logic).
- [ ] **`tests/test_mapping_confirm.py`**:
  - Upload file with low-confidence column. Verify `runs.low_confidence_columns` populated. POST to `/mapping/confirm` with user choice. Verify `accounts.category_id` updated. Re-upload same file: same column now mapped silently (no low-confidence entry).

### 6. E2E Test Suite — Frontend (in-browser smoke)

Formalize the Day-4 smoke list as a manual checklist (Playwright is too heavy for hackathon scope).

- [ ] `docs/sprint/browser-smoke.md` (temp file, delete Day 6) — checklist of 15 in-browser verifications from Day 4 §End-of-Day-Check + 3 new Day-5 additions:
  - Email arrival test (§1)
  - Stale state (§4)
  - Rate-limit countdown (§4)
- [ ] Run through twice — once on desktop Chrome, once on mobile-emulated view in devtools
- [ ] Accessibility spot-check: Tab key cycle through Login, Upload, Report screens; Esc closes modals; `prefers-reduced-motion` toggled → toast slides become fades

### 7. Polish

#### Loading states everywhere
- [ ] Every data-fetching component has a skeleton state: `ReportSummary` (already Day 4), `AnomalyCard` (already Day 4), MappingConfirmPanel (add), EmptyState (transitions are fast, spinner OK), MailButton ("Sending..." label).

#### `messages.py` audit
- [ ] Verify every key listed in `messages.py` is **used** somewhere in backend code (grep)
- [ ] Verify every user-facing string in backend code **maps to** a key (no inline strings)
- [ ] Frontend mirror `src/lib/messages.ts` has the same keys as backend for any string the frontend renders

#### Inline-prompt audit
- [ ] `grep -rn "client.messages.create" backend/ | grep -v anthropic_llm.py` → zero results
- [ ] `grep -rn "You are a" backend/agents/ backend/tools/` → zero results (catches accidental inline personas)
- [ ] Verify `backend/prompts/` contains: `mapping_prompt.txt`, `narrative_prompt.txt`, `narrative_prompt_reinforced.txt` — nothing else

#### Prompt git-SHA logging verification
- [ ] Run a Haiku call, then Opus call. Grep logs for `prompt_sha=`. Verify both log lines include a 40-char SHA.
- [ ] Cross-check: `git hash-object backend/prompts/mapping_prompt.txt` matches the SHA in the log.

#### Backend lint
- [ ] `black .` — format all Python files
- [ ] `flake8` — zero errors. Fix or ignore-with-justification.
- [ ] `mypy backend/` (optional but recommended if time) — zero errors on `domain/`, soft pass elsewhere

#### Frontend lint
- [ ] `npm run lint` (ESLint + Prettier defaults from Vite) → clean
- [ ] No `console.log` in production paths (console.error for ErrorBoundary is fine)

#### Error copy sync
- [ ] For each `messages.<KEY>` in backend, there's a matching `messages.<KEY>` in `src/lib/messages.ts` with identical wording
- [ ] Any plain-English string the frontend renders that doesn't come from backend response body is in `messages.ts` (e.g. client-side file rejection)

### 8. Day-6 Pre-staging

Tasks that make Day 6 smoother without being Day-6 work:

- [ ] Draft Day-6 demo script in `docs/runbook.md` — verify/update against the final product (screens may have drifted from the Day-1 draft)
- [ ] `.env.example` — every env var used anywhere is documented
- [ ] Deploy readiness:
  - `requirements.txt` committed, `package.json` committed with lockfile
  - Backend starts with `uvicorn backend.main:app --port 8000` without error
  - Frontend `npm run build` succeeds
- [ ] Verify Resend sender domain DNS propagation is fully live (not just "verified" in Resend UI)
- [ ] Record a backup demo video (Loom or QuickTime) **tonight** — if Day 6 live demo fails, share the backup (per `docs/runbook.md`)
- [ ] Create a demo-data cache: run the full pipeline once Day 5 evening on the live Railway+Vercel targets (Day 6 will have this ready)

---

## Internal Sequencing

1. **Resend + email template (§1–3)** — must ship first; everything else is testing. Send a real email to yourself to confirm before writing tests.
2. **Day-4 deferrals (§4)** — MappingConfirmPanel, EmptyState, Stale state, rate-limit countdown. Individually small; batch while the UI is fresh.
3. **Backend E2E tests (§5)** — start with PII (highest risk), then guardrail, then RLS, then the rest. PII + guardrail + RLS are the three that must be green before ANY demo.
4. **Frontend smoke (§6)** — after all backend tests green.
5. **Polish (§7)** — `black` + `flake8` + lint + message audits — fast, mechanical, do last before Day 6 staging.
6. **Day-6 pre-staging (§8)** — env vars, build check, backup video recording. Low-effort, high-value insurance for demo day.

Rule of thumb: **Resend first, tests next, polish last.** A broken email during demo is visible to judges; a failing test is only visible to you.

---

## Contracts Produced Today

### Email delivery contract
```
POST /mail/send
  → Validate ownership (RLS on report_id)
  → Render HTML template with format_currency helper
  → EmailSender.send(...)
  → On success: UPDATE reports SET mail_sent=true, mail_sent_at=NOW()
  → Return {status: "sent", message_id}
  → On failure: 503 with messages.MAIL_FAILED
```

### Email template
`backend/templates/report_email.html` + `.txt` — frozen today; any future edit goes through doc review (templates are user-facing; changes have UX impact).

### Test coverage baseline
12 test files + ~40 individual tests covering:
- Parser pipeline (6)
- PII (9)
- Guardrail (6)
- Rate limit (3)
- Storage (5)
- State machine (3)
- RLS isolation (5)
- Empty state (2)
- Stale report (1)
- Mapping confirm (1)

This is the baseline. Day 6 may add demo-day-specific tests; no test deletion without approval.

### Lint baseline
`black --check .`, `flake8`, `npm run lint` all clean. Any violation Day 6 is a regression and must be fixed before demo.

---

## Cut Line

### Must ship today (non-negotiable)
- Resend full wiring + real email arriving with formatted HTML
- `POST /mail/send` full implementation with `reports.mail_sent=true` side effect
- Backend tests: PII (all categories), Guardrail (pass + fail + retry), RLS isolation, DELETE-then-INSERT, Storage cleanup preservation-on-fail, Run state machine invalid transition
- `black .` + `flake8` clean
- Inline-prompt audit passes (zero inline prompts)
- MappingConfirmPanel (needed for demo "oh this flagged" moment — low-effort, high-impact)

### Deferrable to Day 6 morning
- EmptyState implementation (DRONE demo uses a pre-loaded baseline, so demo never hits Empty State — but judges may explore a 2nd account)
- Stale state on ReportSummary
- Rate-limit cooldown countdown (warning toast alone is enough for demo)
- Frontend lint cleanup beyond critical errors
- `messages.py` audit refinements
- Mobile polish pass (demo is on desktop)

### Defer to post-MVP
- Playwright/Cypress E2E automation (manual browser smoke is enough for hackathon)
- `mypy` strict mode everywhere
- Email template A/B visual polish (Mercury-style minimalism is the bar; don't over-design)
- Mail send history / audit log table (beyond `reports.mail_sent` flag)
- Multi-recipient `to_email` (MVP is single recipient)
- Aspirational blocking MappingConfirmModal

---

## Risks (this day)

| Risk | Impact | Mitigation |
|---|---|---|
| Resend sender domain DNS not propagated | Emails silently fail or go to spam | Start DNS verification **Day 4 evening** so propagation happens overnight; Day 5 morning confirms with a test send |
| Resend API quota exhausted during testing | All mail tests fail; demo blocked | Use free-tier budget carefully; route test sends to a single inbox; Resend's free tier allows ~100/day — more than enough |
| RLS test reveals a leak | Major security issue late in sprint | Top priority Day-5 morning test; if any RLS test fails, drop all other work until fixed |
| Test suite eats the whole day | Polish + Day-4 deferrals cut; demo is visibly rough | Parallelize: write test stubs first, implement features (§1–4) in parallel, then fill test bodies |
| Inline-prompt audit finds violations | Prompts slipped past code review during Days 2–3 | Simple `grep` catches it; fix by moving to `prompts/` folder + re-load via adapter; re-run tests |
| Email template renders poorly in Outlook / Gmail plain-text | Looks broken to judges | Test in 3 clients before end of day: Gmail web, Outlook web, iOS Mail. Inline styles only (no `<style>` blocks). Plain-text fallback provided. |
| `black` reformat breaks something | Tests red after format | Run `black` before any test runs; all formatting caught early |
| MappingConfirmPanel regression breaks report path | Demo shows broken panel instead of clean report | Gate rendering on `low_confidence_columns.length > 0`; if empty, panel never mounts |
| Stale state over-triggers (clock drift) | Every fresh report immediately shows "Out of date" | Compare timestamps with ≥5s tolerance; use `updated_at` not `created_at` for entries |
| `mail_sent` flag not persisted on success | User gets email but UI shows unsent state | Unit test the side effect; verify via SQL in E2E test |
| 2nd user creation accidentally seeds DRONE company | RLS test gives false pass | Carefully script the 2nd user creation: email + password only, no company row; verify via `SELECT COUNT(*) FROM companies WHERE owner_id=<user2>` == 0 |
| Demo recording (backup video) eats 30 minutes | Day 5 runs late | Batch: record after §1–4 green; re-record Day 6 if anything changed significantly |
| Rate-limit countdown has off-by-one or negative values | Looks buggy on demo day | Clamp countdown to `max(0, retry_after - elapsed)`; test with fast-forward mock |
| Email arrives in spam folder | Judges think email was never sent | Verified sender domain + SPF/DKIM; send from a domain you control, not Gmail relay |

Cross-day risks (tracked in `risks.md`): Railway cold-start during Day-6 demo, Opus quota exhaustion, Day-6 submission deadline (April 26, 8 PM EST).

---

## Reference Docs

Read these before starting Day 5 tasks.

- **`CLAUDE.md`** — Retry & Error Handling (storage cleanup), Coding Standards (error messages plain English, prompts in `prompts/`, no Claude math), Model Strategy
- **`docs/scope.md`** — Success Criteria (real DRONE Excel uploadable, plain English report, guardrail works, email sent), INCLUDED list (rate limiting, PII sanitization, RLS, trace_id, messages.py)
- **`docs/tech-stack.md`** — Orchestration (three agents via Supabase bus), Numeric Guardrail
- **`docs/agent-flow.md`** — Error Handling table (every error → agent response mapping; tests verify each row)
- **`docs/db-schema.md`** — RLS policies, `reports.mail_sent` field
- **`docs/api.md`** — `POST /mail/send` response shapes, Error Codes Reference
- **`docs/design.md`** — Email is the one user-facing surface not covered in `design.md` — match the Mercury-minimal aesthetic (teal accent, `#FAFAF9` background, Inter typography, tabular numerals)
- **`docs/runbook.md`** — Day-6 demo script (review today, update if drift)
- **`docs/sprint.md`** — Day 5 section (reconciled v3)
