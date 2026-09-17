# Month Proof — Cross-Day Risk Register
*Month Proof 6-Day Sprint — Built with Opus 4.7 Hackathon, April 2026*

Live, append-only register of risks that span multiple sprint days. Risks isolated to a single day live in that day's file under **Risks (this day)**.

---

## Purpose

Day files record risks scoped to one day's work ("Haiku rate-limit during testing"). This file records risks that:

- Span multiple days (a Day-1 decision that fires on Day-4, Day-5, or Day-6)
- Depend on external systems we don't control (Railway, Anthropic, Resend, Supabase, the submission platform)
- Expose a **design gap** in the docs we resolved with an MVP shortcut — the shortcut is tech debt worth tracking
- Represent **intentional scope cuts** (post-MVP backlog) that we want to remember as "decided, not forgotten"

## How to Use

- Each risk has a stable ID (`R-001`, etc.) so day files and commit messages can reference it durably.
- When a risk **fires** during the sprint, update its status to `fired` and append a **Fired Log** entry at the bottom of this file with what happened and how it was resolved.
- When a risk is **mitigated** (the fallback shipped, the DNS propagated, the test went green), mark `mitigated` but keep the entry — the mitigation itself is context.
- When a risk is **retired** (no longer applicable — day passed, decision reversed), strike it through but do NOT delete.
- **Never delete an entry.** History is context.

## Risk Schema

```markdown
### [R-XXX] Title
**Status:** open | mitigated | fired | accepted | retired
**Severity:** high | medium | low
**Category:** external | security | design | schedule | demo | post-mvp
**Raised:** date  **Updated:** date  **Owner:** day-N file or person
**Fires when:** scenario that triggers the risk

**Description:** what's at stake and why
**Mitigation:** what we've done / plan to do
**Trigger action:** runbook if the risk fires
**Referenced by:** day files + sections
```

---

## Legend

- **Status: open** — live risk, not yet mitigated
- **Status: mitigated** — risk is fully addressed; entry kept as context
- **Status: fired** — risk actually happened; see Fired Log
- **Status: accepted** — known risk we chose not to mitigate (e.g. post-MVP backlog)
- **Status: retired** — no longer applicable; keep for history

---

## Active Risks

### External Dependencies

#### [R-001] Railway cold-start during live demo
**Status:** open
**Severity:** high
**Category:** external
**Raised:** Day 1  **Owner:** day-6-demo.md
**Fires when:** Judges watch the live demo; Railway container has been idle >15 min; cold start adds ~10s to the first request

**Description:** Railway free tier cold-starts in ~10s after inactivity. The Hook beat of the demo (0:00–0:20) immediately transitions to Upload (0:20–0:45) — if the first `POST /upload` hits a cold container, the progress bar stalls during the very first action, looks broken.

**Mitigation:**
- Pre-demo checklist fires 5× `GET /health` at 30 min, 15 min, and 5 min before stage (day-6 §7)
- localhost + ngrok fallback tested before stage
- Loom backup video uploaded + link bookmarked

**Trigger action:**
1. If `/health` times out twice consecutively within 5 min of demo → cut to localhost + ngrok *before* stage, not during
2. If cold start fires mid-demo → narrate the architecture during the wait: "Three agents running in sequence — Parser, Comparison, Interpreter. While this loads, let me explain the guardrail…"

**Referenced by:** day-1 §Risks, day-6 §1, §6, §7, `runbook.md` Cold Start Warning

---

#### [R-002] Anthropic quota exhaustion (Haiku + Opus)
**Status:** open
**Severity:** high
**Category:** external
**Raised:** Day 2  **Owner:** day-3-interpreter.md
**Fires when:** Development testing + test suite + rehearsals consume quota before demo day; live demo hits rate limit

**Description:** Parser calls Haiku once per upload; Interpreter calls Opus 1–2× per upload (guardrail retry on failure). Across 6 days of development + Day-5 test suite runs + Day-6 rehearsals + live demo, easy to exhaust quota if budget is tight.

**Mitigation:**
- Parser caches confirmed mappings to `accounts` — re-uploads don't re-call Haiku
- Test suite uses mocked `LLMClient` wherever possible (only integration tests hit real Anthropic)
- Day 5 evening + Day 6 morning: check remaining Anthropic quota before rehearsals
- Rehearsal budget: 2 full runs on live URL (~4 LLM calls total, including guardrail retry headroom)

**Trigger action:**
1. If quota exhausts mid-Day-5 → finish test suite on mocks, leave 1 live integration run for demo
2. If quota exhausts mid-demo → pivot to Loom backup video

**Referenced by:** day-2 §Risks, day-3 §Risks, day-5 §Risks

---

#### [R-003] Resend sender DNS propagation delay
**Status:** open
**Severity:** high
**Category:** external
**Raised:** Day 4  **Owner:** day-5-polish.md
**Fires when:** DNS records (SPF, DKIM, DMARC, sender domain) added too close to Day-5 morning; Resend rejects sends or emails land in spam

**Description:** Resend requires verified sender domain with DNS records propagated. Propagation can take 12–48 hours. Starting too close to Day 5 risks Day-5 mail tests failing, which masks whether the wiring itself is correct.

**Mitigation:**
- Start DNS setup **Day 4 evening** so propagation happens overnight
- Day 5 morning: confirm with a test send before beginning §1 work
- Avoid Gmail relay — use a domain you control to reduce spam-folder risk

**Trigger action:**
1. If DNS not propagated Day-5 morning → temporarily use Resend's default sender (`onboarding@resend.dev`) for testing; switch to verified sender when DNS lands; re-run mail tests
2. If emails land in spam during demo → show UI success toast + pivot verbally: "email is also persisted in the dashboard as `mail_sent: true`"

**Referenced by:** day-5 §Preconditions, day-5 §Risks, day-6 §1 Resend env var

---

#### [R-004] Supabase free tier rate limits
**Status:** open
**Severity:** low
**Category:** external
**Raised:** Day 1  **Owner:** day-6-demo.md
**Fires when:** Testing + rehearsals + demo hit Supabase free-tier DB connection limits

**Description:** Supabase free tier has connection pool limits. Unlikely to hit with 3-minute demo traffic, but worth tracking.

**Mitigation:** Single client instance per backend process; `supabase_repos.py` shares one client across all repos (per CLAUDE.md)

**Trigger action:** Restart Railway container if connection errors surface

**Referenced by:** day-6 §Risks (prod data shared with dev)

---

#### [R-005] Cerebral Valley submission platform flakiness near deadline
**Status:** open
**Severity:** high
**Category:** external
**Raised:** Day 1  **Owner:** day-6-demo.md
**Fires when:** Submission form crashes / hangs / rejects payload in the final hour before 8 PM EST

**Description:** Hackathon submission platforms commonly get overloaded in the final hour. Submitting at 7:55 PM is the single highest-risk move of the entire sprint.

**Mitigation:**
- Submit at 6 PM EST, not 7:55 PM (day-6 §10)
- Capture confirmation email / screenshot as proof
- Have all submission fields pre-drafted in a text file; paste into form

**Trigger action:**
1. If platform crashes → try again 15 min later; contact hackathon organizers with timestamp proof of attempted submission
2. Always better to submit an imperfect entry early than a perfect entry late

**Referenced by:** day-6 §10, day-6 §Risks

---

### Security & Compliance

#### [R-006] PII leak to Anthropic
**Status:** mitigated
**Severity:** high (disqualifying if fires)
**Category:** security
**Raised:** Day 1  **Owner:** day-2-parser.md
**Fires when:** PII sanitizer skipped, runs after Haiku call, or misses a PII column; SSN/name/DOB/address/bank data reaches Claude

**Description:** Sending PII to Anthropic violates data-handling norms and is likely disqualifying for the hackathon. The Parser pipeline must strip PII **before** pandera validation and **before** the Haiku call. Pipeline order is load-bearing.

**Mitigation:**
- `tools/pii_sanitizer.py` ships Day 1
- Pipeline order hard-coded in `agents/parser.py` (Python, not prompt)
- Day-5 test `test_pii_never_in_claude_context` mocks `anthropic_llm.py` and asserts payload contains no PII values or header substrings
- Day-5 tests cover all 9 blacklist categories individually
- Never log DataFrame cell values anywhere (CLAUDE.md explicit rule)

**Trigger action:** If PII leak is discovered, immediately stop all Anthropic traffic; audit all past runs via logs; document + disclose. This is a do-not-ship condition.

**Referenced by:** CLAUDE.md Critical Files, day-1 §8, day-2 §3, day-5 §5, Golden Rules §3

---

#### [R-007] RLS isolation leak between users
**Status:** open
**Severity:** high (disqualifying if fires in live demo)
**Category:** security
**Raised:** Day 1  **Owner:** day-5-polish.md
**Fires when:** RLS policy incorrect on any table or storage bucket; user A can read user B's data

**Description:** Every company-owning table has RLS via EXISTS-through-`companies`. Storage is keyed on `(storage.foldername(name))[1] = auth.uid()::text`. A missed policy or a wrong `auth.uid()` cast leaks cross-company data.

**Mitigation:**
- Day-1 manual RLS test with two JWTs before end of Day 1
- Day-5 `tests/test_rls.py` covers 5 access paths (report / anomalies / status / SQL / storage)
- Escalation rule: **if any RLS test fails Day-5 morning, drop all other Day-5 work until fixed**

**Trigger action:** If RLS leak discovered → fix policy, re-run full Day-5 RLS test suite, spot-check via two real JWTs in Bruno

**Referenced by:** day-1 §Risks, day-5 §5 test_rls.py, day-6 §End-of-Day-Check #10

---

#### [R-008] Secrets committed to public repo
**Status:** open
**Severity:** high
**Category:** security
**Raised:** Day 6  **Owner:** day-6-demo.md
**Fires when:** Repo made public with `.env`, API keys, or service role keys in git history

**Description:** Day-6 flips the repo to public for submission. Any secret ever committed — even squashed or reverted — lives in git history and is immediately scanned by credential-harvesting bots.

**Mitigation:**
- `.gitignore` includes `.env` from Day 1
- Day-6 §8 explicit grep: `git log -p | grep -iE "SUPABASE_SERVICE_KEY|ANTHROPIC_API_KEY|RESEND_API_KEY"` must return empty
- Push final commit, THEN flip to public (not the reverse)

**Trigger action:** If leak found post-public → **rotate all three keys immediately** (Anthropic, Supabase service, Resend), force-push cleaned history, update env vars in Railway + Vercel + local `.env`, disclose in submission if relevant

**Referenced by:** day-6 §8, day-6 §Risks

---

### Design / Contract Gaps (MVP Shortcuts)

#### [R-009] MappingConfirmModal is post-hoc panel, not blocking modal
**Status:** accepted (MVP decision; full flow is post-MVP)
**Severity:** medium
**Category:** design
**Raised:** Day 2  **Owner:** day-2-parser.md (decision), day-5-polish.md (implementation)
**Fires when:** User sees low-confidence columns auto-mapped to OTHER without prompt; review panel renders after-the-fact

**Description:** `design.md` §7 specifies the modal **blocks the pipeline until resolved**. The current `db-schema.md` state machine has no `awaiting_mapping` state. Implementing blocking pause/resume requires a new state, a new endpoint, and stateful parser orchestration — too much risk for a 6-day sprint. MVP ships the non-blocking post-hoc review panel: low-confidence columns auto-map to `OTHER`, `runs.low_confidence_columns` JSONB is populated, Day-4 UI renders the review panel below the report.

**Mitigation:**
- Clear decision documented in day-2 §5 with both approaches (aspirational vs MVP)
- Auto-map to `OTHER` keeps the pipeline flowing
- Post-hoc panel lets user correct mappings for **future** uploads (persisted to `accounts`)
- Tradeoff acknowledged: current run's anomalies may include `OTHER`-bucketed items

**Trigger action:** If judges ask about this during demo: "We ship a non-blocking review panel for MVP. The blocking modal is post-hackathon — it requires an `awaiting_mapping` state and stateful pause/resume. We made the tradeoff to keep the pipeline in one clean state machine."

**Referenced by:** day-2 §5, day-4 §10, day-5 §4 MappingConfirmPanel, scope.md §Future Roadmap

---

#### [R-010] Column-level provenance is filename-only fallback if schema extension slips
**Status:** mitigated (schema extension shipped Day 4)
**Severity:** low
**Category:** design
**Raised:** Day 4  **Owner:** day-4-frontend.md
**Fires when:** `monthly_entries.source_column` column not added + Parser retrofit not completed; hover shows only filename

**Description:** `design.md` specifies provenance hover shows **both** `source_file` and original column name. Day-1 schema has only `source_file`. Day 4 ships a small schema extension (`ALTER TABLE monthly_entries ADD COLUMN source_column TEXT;`) + Parser retrofit to record original column header + API response extension.

**Mitigation:** Schema extension in day-4 §6 (small, shipped). MVP fallback documented if extension slips: filename-only provenance with a "column name captured post-MVP" footnote.

**Trigger action:** N/A — mitigated

**Referenced by:** day-4 §6, day-4 §8 AnomalyCard

---

#### [R-011] Number-level prose provenance vs card-level provenance
**Status:** accepted (card-level for MVP; number-level is post-MVP)
**Severity:** low
**Category:** design
**Raised:** Day 4  **Owner:** day-4-frontend.md
**Fires when:** Narrative prose numbers are not hoverable; only AnomalyCard figures have provenance

**Description:** `design.md` says "every number in the narrative prose is hoverable." Implementing regex-parse-and-wrap on narrative strings is ambitious in a sprint. MVP ships **card-level** provenance — every AnomalyCard's numbers have hover; narrative prose renders plain. Judge-visible impact is small: AnomalyCards are where numbers are prominent; narrative is one paragraph.

**Mitigation:** Document as MVP shortcut; wire `<Tooltip>` on AnomalyCard cleanly so upgrade to narrative parsing is straightforward post-hackathon.

**Trigger action:** None — accepted scope cut

**Referenced by:** day-4 §8 ReportSummary, day-4 §Cut Line

---

#### [R-012] `comparing_failed` terminal state missing from state machine
**Status:** open
**Severity:** low
**Category:** design
**Raised:** Day 2  **Owner:** day-2-parser.md
**Fires when:** Comparison agent crashes mid-run; no clean terminal state to transition to

**Description:** `db-schema.md` enumerates `upload_failed`, `parsing_failed`, `guardrail_failed`. No `comparing_failed`. If Comparison crashes (e.g. bad `variance_pct` math, no-history edge case), the run has no clean terminal.

**Mitigation:** Day-2 decision: use `parsing_failed` as the catch-all for all pre-Interpreter failures. Frontend renders the same plain-English error.

**Trigger action:** Post-MVP: add `comparing_failed` + `interpreting_failed` + wire frontend-specific copy for each.

**Referenced by:** day-2 §6 Comparison Agent, day-2 §Risks

---

#### [R-013] Dynamic-stdev severity not shipped
**Status:** accepted (post-MVP)
**Severity:** low
**Category:** design
**Raised:** Day 2  **Owner:** day-2-parser.md
**Fires when:** Company has 3+ months of history but severity still uses ±20% fixed threshold

**Description:** `agent-flow.md` specifies: first 3 months = ±20% fixed, after 3+ months = dynamic based on company's own stdev. MVP ships only the fixed rule.

**Mitigation:** None for MVP. Document as post-MVP work. DRONE demo has only 2 months of data so the fixed rule is what runs for the demo anyway.

**Trigger action:** None — accepted scope cut

**Referenced by:** day-2 §6 Comparison Agent, day-2 §Cut Line

---

#### [R-014] Regenerate-report flow is re-upload, not true regenerate
**Status:** accepted (MVP shortcut)
**Severity:** low
**Category:** design
**Raised:** Day 5  **Owner:** day-5-polish.md
**Fires when:** User clicks Regenerate on a Stale ReportSummary; full re-upload triggered instead of skipping Parser

**Description:** Stale state on `ReportSummary` offers "Regenerate report." A true regenerate skips Parser (data already in `monthly_entries`) and re-runs Comparison + Interpreter only. MVP shortcut: Regenerate triggers a full re-upload (user drops the file again). Simpler, one fewer endpoint.

**Mitigation:** Copy on the Stale chip explicitly says "re-upload the file." User expectation matches behavior.

**Trigger action:** None — accepted scope cut

**Referenced by:** day-5 §4 Stale state

---

#### [R-015] Storage TTL sweep for abandoned guardrail_failed runs
**Status:** accepted (post-MVP)
**Severity:** low
**Category:** design
**Raised:** Day 3  **Owner:** day-3-interpreter.md
**Fires when:** Guardrail-failed runs accumulate in Storage indefinitely (file stays on fail, per Retry Analysis design)

**Description:** Day 3 explicitly leaves the Storage file on `guardrail_failed` so Retry Analysis reuses it without re-upload. Over time, abandoned guardrail-failed runs leak Storage. For a 6-day hackathon this never fires; for production it needs a TTL sweep.

**Mitigation:** None for MVP. Post-MVP: nightly job deletes Storage files for `guardrail_failed` runs older than 7 days.

**Trigger action:** None — accepted

**Referenced by:** day-3 §5 Post-Success Storage Cleanup, CLAUDE.md Retry & Error Handling

---

### Schedule / Scope

#### [R-016] Day-1 Clean Architecture scaffold cascades
**Status:** mitigated (Day 1 shipped)
**Severity:** high (if fires)
**Category:** schedule
**Raised:** Day 1  **Owner:** day-1-foundation.md
**Fires when:** Day-1 tasks slip; Day 2 starts without domain contracts frozen / RLS correct / PII sanitizer shipped

**Description:** Day 1 is the single most important day. `PandasSummary` / `NarrativeJSON` contracts + RLS policies + PII sanitizer + JWT validator all block subsequent days. Slipping Day 1 cascades into Days 2–6.

**Mitigation:**
- day-1 §Cut Line ranks tasks by criticality (must-ship, deferrable to Day 2 morning, Day 3, post-MVP)
- Pure Python layers (domain, contracts, messages, state machine) ship first — no external dependencies
- PII sanitizer + RLS are non-negotiable

**Trigger action:** If Day 1 slips → ship minimal domain + one adapter per port; refine shapes mid-sprint; accept that rate-limit decorators slip to Day 3

**Referenced by:** day-1 §Cut Line, day-1 §Risks

---

#### [R-017] Day-4 frontend component sprawl
**Status:** open
**Severity:** high
**Category:** schedule
**Raised:** Day 1  **Owner:** day-4-frontend.md
**Fires when:** Day 4 underestimates frontend scope; components half-built, states incomplete, demo flow broken

**Description:** Frontend is consistently underestimated. Day 4 has 12+ components each with multiple states. Realistically it's a day and a half of work compressed into one day.

**Mitigation:**
- day-4 §Cut Line: Empty State, MappingConfirmPanel, Stale state, tablet polish all deferrable to Day 5
- DRONE demo has pre-loaded baseline + clean-mapping headers → happy path is the core demo
- shadcn/ui defaults instead of custom styling (CLAUDE.md discipline)

**Trigger action:** Cut to Day 5 in the order listed; never cut the Verified badge or provenance (trust signals are demo-critical)

**Referenced by:** day-4 §Cut Line, day-4 §Risks

---

#### [R-018] Day-5 test suite eats the whole day
**Status:** open
**Severity:** medium
**Category:** schedule
**Raised:** Day 5  **Owner:** day-5-polish.md
**Fires when:** Test suite (§5) consumes so much time that Resend wiring / Day-4 deferrals / polish / Day-6 pre-staging all cut

**Description:** 9 test files × ~40 tests is substantial. Writing them sequentially eats the day.

**Mitigation:**
- Parallelize: test stubs first, features in parallel, then fill test bodies
- Priority order: PII → guardrail → RLS → rest (top three are non-negotiable)
- Other tests can be deferred to "written tonight" if essential flows are green

**Trigger action:** Cut to PII + guardrail + RLS + parser pipeline + storage cleanup only. Defer rest to post-MVP.

**Referenced by:** day-5 §5, day-5 §Risks

---

#### [R-019] Day-6 submission deadline (April 26, 8:00 PM EST)
**Status:** open
**Severity:** high
**Category:** schedule
**Raised:** Day 1  **Owner:** day-6-demo.md
**Fires when:** Any Day-6 task slips; submission filed late or not at all

**Description:** Hard deadline. Late submission = no submission. Everything Day 6 funnels to one outcome: hitting the submit button before 8 PM.

**Mitigation:**
- Submit at 6 PM, not 7:55 PM (day-6 §10)
- All submission fields pre-drafted
- Capture confirmation email / screenshot as proof

**Trigger action:** Submit imperfect entry before deadline rather than perfect entry after. Missing the deadline loses everything.

**Referenced by:** day-6 §10, day-6 §Risks

---

### Demo Day

#### [R-020] Guardrail fires unexpectedly during live demo
**Status:** open
**Severity:** medium (turns into opportunity if handled well)
**Category:** demo
**Raised:** Day 3  **Owner:** day-6-demo.md
**Fires when:** Opus produces a number not in `PandasSummary` during live demo; `guardrail_failed` screen renders instead of verified report

**Description:** Guardrail is designed to fire when needed — that's the point. If it fires during demo, it can look like a bug OR a feature depending on framing.

**Mitigation:**
- Prompt is rigorous; tolerance is 2% (enough headroom for float precision)
- Day-5 + Day-6 rehearsals verify pipeline is clean on DRONE data
- Demo-day emergency lever: raise tolerance to 3% (documented as emergency-only, not normal)

**Trigger action:** If it fires live → **frame it as a feature**: "And here's the guardrail working — it refused to save an unverified report. This is exactly the point of Month Proof. Let me click Retry Analysis." Then show the retry succeeds (or pivot to Loom backup if retry also fails).

**Referenced by:** day-3 §Risks, day-6 §6 Fallback Plans

---

#### [R-021] AnomalyCard direction vs severity confusion
**Status:** mitigated (Day 4 explicit separation)
**Severity:** high (finance UX credibility)
**Category:** design
**Raised:** Day 4  **Owner:** day-4-frontend.md
**Fires when:** G&A −34% renders as red (bad) instead of green (favorable); looks like team doesn't understand finance

**Description:** The #1 bug pattern in finance UIs: conflating variance sign with severity. A negative variance can be favorable (G&A expense down) or unfavorable (revenue down). Severity (magnitude) is separate from direction (good/bad).

**Mitigation:**
- Day-4 §8 AnomalyCard API explicitly splits `direction` (drives color) from `severity` (drives label)
- Day-4 End-of-Day-Check #5 verifies G&A renders favorable green
- Smoke test fixtures include both directions

**Trigger action:** N/A — mitigated

**Referenced by:** day-4 §8, day-4 §Risks

---

### Post-MVP Backlog

Intentional scope cuts. Decided, not forgotten. Each is tracked here so it resurfaces for Day-7+ work rather than getting lost.

#### [R-100] pgvector for long-term pattern recognition
**Status:** accepted
**Category:** post-mvp
**Source:** scope.md Future Roadmap
**Decision:** SQL joins sufficient for Week 1 history comparison. pgvector adds complexity without MVP value.

#### [R-101] ERP API integration (NetSuite, QuickBooks, SAP)
**Status:** accepted
**Category:** post-mvp
**Source:** scope.md EXCLUDED
**Decision:** MVP reads file exports. Direct API integration is a full product milestone, not a hackathon feature.

#### [R-102] Multi-user / role management (Controller vs CFO)
**Status:** accepted
**Category:** post-mvp
**Source:** scope.md EXCLUDED
**Decision:** Single user per company in MVP. Role system is a Day-7+ schema change.

#### [R-103] Budget vs actuals comparison
**Status:** accepted
**Category:** post-mvp
**Source:** scope.md EXCLUDED
**Decision:** Comparison compares to historical averages only. Plan/budget layer is additive post-MVP.

#### [R-104] Draft journal entries (auto-generated JE for ERP upload)
**Status:** accepted
**Category:** post-mvp
**Source:** scope.md Future Roadmap
**Decision:** Impressive demo candidate for Day-7+; out of scope for MVP.

#### [R-105] Aspirational blocking MappingConfirmModal (true pause/resume)
**Status:** accepted
**Category:** post-mvp
**Source:** day-2 §5
**Decision:** Requires `awaiting_mapping` state + new endpoint + stateful parser. MVP ships non-blocking post-hoc panel. See [R-009].

#### [R-106] Number-level prose provenance
**Status:** accepted
**Category:** post-mvp
**Source:** day-4 §8
**Decision:** Card-level provenance for MVP. Parsing numbers out of narrative prose at render time is post-MVP. See [R-011].

#### [R-107] TrendChart / MetricCard / HistoryList components
**Status:** accepted
**Category:** post-mvp
**Source:** design.md §Component List "Optional (if time permits)"
**Decision:** Nice-to-have; not demo-critical. AnomalyCards + ReportSummary carry the demo.

#### [R-108] Prod/dev Supabase separation
**Status:** accepted
**Category:** post-mvp
**Source:** day-6 §Preconditions
**Decision:** Single Supabase project for MVP. Separate environments post-hackathon.

#### [R-109] Observability (Sentry / Datadog / structured log aggregation)
**Status:** accepted
**Category:** post-mvp
**Source:** day-6 §Cut Line
**Decision:** `trace_id` + structured JSON logs are enough for hackathon. Production observability is post-MVP.

#### [R-110] CI/CD pipeline
**Status:** accepted
**Category:** post-mvp
**Source:** day-6 §Cut Line
**Decision:** Manual deploy for hackathon. Railway + Vercel auto-deploy on push is enabled but no testing-in-CI gate.

#### [R-111] mypy strict mode everywhere
**Status:** accepted
**Category:** post-mvp
**Source:** day-5 §7
**Decision:** Day-5 runs `mypy` on `domain/` only if time permits. Strict across the codebase is post-MVP.

#### [R-112] Redis-backed rate limiting (multi-container)
**Status:** accepted
**Category:** post-mvp
**Source:** scope.md §MVP Scope
**Decision:** In-memory slowapi sufficient for single Railway container. Redis post-MVP for horizontal scale.

#### [R-113] Multi-recipient `POST /mail/send`
**Status:** accepted
**Category:** post-mvp
**Source:** day-5 §Cut Line
**Decision:** Single `to_email` for MVP. Distribution lists post-MVP.

#### [R-114] Dynamic-stdev severity ladder (3+ months history)
**Status:** accepted
**Category:** post-mvp
**Source:** day-2 §6
**Decision:** Fixed ±20% threshold for MVP. See [R-013].

#### [R-115] Storage TTL sweep for abandoned `guardrail_failed` runs
**Status:** accepted
**Category:** post-mvp
**Source:** day-3 §5
**Decision:** Files stay on guardrail failure (intentional, for Retry Analysis). TTL cleanup post-MVP. See [R-015].

#### [R-116] `comparing_failed` / `interpreting_failed` terminal states
**Status:** accepted
**Category:** post-mvp
**Source:** day-2 §6
**Decision:** `parsing_failed` is the catch-all terminal in MVP. Granular failure states post-MVP. See [R-012].

#### [R-117] Sample-Excel-download on EmptyState
**Status:** accepted
**Category:** post-mvp
**Source:** design.md §Empty State, day-4 §11
**Decision:** Optional secondary link. Cut if Day-4 runs tight.

#### [R-118] Playwright / Cypress E2E automation
**Status:** accepted
**Category:** post-mvp
**Source:** day-5 §6
**Decision:** Manual browser smoke is enough for hackathon. Automated E2E post-MVP.

#### [R-119] Configurable guardrail tolerance per company
**Status:** accepted
**Category:** post-mvp
**Source:** day-3 §Cut Line
**Decision:** Hard-coded 2% tolerance for MVP. Per-company config post-MVP.

#### [R-120] Per-row email action on /reports list
**Status:** accepted
**Category:** post-mvp
**Source:** Reports-page scoping — "Option Y"
**Decision:** MVP ships **Option X** — user clicks a row → `/report/:period` → clicks `MailButton` → email dialog. Two clicks to send.

**Option Y (deferred):** inline per-row email affordance (icon button or kebab menu) on `/reports`, wiring each row to the existing `MailButton` dialog with that row's `report_id`. One click to send from the list view.

**Why not now:**
- Keeps the Reports list visually clean (filing-cabinet feel, not action-panel feel).
- `MailButton` already exists on `ReportPage` — the flow works end-to-end today, just with one extra click.
- Marginal work (~15 min) but reopens visual-density tradeoffs that deserve a second pass post-demo.

**When to revisit:** if any demo reviewer or user says "I want to email from the list without drilling in," or if the `/reports` page gets bulk-select / multi-email features. Either of those would make the per-row affordance earn its pixels.

**Re-enabling is cheap:** `MailButton` already supports being rendered with an arbitrary `reportId` prop. Adding an icon-button variant and placing it in the `HistoryList` / Reports row is self-contained — no backend change, no API change.

---

## Fired Log

Risks that actually fire during the sprint get appended here. Format: date, risk ID, what happened, resolution, lessons.

*(Empty. Append entries as risks fire.)*

Example template:
```markdown
### 2026-04-22 — [R-XXX] Title
**What happened:** Brief factual account
**Resolution:** What was actually done
**Lesson:** What we'd do differently
```

---

## Retired Risks

Risks no longer applicable because their day has passed or the underlying concern was resolved. Struck through, not deleted.

*(Empty. Move entries here as they retire.)*

---

## Index by Category

**external** — R-001, R-002, R-003, R-004, R-005
**security** — R-006, R-007, R-008
**design** — R-009, R-010, R-011, R-012, R-013, R-014, R-015, R-021
**schedule** — R-016, R-017, R-018, R-019
**demo** — R-020, R-021
**post-mvp** — R-100 through R-120

## Index by Severity

**high** — R-001, R-002, R-003, R-005, R-006, R-007, R-008, R-016, R-017, R-019, R-021
**medium** — R-009, R-018, R-020
**low** — R-004, R-010, R-011, R-012, R-013, R-014, R-015
**accepted (post-mvp)** — R-100 through R-120

## Index by Day File

**day-1-foundation.md** — R-006, R-007, R-016
**day-2-parser.md** — R-002, R-009, R-012, R-013
**day-3-interpreter.md** — R-002, R-015, R-020
**day-4-frontend.md** — R-010, R-011, R-017, R-021
**day-5-polish.md** — R-003, R-007 (escalation), R-014, R-018
**day-6-demo.md** — R-001, R-004, R-005, R-008, R-019, R-020
